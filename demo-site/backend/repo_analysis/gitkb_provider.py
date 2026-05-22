from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .models import EvidenceRecord, FactRecord


SYMBOL_LINE_RE = re.compile(
    r"^(?P<kind>class|function|method|component|interface|type|type_alias)\s+"
    r"(?P<name>\S+)\s+(?P<path>.+):(?P<line>\d+)\s*$"
)
NATIVE_CALLER_RE = re.compile(r"^\s+(?P<path>.+):(?P<line>\d+)\s+in\s+(?P<caller>\S+)\s*$")
NATIVE_CALLEE_RE = re.compile(r"^\s+calls:\s+(?P<callee>\S+)\s*$")
CLI_CALL_RE = re.compile(
    r"^(?:function|method)\s+(?P<name>\S+)\s+(?P<path>.+):(?P<line>\d+)"
    r"(?:\s+\(called at line (?P<called_line>\d+)\))?"
)


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def gitkb_artifact_status(artifact_dir: Path) -> str:
    if not artifact_dir.exists():
        return "missing"
    if not (artifact_dir / "summary.txt").exists():
        return "missing-summary"
    if not any((artifact_dir / name).exists() for name in ("symbols_python.txt", "symbols_typescript.txt")):
        return "missing-symbols"
    return "available"


def collect_gitkb_evidence(repo_root: Path, artifact_dir: Path) -> list[EvidenceRecord]:
    artifact_dir = artifact_dir.resolve()
    records: list[EvidenceRecord] = []
    if gitkb_artifact_status(artifact_dir) != "available":
        return records

    for filename, language in (("symbols_python.txt", "python"), ("symbols_typescript.txt", "typescript"), ("symbols_functions.txt", "code")):
        records.extend(_parse_symbol_file(artifact_dir / filename, language))

    records.extend(_parse_callers_file(artifact_dir / "callers_build_dfd_from_erd.txt", "build_dfd_from_erd"))
    records.extend(_parse_callees_file(artifact_dir / "callees_propagate_erd_to_dfd.txt", "propagate_erd_to_dfd"))
    return _dedupe(records)


def _parse_symbol_file(path: Path, language: str) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    records: list[EvidenceRecord] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SYMBOL_LINE_RE.match(line.strip())
        if not match:
            continue
        kind = match.group("kind")
        name = match.group("name")
        source_path = match.group("path").strip()
        line_number = int(match.group("line"))
        records.append(EvidenceRecord(
            id=_stable_id("ev", "gitkb_symbol", language, kind, source_path, name, str(line_number)),
            type="code_symbol",
            source="gitkb_artifact",
            path=source_path,
            line_start=line_number,
            line_end=line_number,
            excerpt=line.strip(),
            tags=["gitkb", "symbol", language],
            confidence=0.88 if language == "code" else 0.92,
            attributes={
                "name": name,
                "kind": kind,
                "language": language,
                "qualified_name": name,
            },
        ))
    return records


def _parse_callers_file(path: Path, callee: str) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    records: list[EvidenceRecord] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        native = NATIVE_CALLER_RE.match(line)
        if native:
            caller = native.group("caller")
            source_path = native.group("path")
            line_number = int(native.group("line"))
            records.append(_call_edge_record(caller, callee, source_path, line_number, line.strip()))
            continue
        cli = CLI_CALL_RE.match(line.strip())
        if cli:
            caller = cli.group("name")
            source_path = cli.group("path")
            line_number = int(cli.group("called_line") or cli.group("line"))
            records.append(_call_edge_record(caller, callee, source_path, line_number, line.strip()))
    return records


def _parse_callees_file(path: Path, caller: str) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    records: list[EvidenceRecord] = []
    header_path: str | None = None
    header_line: int | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        header = re.search(r"\((?:function|method)\s+(.+):(\d+)\)", line)
        if header:
            header_path = header.group(1)
            header_line = int(header.group(2))
            continue
        native = NATIVE_CALLEE_RE.match(line)
        if native:
            callee = native.group("callee")
            records.append(_call_edge_record(caller, callee, header_path, header_line, line.strip()))
            continue
        cli = CLI_CALL_RE.match(line.strip())
        if cli:
            callee = cli.group("name")
            source_path = cli.group("path")
            line_number = int(cli.group("called_line") or cli.group("line"))
            records.append(_call_edge_record(caller, callee, source_path, line_number, line.strip()))
    return records


def _call_edge_record(
    caller: str,
    callee: str,
    source_path: str | None,
    line_number: int | None,
    excerpt: str,
) -> EvidenceRecord:
    return EvidenceRecord(
        id=_stable_id("ev", "gitkb_call", caller, callee, source_path or "", str(line_number or "")),
        type="code_call_edge",
        source="gitkb_artifact",
        path=source_path,
        line_start=line_number,
        line_end=line_number,
        excerpt=excerpt,
        tags=["gitkb", "call_edge"],
        confidence=0.86,
        attributes={
            "caller": caller,
            "callee": callee,
        },
    )


def _dedupe(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    seen: set[str] = set()
    result: list[EvidenceRecord] = []
    for record in records:
        if record.id in seen:
            continue
        seen.add(record.id)
        result.append(record)
    return result


def gitkb_evidence_to_facts(records: list[EvidenceRecord]) -> list[FactRecord]:
    facts: list[FactRecord] = []
    for record in records:
        if record.type == "code_symbol":
            subject = f"symbol:{record.attributes.get('language')}:{record.path}:{record.attributes.get('name')}"
            facts.append(FactRecord(
                id=_stable_id("fact", "code.symbol", subject),
                type="code.symbol",
                subject=subject,
                attributes={
                    "name": record.attributes.get("name"),
                    "kind": record.attributes.get("kind"),
                    "language": record.attributes.get("language"),
                    "source_path": record.path,
                    "line_start": record.line_start,
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
        elif record.type == "code_call_edge":
            caller = str(record.attributes.get("caller"))
            callee = str(record.attributes.get("callee"))
            subject = f"call:{caller}:{callee}:{record.path}:{record.line_start}"
            facts.append(FactRecord(
                id=_stable_id("fact", "code.call_edge", subject),
                type="code.call_edge",
                subject=subject,
                attributes={
                    "caller": caller,
                    "callee": callee,
                    "source_path": record.path,
                    "line_start": record.line_start,
                },
                evidence_ids=[record.id],
                confidence=record.confidence,
                status="candidate",
            ))
    return facts
