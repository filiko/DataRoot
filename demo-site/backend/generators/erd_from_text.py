"""ERD generation (eval-scoped): English business rules → an ERD PenFile.

Used by the generation eval (evals/run_erd_eval.py) to test the literal textbook
task — read a business-rule paragraph and produce the ERD — then score the result
against the Watt answer key. Deliberately NOT wired into the demo UI.

The LLM call routes through MiniMax (llm/minimax.py) at temperature 0, so the
token-heavy generation runs off the main model. The model is handed the ErdModel
JSON schema as its target and asked to emit a single JSON object; we validate it
with `ErdModel.model_validate` and normalize via `apply_rules_gate`.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from generators.diagram_rules import apply_rules_gate
from llm import minimax
from models.pen import ErdModel, PenFile


@dataclass
class GenerationResult:
    pen: PenFile | None
    raw: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.pen is not None


_SYSTEM = """You are a database modeler. Read the business rules and produce a \
physical entity-relationship diagram (crow's-foot) as a SINGLE JSON object — no \
markdown, no prose, no code fences — matching the provided JSON schema.

Modeling rules:
- Every entity needs a primary-key attribute (key_role="primary", nullable=false).
- A reference to another entity is a foreign-key attribute (key_role="foreign") \
plus a relationship whose "from" endpoint is that foreign key and whose "to" \
endpoint is the referenced entity's primary key.
- RESOLVE every many-to-many with a junction/associative entity and two \
many-to-one relationships — never emit a single relationship with from_max="many" \
AND to_max="many".
- cardinality.from_max / to_max are either an integer (use 1) or the string \
"many"; from_min / to_min are 0 (optional) or 1 (mandatory). The "from" side holds \
the foreign key (the "many" side); the "to" side is the referenced parent.
- Use snake_case entity/attribute names. Give every entity, attribute and \
relationship a short unique "id".

Output ONLY the JSON object with top-level keys "entities" and "relationships"."""


def _extract_json(raw: str) -> dict | None:
    for candidate in (raw, *(_brace_spans(raw))):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def _brace_spans(raw: str) -> list[str]:
    # Largest balanced {...} block, then any {...} via a permissive regex.
    out: list[str] = []
    start = raw.find("{")
    end = raw.rfind("}")
    if 0 <= start < end:
        out.append(raw[start:end + 1])
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        out.append(m.group(0))
    return out


def erd_schema_hint() -> str:
    """The ErdModel JSON schema — the LLM's generation target."""
    return json.dumps(ErdModel.model_json_schema(), separators=(",", ":"))


def generate_erd_from_text(paragraph: str, *, max_tokens: int = 3000) -> GenerationResult:
    """Generate an ERD PenFile from a business-rule paragraph. Never raises —
    returns a GenerationResult whose `error` is set on any failure."""
    if not minimax.is_configured():
        return GenerationResult(pen=None, raw="", error="MINIMAX_API_KEY not configured")

    user = f"JSON schema for the ERD:\n{erd_schema_hint()}\n\nBusiness rules:\n{paragraph}"
    try:
        raw = minimax._complete(_SYSTEM, user, max_tokens=max_tokens, temperature=0)
    except Exception as e:  # noqa: BLE001 — eval must not crash the run
        return GenerationResult(pen=None, raw="", error=f"LLM call failed: {e}")

    data = _extract_json(raw)
    if data is None:
        return GenerationResult(pen=None, raw=raw, error="no JSON object found in response")
    try:
        erd = ErdModel.model_validate(data)
    except Exception as e:  # noqa: BLE001
        return GenerationResult(pen=None, raw=raw, error=f"schema validation failed: {e}")

    pen = PenFile()
    pen.erd = erd
    try:
        apply_rules_gate(pen)  # normalize derived DFD + structural warnings
    except Exception as e:  # noqa: BLE001
        return GenerationResult(pen=pen, raw=raw, error=f"rules gate raised: {e}")
    return GenerationResult(pen=pen, raw=raw, error=None)
