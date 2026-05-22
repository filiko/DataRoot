from __future__ import annotations

import ast
import hashlib
import re
from pathlib import Path
from typing import Any

from .models import EvidenceRecord, FactRecord, RepositoryInventory


MODEL_BASES = {"BaseModel", "TypedDict", "SQLModel", "DeclarativeBase"}
MODEL_DECORATORS = {"dataclass"}
SCALAR_TYPE_MAP = {
    "str": "text",
    "String": "text",
    "Text": "text",
    "int": "integer",
    "Integer": "integer",
    "float": "numeric",
    "Decimal": "numeric",
    "bool": "boolean",
    "Boolean": "boolean",
    "date": "date",
    "datetime": "timestamptz",
    "UUID": "uuid",
    "uuid.UUID": "uuid",
    "dict": "jsonb",
    "Dict": "jsonb",
    "list": "jsonb",
    "List": "jsonb",
}


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _safe_name(value: str) -> str:
    parts = re.findall(r"[A-Z]?[a-z0-9]+|[A-Z]+(?=[A-Z]|$)", value)
    if not parts:
        parts = re.split(r"[^A-Za-z0-9]+", value)
    name = "_".join(part.lower() for part in parts if part)
    return name or "model"


def _display_name(value: str) -> str:
    return " ".join(part.capitalize() for part in _safe_name(value).split("_"))


def _annotation_to_string(node: ast.AST | None) -> str:
    if node is None:
        return "Any"
    try:
        return ast.unparse(node)
    except Exception:
        return "Any"


def _name_from_expr(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name_from_expr(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Subscript):
        return _name_from_expr(node.value)
    if isinstance(node, ast.Call):
        return _name_from_expr(node.func)
    return None


def _decorator_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _name_from_expr(node.func)
    return _name_from_expr(node)


def _has_model_shape(node: ast.ClassDef) -> bool:
    base_names = {_name_from_expr(base) or "" for base in node.bases}
    base_tails = {name.split(".")[-1] for name in base_names}
    decorator_names = {_decorator_name(decorator) or "" for decorator in node.decorator_list}
    decorator_tails = {name.split(".")[-1] for name in decorator_names}
    has_model_base = bool(base_tails & MODEL_BASES)
    has_model_decorator = bool(decorator_tails & MODEL_DECORATORS)
    has_annotations = any(isinstance(child, ast.AnnAssign) for child in node.body)
    return has_annotations and (has_model_base or has_model_decorator)


def _field_default(value: ast.AST | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, ast.Constant):
        return repr(value.value)
    if isinstance(value, ast.Call):
        return _name_from_expr(value.func)
    return None


def _is_nullable(annotation: str, default: ast.AST | None) -> bool:
    if default is not None and isinstance(default, ast.Constant) and default.value is None:
        return True
    return "None" in annotation or "Optional" in annotation or "| None" in annotation


def _base_type(annotation: str) -> str:
    cleaned = annotation.replace("typing.", "")
    cleaned = re.sub(r"Annotated\[(.*?),.*\]$", r"\1", cleaned)
    cleaned = cleaned.replace("Optional[", "").rstrip("]")
    cleaned = cleaned.replace("None |", "").replace("| None", "").strip()
    list_match = re.match(r"(?:list|List|Sequence|set)\[(.+)\]$", cleaned)
    if list_match:
        cleaned = list_match.group(1).strip()
    union_match = re.match(r"Union\[(.+)\]$", cleaned)
    if union_match:
        cleaned = union_match.group(1).split(",")[0].strip()
    return cleaned.strip("'\"")


def _pg_type(annotation: str) -> str:
    base = _base_type(annotation)
    if base in SCALAR_TYPE_MAP:
        return SCALAR_TYPE_MAP[base]
    tail = base.split(".")[-1]
    return SCALAR_TYPE_MAP.get(tail, "jsonb" if "[" in annotation else "text")


def _key_role(field_name: str, annotation: str) -> str:
    lowered = field_name.lower()
    if lowered == "id":
        return "primary"
    if lowered.endswith("_id"):
        return "foreign"
    if lowered in {"created_at", "updated_at", "modified_at"}:
        return "audit"
    if "UUID" in annotation and lowered.endswith("id"):
        return "business_key"
    return "none"


def collect_model_evidence(repo_root: Path, inventory: RepositoryInventory) -> list[EvidenceRecord]:
    repo_root = repo_root.resolve()
    records: list[EvidenceRecord] = []
    python_files = [item for item in inventory.files if item.included and item.language == "python"]

    for item in python_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        lines = source.splitlines()
        model_classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and _has_model_shape(node)]
        class_names = {node.name for node in model_classes}

        for class_node in model_classes:
            class_id = _stable_id("ev", "model_class", item.path, class_node.name)
            records.append(EvidenceRecord(
                id=class_id,
                type="model_class",
                source="python_ast",
                path=item.path,
                line_start=class_node.lineno,
                line_end=getattr(class_node, "end_lineno", class_node.lineno),
                excerpt=lines[class_node.lineno - 1].strip() if class_node.lineno <= len(lines) else None,
                tags=["model", "python"],
                confidence=0.9,
                attributes={
                    "class_name": class_node.name,
                    "model_name": _safe_name(class_node.name),
                    "display_name": _display_name(class_node.name),
                    "language": "python",
                },
            ))

            for child in class_node.body:
                if not isinstance(child, ast.AnnAssign) or not isinstance(child.target, ast.Name):
                    continue
                field_name = child.target.id
                if field_name.startswith("_"):
                    continue
                annotation = _annotation_to_string(child.annotation)
                base = _base_type(annotation)
                field_id = _stable_id("ev", "model_field", item.path, class_node.name, field_name)
                records.append(EvidenceRecord(
                    id=field_id,
                    type="model_field",
                    source="python_ast",
                    path=item.path,
                    line_start=child.lineno,
                    line_end=getattr(child, "end_lineno", child.lineno),
                    excerpt=lines[child.lineno - 1].strip() if child.lineno <= len(lines) else None,
                    tags=["model_field", "python"],
                    confidence=0.9,
                    attributes={
                        "class_name": class_node.name,
                        "model_name": _safe_name(class_node.name),
                        "field_name": field_name,
                        "raw_type": annotation,
                        "base_type": base,
                        "pg_type": _pg_type(annotation),
                        "key_role": _key_role(field_name, annotation),
                        "nullable": _is_nullable(annotation, child.value),
                        "default": _field_default(child.value),
                        "relationship_target": base if base in class_names else None,
                        "relationship_many": bool(re.match(r"(?:list|List|Sequence|set)\[", annotation.replace("typing.", ""))),
                    },
                ))

    records.extend(_collect_typescript_model_evidence(repo_root, inventory))
    return records


