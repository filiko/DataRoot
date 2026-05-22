from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

from .models import EvidenceRecord, FactRecord, RepositoryInventory


HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _join_route(prefix: str, route_path: str) -> str:
    if not prefix:
        return route_path
    if not route_path:
        return prefix
    return f"{prefix.rstrip('/')}/{route_path.lstrip('/')}"


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _router_prefixes(tree: ast.AST) -> dict[str, str]:
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if not isinstance(value, ast.Call) or _call_name(value.func) != "APIRouter":
            continue

        prefix = ""
        for keyword in value.keywords:
            if keyword.arg == "prefix":
                prefix = _literal_string(keyword.value) or ""
                break

        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix
    return prefixes


def _decorator_route(decorator: ast.AST, router_prefixes: dict[str, str]) -> tuple[str, str] | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    method = func.attr.lower()
    if method not in HTTP_METHODS:
        return None
    if not isinstance(func.value, ast.Name):
        return None
    receiver = func.value.id
    if receiver == "app":
        prefix = ""
    elif receiver in router_prefixes or receiver == "router" or receiver.endswith("router"):
        prefix = router_prefixes.get(receiver, "")
    else:
        return None

    route_path = _literal_string(decorator.args[0]) if decorator.args else None
    if route_path is None:
        for keyword in decorator.keywords:
            if keyword.arg in {"path", "url_path"}:
                route_path = _literal_string(keyword.value)
                break
    if route_path is None:
        return None
    return method.upper(), _join_route(prefix, route_path)


def collect_fastapi_routes(repo_root: Path, inventory: RepositoryInventory) -> list[EvidenceRecord]:
    repo_root = repo_root.resolve()
    records: list[EvidenceRecord] = []
    python_files = [
        item for item in inventory.files
        if item.included and item.language == "python"
    ]

    for item in python_files:
        path = repo_root / item.path
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue

        router_prefixes = _router_prefixes(tree)
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = _decorator_route(decorator, router_prefixes)
                if route is None:
                    continue
                method, route_path = route
                line_start = getattr(decorator, "lineno", node.lineno)
                excerpt = lines[line_start - 1].strip() if 0 < line_start <= len(lines) else None
                record_id = _stable_id("ev", item.path, method, route_path, node.name)
                records.append(EvidenceRecord(
                    id=record_id,
                    type="api_route_decorator",
                    source="fastapi_ast",
                    path=item.path,
                    line_start=line_start,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    excerpt=excerpt,
                    tags=["api_route", "fastapi"],
                    confidence=0.95,
                    attributes={
                        "method": method,
                        "route_path": route_path,
                        "handler": node.name,
                        "handler_line_start": node.lineno,
                        "handler_line_end": getattr(node, "end_lineno", node.lineno),
                    },
                ))

    return records


def route_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    facts: list[FactRecord] = []
    for record in records:
        if record.type != "api_route_decorator":
            continue
        attrs: dict[str, Any] = record.attributes
        method = str(attrs["method"])
        route_path = str(attrs["route_path"])
        handler = str(attrs["handler"])
        route_subject = f"route:{method}:{route_path}"
        process_subject = f"process:fastapi:{method}:{route_path}"

        facts.append(FactRecord(
            id=_stable_id("fact", "api.route", route_subject),
            type="api.route",
            subject=route_subject,
            attributes={
                "method": method,
                "path": route_path,
                "handler": handler,
                "framework": "fastapi",
                "source_path": record.path,
            },
            evidence_ids=[record.id],
            confidence=0.95,
            status="candidate",
        ))
        facts.append(FactRecord(
            id=_stable_id("fact", "flow.process", process_subject, handler),
            type="flow.process",
            subject=process_subject,
            attributes={
                "name": _handler_to_process_name(handler),
                "handler": handler,
                "route_subject": route_subject,
                "source_path": record.path,
            },
            evidence_ids=[record.id],
            confidence=0.82,
            status="candidate",
        ))
    return facts


def auto_accept_phase_a_facts(facts: list[FactRecord]) -> list[FactRecord]:
    accepted: list[FactRecord] = []
    for fact in facts:
        next_fact = fact.model_copy(deep=True)
        if next_fact.status == "candidate" and next_fact.type in {
            "api.route",
            "flow.process",
            "app.model",
            "app.attribute",
            "app.relationship",
            "code.symbol",
            "code.call_edge",
        }:
            next_fact.status = "accepted"
        accepted.append(next_fact)
    return accepted


def _handler_to_process_name(handler: str) -> str:
    words = handler.strip("_").replace("_", " ").split()
    if not words:
        return "Handle request"
    return " ".join(word.capitalize() for word in words)
