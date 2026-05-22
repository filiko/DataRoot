from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InventoryFile(BaseModel):
    id: str
    path: str
    kind: str
    language: str | None = None
    size_bytes: int
    sha256: str | None = None
    included: bool = True
    skip_reason: str | None = None


class RepositoryInventory(BaseModel):
    repo_root: str
    generated_at: str = Field(default_factory=utc_now_iso)
    files: list[InventoryFile] = Field(default_factory=list)
    detected_stack: dict[str, list[str]] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    id: str
    type: str
    source: str
    path: str | None = None
    line_start: int | None = None
    line_end: int | None = None
    excerpt: str | None = None
    tags: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    attributes: dict[str, Any] = Field(default_factory=dict)


class FactRecord(BaseModel):
    id: str
    type: str
    subject: str
    attributes: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    status: Literal["candidate", "accepted", "rejected", "superseded"] = "candidate"


class AnalyzeResult(BaseModel):
    project_config_path: str
    inventory_path: str
    evidence_path: str
    facts_path: str
    decisions_path: str
    run_log_path: str
    pen_path: str
    route_count: int
    process_count: int