_TS_INTERFACE_RE = re.compile(r"(?:export\s+)?interface\s+(\w+)\s*\{(?P<body>.*?)\}", re.S)
_TS_TYPE_RE = re.compile(r"(?:export\s+)?type\s+(\w+)\s*=\s*\{(?P<body>.*?)\}", re.S)
_TS_FIELD_RE = re.compile(r"^\s*(\w+)(\?)?\s*:\s*([^;,\n]+)", re.M)


def _collect_typescript_model_evidence(repo_root: Path, inventory: RepositoryInventory) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    ts_files = [
        item for item in inventory.files
        if item.included and item.language == "typescript" and _typescript_path_can_hold_models(item.path)
    ]
    for item in ts_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(_TS_INTERFACE_RE.finditer(source)) + list(_TS_TYPE_RE.finditer(source))
        type_names = {match.group(1) for match in matches}
        for match in matches:
            type_name = match.group(1)
            if type_name.lower().endswith("props"):
                continue
            line = source[:match.start()].count("\n") + 1
            class_id = _stable_id("ev", "model_class", item.path, type_name)
            records.append(EvidenceRecord(
                id=class_id,
                type="model_class",
                source="typescript_regex",
                path=item.path,
                line_start=line,
                line_end=line + match.group("body").count("\n") + 1,
                excerpt=source.splitlines()[line - 1].strip() if line <= len(source.splitlines()) else None,
                tags=["model", "typescript"],
                confidence=0.72,
                attributes={
                    "class_name": type_name,
                    "model_name": _safe_name(type_name),
                    "display_name": _display_name(type_name),
                    "language": "typescript",
                },
            ))
            for field_match in _TS_FIELD_RE.finditer(match.group("body")):
                field_name = field_match.group(1)
                optional = bool(field_match.group(2))
                raw_type = field_match.group(3).strip()
                base = raw_type.replace("[]", "").strip()
                field_id = _stable_id("ev", "model_field", item.path, type_name, field_name)
                records.append(EvidenceRecord(
                    id=field_id,
                    type="model_field",
                    source="typescript_regex",
                    path=item.path,
                    line_start=line + match.group("body")[:field_match.start()].count("\n"),
                    line_end=line + match.group("body")[:field_match.start()].count("\n"),
                    tags=["model_field", "typescript"],
                    confidence=0.72,
                    attributes={
                        "class_name": type_name,
                        "model_name": _safe_name(type_name),
                        "field_name": field_name,
                        "raw_type": raw_type,
                        "base_type": base,
                        "pg_type": _typescript_pg_type(raw_type),
                        "key_role": _key_role(field_name, raw_type),
                        "nullable": optional or "null" in raw_type or "undefined" in raw_type,
                        "default": None,
                        "relationship_target": base if base in type_names else None,
                        "relationship_many": raw_type.endswith("[]") or raw_type.startswith("Array<"),
                    },
                ))
    return records


