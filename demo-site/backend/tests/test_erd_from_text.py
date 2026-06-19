"""Generator pipeline (offline): JSON extraction → ErdModel validation → gate.

Monkeypatches the MiniMax client so the full generate→validate→apply_rules_gate
path is exercised without an API key. The live LLM call is covered (when a key is
present) by tests/test_erd_score.py.
"""
from __future__ import annotations

from evals.erd_score import score_erd
from evals.watt_corpus import car_dealership_pen
from generators import erd_from_text
from llm import minimax

_CANNED = """Sure — here is the ERD:
```json
{
  "entities": [
    {"id": "e_customer", "name": "customer", "display_name": "Customer",
     "attributes": [{"id": "a_pk", "name": "id", "pg_type": "uuid", "key_role": "primary", "nullable": false}]},
    {"id": "e_order", "name": "order", "display_name": "Order",
     "attributes": [{"id": "o_pk", "name": "id", "pg_type": "uuid", "key_role": "primary", "nullable": false},
                    {"id": "o_fk", "name": "customer_id", "pg_type": "uuid", "key_role": "foreign", "nullable": false}]}
  ],
  "relationships": [
    {"id": "r1", "name": "places",
     "from": {"entity_id": "e_order", "attribute_id": "o_fk"},
     "to": {"entity_id": "e_customer", "attribute_id": "a_pk"},
     "cardinality": {"from_min": 0, "from_max": "many", "to_min": 1, "to_max": 1}}
  ]
}
```
"""


def test_generator_extracts_validates_and_gates(monkeypatch) -> None:
    monkeypatch.setattr(minimax, "is_configured", lambda: True)
    monkeypatch.setattr(minimax, "_complete", lambda *a, **k: _CANNED)

    result = erd_from_text.generate_erd_from_text("A customer may place many orders.")
    assert result.ok, result.error
    names = {e.name for e in result.pen.erd.entities}
    assert names == {"customer", "order"}
    assert len(result.pen.erd.relationships) == 1
    # The customer/order ERD scores as a clean one-to-many against itself.
    s = score_erd(result.pen, result.pen)
    assert s.entity_recall == 1.0 and s.cardinality_accuracy == 1.0


def test_generator_reports_bad_json_without_raising(monkeypatch) -> None:
    monkeypatch.setattr(minimax, "is_configured", lambda: True)
    monkeypatch.setattr(minimax, "_complete", lambda *a, **k: "no json here, sorry")
    result = erd_from_text.generate_erd_from_text("anything")
    assert not result.ok and result.error


def test_generator_skips_when_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(minimax, "is_configured", lambda: False)
    result = erd_from_text.generate_erd_from_text(car_dealership_pen().project.name)
    assert not result.ok and "MINIMAX_API_KEY" in (result.error or "")
