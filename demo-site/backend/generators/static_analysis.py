"""Static analysis — runs the full rule engine over a PenFile."""
from __future__ import annotations

from models.pen import PenFile
from generators.diagram_rules import detect_violations
from generators.sync_engine import Conflict, validate


def run_full_analysis(pen: PenFile) -> tuple[list[Conflict], list]:
    """Return (referential conflicts, structural rule violations).

    Conflicts are detected by `sync_engine.validate` (broken refs, M2M-no-join).
    Rule violations are detected by the diagram rules engine.

    The /schema/{id}/analyze route unpacks this tuple — callers that only want
    one of the two should use the underlying functions directly.
    """
    return validate(pen), detect_violations(pen)