def _typescript_path_can_hold_models(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return any(part in normalized for part in (
        "/types/",
        "/models/",
        "/schemas/",
        "/schema/",
        "/api/",
        "types/",
        "models/",
    ))


def _typescript_pg_type(raw_type: str) -> str:
    cleaned = raw_type.replace("[]", "").strip()
    if cleaned in {"string"}:
        return "text"
    if cleaned in {"number"}:
        return "numeric"
    if cleaned in {"boolean"}:
        return "boolean"
    if cleaned in {"Date"}:
        return "timestamptz"
    return "jsonb" if "[]" in raw_type or "Array<" in raw_type else "text"


def model_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    facts: list[FactRecord] = []
    class_records = {record.attributes.get("class_name"): record for record in records if record.type == "model_class"}
    for record in records:
        if record.type == "model_class":
            class_name = str(record.attributes["class_name"])
            subject = f"model:{record.attributes.get('language', 'code')}:{record.path}:{class_name}"
            facts.append(FactRecord(
                id=_stable_id("fact", "app.model", subject),
                type="app.model",
                subject=subject,
                attributes={
                    "class_name": class_name,
                    "name": record.attributes["model_name"],
                    "display_name": record.attributes["display_name"],
                    "language": record.attributes.get("language"),
                    "source_path": record.path,
                    "line_start": record.line_start,
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
        elif record.type == "model_field":
            class_name = str(record.attributes["class_name"])
            class_record = class_records.get(class_name)
            if class_record is None:
                continue
            model_subject = f"model:{class_record.attributes.get('language', 'code')}:{class_record.path}:{class_name}"
            field_name = str(record.attributes["field_name"])
            subject = f"{model_subject}:field:{field_name}"
            facts.append(FactRecord(
                id=_stable_id("fact", "app.attribute", subject),
                type="app.attribute",
                subject=subject,
                attributes={
                    "model_subject": model_subject,
                    "model_class": class_name,
                    "name": field_name,
                    "display_name": _display_name(field_name),
                    "raw_type": record.attributes.get("raw_type"),
                    "pg_type": record.attributes.get("pg_type"),
                    "key_role": record.attributes.get("key_role", "none"),
                    "nullable": record.attributes.get("nullable", True),
                    "source_path": record.path,
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
            target = record.attributes.get("relationship_target")
            if target and target in class_records:
                target_record = class_records[target]
                target_subject = f"model:{target_record.attributes.get('language', 'code')}:{target_record.path}:{target}"
                rel_subject = f"relationship:{model_subject}:{field_name}:{target_subject}"
                facts.append(FactRecord(
                    id=_stable_id("fact", "app.relationship", rel_subject),
                    type="app.relationship",
                    subject=rel_subject,
                    attributes={
                        "from_model_subject": model_subject,
                        "to_model_subject": target_subject,
                        "attribute_subject": subject,
                        "attribute_name": field_name,
                        "relationship_many": record.attributes.get("relationship_many", False),
                    },
                    evidence_ids=[record.id],
                    confidence=record.confidence * 0.9,
                    status="candidate",
                ))
    return facts
