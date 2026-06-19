"""V1 business-rule verification: rule statement ↔ ERD cardinality.

Uses textbook-style phrasings (cf. Watt, Appendix B sample ERD exercises) to
check the may/must/one/many translation drives enforced/gap status correctly,
and that behavioral rules are left untouched.
"""
from __future__ import annotations

from generators.business_rule_verification import (
    parse_cardinality_expectation,
    verify_business_rules,
)
from models.pen import (
    Attribute,
    BusinessRule,
    Cardinality,
    Entity,
    PenFile,
    Relationship,
    RelationshipEndpoint,
)


def _customer_order_pen(card: Cardinality) -> PenFile:
    customer = Entity(id="customer", name="customer", display_name="Customer",
                      attributes=[Attribute(id="c_pk", name="id", pg_type="uuid", key_role="primary")])
    order = Entity(id="order", name="order", display_name="Order",
                   attributes=[Attribute(id="o_pk", name="id", pg_type="uuid", key_role="primary"),
                               Attribute(id="o_fk", name="customer_id", pg_type="uuid", key_role="foreign")])
    rel = Relationship(
        id="rel_places", name="places",
        from_=RelationshipEndpoint(entity_id="order", attribute_id="o_fk"),
        to=RelationshipEndpoint(entity_id="customer", attribute_id="c_pk"),
        cardinality=card,
    )
    pen = PenFile()
    pen.erd.entities = [customer, order]
    pen.erd.relationships = [rel]
    return pen


def _rule(statement: str, **kw) -> BusinessRule:
    return BusinessRule(
        id="r1", title="t", statement=statement,
        category="invariant", severity="constraint", status="deferred", **kw,
    )


# ── parser ────────────────────────────────────────────────────────────────────

def test_parser_reads_many_and_optional() -> None:
    exp = parse_cardinality_expectation("A customer may place many orders.")
    assert exp.mentions_cardinality and exp.max_one is False and exp.mandatory is False


def test_parser_reads_mandatory_one() -> None:
    exp = parse_cardinality_expectation("Each order must belong to exactly one customer.")
    assert exp.mandatory is True and exp.max_one is True


def test_parser_reads_m2m() -> None:
    assert parse_cardinality_expectation("Students have a many-to-many link to courses.").m2m


def test_parser_ignores_behavioral_statement() -> None:
    exp = parse_cardinality_expectation("A batch status transitions REVIEW → APPROVED on sign-off.")
    assert not exp.mentions_cardinality


# ── verification: enforced vs gap ──────────────────────────────────────────────

# many_to_one: order(many) → customer(one), each order mandatory to one customer
_M2O = Cardinality(from_min=0, from_max="many", to_min=1, to_max=1)
# one_to_one
_O2O = Cardinality(from_min=1, from_max=1, to_min=1, to_max=1)


def test_enforced_when_statement_matches_cardinality() -> None:
    pen = _customer_order_pen(_M2O)
    pen.dfd.business_rules = [_rule("Each order must belong to exactly one customer.",
                                    relationship_id="rel_places")]
    verify_business_rules(pen)
    assert pen.dfd.business_rules[0].status == "enforced"
    assert "consistent" in (pen.dfd.business_rules[0].verified_by or "")


def test_gap_when_many_claim_contradicts_one_to_one() -> None:
    pen = _customer_order_pen(_O2O)
    pen.dfd.business_rules = [_rule("A customer may place many orders.",
                                    relationship_id="rel_places")]
    verify_business_rules(pen)
    assert pen.dfd.business_rules[0].status == "gap"
    assert "many" in (pen.dfd.business_rules[0].verified_by or "")


def test_gap_when_m2m_claim_contradicts_many_to_one() -> None:
    pen = _customer_order_pen(_M2O)
    pen.dfd.business_rules = [_rule("Customer and order are many-to-many.",
                                    relationship_id="rel_places")]
    verify_business_rules(pen)
    assert pen.dfd.business_rules[0].status == "gap"


def test_gap_when_cardinality_stated_but_no_relationship() -> None:
    pen = _customer_order_pen(_M2O)
    pen.erd.relationships = []  # rule claims cardinality but nothing to check against
    pen.dfd.business_rules = [_rule("A customer may place many orders.", entity_id="customer")]
    verify_business_rules(pen)
    assert pen.dfd.business_rules[0].status == "gap"


def test_behavioral_rule_status_untouched() -> None:
    pen = _customer_order_pen(_M2O)
    rule = _rule("A batch must be released before it can ship.", entity_id="order")
    rule.status = "enforced"
    pen.dfd.business_rules = [rule]
    verify_business_rules(pen)
    # "must" + no one/many → no cardinality max claim; mandatory-only with a
    # mandatory-side relationship is consistent, so it should NOT become a gap.
    assert pen.dfd.business_rules[0].status == "enforced"


def test_resolves_by_entity_id_when_single_relationship() -> None:
    pen = _customer_order_pen(_M2O)
    pen.dfd.business_rules = [_rule("Each order must reference exactly one customer.", entity_id="order")]
    verify_business_rules(pen)
    assert pen.dfd.business_rules[0].status == "enforced"
