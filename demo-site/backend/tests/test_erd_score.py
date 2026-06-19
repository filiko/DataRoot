"""Tier 2 — generation eval scorer (deterministic) + a gated live-generation check.

The scorer is pure, so we verify it against the answer keys with no API key:
scoring the answer key against itself is a perfect score; corrupting the
"generated" model degrades exactly the metric it should. The actual LLM
generation runs only when MINIMAX_API_KEY is set.
"""
from __future__ import annotations

import os

import pytest

from evals.erd_score import score_erd
from evals.watt_corpus import EXERCISES, car_dealership_pen
from generators.erd_from_text import generate_erd_from_text
from llm import minimax


# ── scorer: deterministic, no API key ──────────────────────────────────────────

@pytest.mark.parametrize("ex", EXERCISES, ids=lambda e: e.key)
def test_answer_key_scores_perfectly_against_itself(ex) -> None:
    pen = ex.build()
    s = score_erd(pen, ex.build())
    assert s.entity_recall == 1.0 and s.entity_precision == 1.0
    assert s.relationship_recall == 1.0 and s.relationship_precision == 1.0
    assert s.cardinality_accuracy == 1.0
    assert s.pk_accuracy == 1.0
    assert s.missing_entities == [] and s.extra_entities == []


def test_missing_entity_lowers_recall_and_is_reported() -> None:
    answer = car_dealership_pen()
    generated = car_dealership_pen()
    generated.erd.entities = [e for e in generated.erd.entities if e.id != "ent_part"]
    s = score_erd(generated, answer)
    assert s.entity_recall < 1.0
    assert "part" in s.missing_entities


def test_wrong_cardinality_lowers_cardinality_accuracy() -> None:
    answer = car_dealership_pen()
    generated = car_dealership_pen()
    # Make Car↔Salesperson look many-to-many (wrong shape) in the generated model.
    rel = next(r for r in generated.erd.relationships if r.id == "rel_sells")
    rel.cardinality.to_max = "many"
    s = score_erd(generated, answer)
    assert s.cardinality_accuracy < 1.0
    assert s.entity_recall == 1.0  # entities unchanged


def test_extra_entity_lowers_precision() -> None:
    answer = car_dealership_pen()
    generated = car_dealership_pen()
    from models.pen import Attribute, Entity
    generated.erd.entities.append(Entity(
        id="ent_ghost", name="ghost", display_name="Ghost",
        attributes=[Attribute(id="g_pk", name="id", pg_type="uuid", key_role="primary")],
    ))
    s = score_erd(generated, answer)
    assert s.entity_precision < 1.0
    assert "ghost" in s.extra_entities


# ── live generation: only when an API key is present ───────────────────────────

@pytest.mark.skipif(not minimax.is_configured(), reason="MINIMAX_API_KEY not set")
@pytest.mark.parametrize("ex", EXERCISES, ids=lambda e: e.key)
def test_generated_erd_meets_thresholds(ex) -> None:
    result = generate_erd_from_text(ex.paragraph)
    assert result.ok, f"generation failed: {result.error}"
    s = score_erd(result.pen, ex.build())
    assert s.entity_recall >= 0.9, s.as_dict()
    assert s.cardinality_accuracy >= 0.8, s.as_dict()
