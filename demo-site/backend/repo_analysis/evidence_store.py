from __future__ import annotations

import json
from pathlib import Path

from .models import EvidenceRecord


def write_evidence_jsonl(path: Path, records: list[EvidenceRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in sorted(records, key=lambda item: item.id):
            handle.write(json.dumps(record.model_dump(), sort_keys=True) + "\n")


def read_evidence_jsonl(path: Path) -> list[EvidenceRecord]:
    if not path.exists():
        return []
    records: list[EvidenceRecord] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                records.append(EvidenceRecord.model_validate_json(stripped))
    return records

