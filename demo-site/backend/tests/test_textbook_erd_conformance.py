"""Tier 1 — verification conformance against the textbook answer key.

Encodes Watt & Eng, Appendix B (CC BY 4.0) Exercises 1 & 2 as known-correct
ERDs and asserts the verification layers agree with the textbook:

  * the answer-key ERD raises NO structural violation (ERD-02/05/06/07);
  * the cardinality rules verify as `enforced` (V1);
  * optionality/participation rules (mandatory-only) are LEFT UNTOUCHED;
  * each corrupted variant raises exactly the expected rule;
  * the may/must/one/many translation reads the verbatim sentences correctly.

These are the regression gate: they go red if the verifier regresses on the
clobber / cardinality-parsing / referential-integrity behavior.
"""
from __future__ import annotations

from evals.watt_corpus import (
    RULE_BUYS,
    RULE_PARTS_OPTIONAL,
    RULE_SELLS,
    RULE_SERVICE_M2M,
    car_dealership_pen,
    manufacturer_pen,
)
from generators.business_rule_verification import (
    parse_cardinality_expectation,
    verify_business_rules,
)
from generators.diagram_rules import detect_violations
from models.pen import (
    Cardinality,
    Relationship,
    RelationshipEndpoint,
    ReviewProposal,
)


def _erd_violation_ids(pen) -> list[str]:
    return sorted(v.rule_id for v in detect_violations(pen) if v.rule_id.startswith("ERD-"))


def _rule(pen, rule_id: str):
    return next(r for r in pen.dfd.business_rules if r.id == rule_id)


def _attr(pen, entity_id: str, attr_id: str):
    ent = next(e for e in pen.erd.entities if e.id == entity_id)
    return next(a for a in ent.attributes if a.id == attr_id)


# ── Positive: answer keys are structurally clean ──────────────────────────────

def test_manufacturer_answer_key_has_no_structural_violations() -> None:
    assert _erd_violation_ids(manufacturer_pen()) == []


def test_car_dealership_answer_key_has_no_structural_violations() -> None:
    assert _erd_violation_ids(car_dealership_pen()) == []


def test_manyto_many_resolved_by_junction_does_not_trip_erd02() -> None:
    # Component↔Product and Component↔Supplier are M:N, resolved by Build/CompSupp;
    # Mechanic↔Car is resolved by WorkOn. None should raise the direct-M:N rule.
    assert "ERD-02" not in _erd_violation_ids(manufacturer_pen())
    assert "ERD-02" not in _erd_violation_ids(car_dealership_pen())


# ── V1: cardinality rules verify enforced; optionality rules untouched ─────────

def test_two_sided_sales_rules_verify_enforced() -> None:
    pen = car_dealership_pen()
    verify_business_rules(pen)
    assert _rule(pen, "rule_sells").status == "enforced"
    assert _rule(pen, "rule_buys").status == "enforced"
    assert "consistent" in (_rule(pen, "rule_sells").verified_by or "")


def test_service_many_rule_verifies_enforced() -> None:
    pen = car_dealership_pen()
    verify_business_rules(pen)
    # "worked on by many mechanics …" — a many claim, consistent with the junction
    # relationship's many side.
    assert _rule(pen, "rule_service").status == "enforced"


def test_optional_parts_rule_left_untouched() -> None:
    pen = car_dealership_pen()
    verify_business_rules(pen)
    # "may or may not need parts" carries no max claim → not a cardinality rule.
    assert _rule(pen, "rule_parts").status == "deferred"


def test_manufacturer_participation_rules_left_untouched() -> None:
    pen = manufacturer_pen()
    verify_business_rules(pen)
    # mandatory-only optionality narrative — must not be clobbered to gap even
    # though each rule is linked to an entity.
    assert _rule(pen, "rule_mfr_product_needs_components").status == "deferred"
    assert _rule(pen, "rule_mfr_supplier_optional").status == "deferred"


# ── Negative: each corruption raises exactly the expected rule ─────────────────

def test_nullable_fk_on_mandatory_reference_raises_erd06() -> None:
    pen = car_dealership_pen()
    _attr(pen, "ent_car", "car_sp_fk").nullable = True  # each car must have one salesperson
    ids = _erd_violation_ids(pen)
    assert "ERD-06" in ids


def test_dangling_relationship_endpoint_raises_erd05() -> None:
    pen = car_dealership_pen()
    rel = next(r for r in pen.erd.relationships if r.id == "rel_sells")
    rel.from_.attribute_id = "DOES_NOT_EXIST"
    assert "ERD-05" in _erd_violation_ids(pen)


def test_entity_without_primary_key_raises_erd07() -> None:
    pen = car_dealership_pen()
    _attr(pen, "ent_car", "car_pk").key_role = "none"  # strip Car's primary key
    assert "ERD-07" in _erd_violation_ids(pen)


def test_unresolved_many_to_many_raises_erd02() -> None:
    pen = car_dealership_pen()
    # A direct M:N between two entities with NO bridging entity (mechanic↔part —
    # nothing references both), plus the pending join proposal the tool raises:
    # the textbook's "resolve this M:N" situation.
    pen.erd.relationships.append(Relationship(
        id="rel_bad_m2m", name="direct",
        from_=RelationshipEndpoint(entity_id="ent_mechanic", attribute_id="me_pk"),
        to=RelationshipEndpoint(entity_id="ent_part", attribute_id="pt_pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=0, to_max="many"),
        review_status="accepted",
    ))
    pen.review.proposals.append(ReviewProposal(
        proposal_type="many_to_many_join",
        title="Resolve mechanic↔part many-to-many",
        question="Create a junction table?",
        options=["Yes", "No"],
        context={"from_table": "mechanic", "to_table": "part"},
        status="pending",
    ))
    assert "ERD-02" in _erd_violation_ids(pen)


def test_rule_contradicting_cardinality_becomes_gap() -> None:
    pen = car_dealership_pen()
    _rule(pen, "rule_sells").statement = "Salespeople and cars have a many-to-many relationship."
    verify_business_rules(pen)
    assert _rule(pen, "rule_sells").status == "gap"
    assert "many-to-many" in (_rule(pen, "rule_sells").verified_by or "")


def test_one_to_many_rule_gaps_when_relationship_is_one_to_one() -> None:
    pen = car_dealership_pen()
    rel = next(r for r in pen.erd.relationships if r.id == "rel_sells")
    rel.cardinality = Cardinality(from_min=1, from_max=1, to_min=1, to_max=1)  # 1:1
    verify_business_rules(pen)
    # RULE_SELLS is one-to-many; a 1:1 relationship contradicts it.
    assert _rule(pen, "rule_sells").status == "gap"


# ── Translation unit: the may/must/one/many parser on verbatim sentences ───────

def test_parser_reads_two_sided_one_to_many() -> None:
    exp = parse_cardinality_expectation(RULE_SELLS)
    assert exp.one_to_many is True
    assert exp.mentions_cardinality is True
    assert exp.mandatory is False  # "may"


def test_parser_reads_buys_as_one_to_many() -> None:
    assert parse_cardinality_expectation(RULE_BUYS).one_to_many is True


def test_parser_reads_service_as_many() -> None:
    exp = parse_cardinality_expectation(RULE_SERVICE_M2M)
    assert exp.max_one is False  # "many" on both sides, no single-reference claim


def test_parser_ignores_optional_parts_statement() -> None:
    assert parse_cardinality_expectation(RULE_PARTS_OPTIONAL).mentions_cardinality is False
