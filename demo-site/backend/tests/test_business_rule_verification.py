"""V0 business-rule verification: ERD structural integrity checks (ERD-05/06/07).

See docs/business-rule-verification.md for the framing. These checks live in
generators/diagram_rules.py and surface via the existing rules gate.
"""
from __future__ import annotations

from generators.diagram_rules import apply_rules_gate, detect_violations
from models.pen import (
    Attribute,
    Cardinality,
    Entity,
    PenFile,
    Relationship,
    RelationshipEndpoint,
)


def _attr(attr_id: str, name: str, *, key_role: str = "none", nullable: bool = True) -> Attribute:
    return Attribute(id=attr_id, name=name, pg_type="uuid", key_role=key_role, nullable=nullable)


def _pen(entities: list[Entity], relationships: list[Relationship] | None = None) -> PenFile:
    pen = PenFile()
    pen.erd.entities = entities
    pen.erd.relationships = relationships or []
    return pen


def _ids(pen: PenFile, rule_id: str) -> list[str]:
    return [v.rule_id for v in detect_violations(pen) if v.rule_id == rule_id]


# ── ERD-07: entity integrity (primary key) ───────────────────────────────────

def test_erd07_flags_entity_without_primary_key() -> None:
    ent = Entity(id="e1", name="customer", display_name="Customer",
                 attributes=[_attr("a1", "name")])  # no primary
    assert _ids(_pen([ent]), "ERD-07") == ["ERD-07"]


def test_erd07_clean_when_primary_key_present() -> None:
    ent = Entity(id="e1", name="customer", display_name="Customer",
                 attributes=[_attr("a1", "id", key_role="primary"), _attr("a2", "name")])
    assert _ids(_pen([ent]), "ERD-07") == []


# ── ERD-05: broken relationship endpoint (referential integrity) ──────────────

def _two_entities_with_fk(*, fk_nullable: bool = False) -> tuple[Entity, Entity]:
    parent = Entity(id="parent", name="customer", display_name="Customer",
                    attributes=[_attr("pk", "id", key_role="primary")])
    child = Entity(id="child", name="order", display_name="Order",
                   attributes=[_attr("ck", "id", key_role="primary"),
                               _attr("fk", "customer_id", key_role="foreign", nullable=fk_nullable)])
    return parent, child


def test_erd05_flags_dangling_attribute() -> None:
    parent, child = _two_entities_with_fk()
    rel = Relationship(
        name="places",
        from_=RelationshipEndpoint(entity_id="child", attribute_id="DOES_NOT_EXIST"),
        to=RelationshipEndpoint(entity_id="parent", attribute_id="pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
    )
    assert _ids(_pen([parent, child], [rel]), "ERD-05") == ["ERD-05"]


def test_erd05_flags_missing_entity() -> None:
    parent, child = _two_entities_with_fk()
    rel = Relationship(
        from_=RelationshipEndpoint(entity_id="child", attribute_id="fk"),
        to=RelationshipEndpoint(entity_id="GHOST", attribute_id="pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
    )
    assert _ids(_pen([parent, child], [rel]), "ERD-05") == ["ERD-05"]


def test_erd05_clean_when_endpoints_resolve() -> None:
    parent, child = _two_entities_with_fk()
    rel = Relationship(
        from_=RelationshipEndpoint(entity_id="child", attribute_id="fk"),
        to=RelationshipEndpoint(entity_id="parent", attribute_id="pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
    )
    assert _ids(_pen([parent, child], [rel]), "ERD-05") == []


# ── ERD-06: mandatory reference with nullable FK ──────────────────────────────

def _mandatory_rel() -> Relationship:
    return Relationship(
        from_=RelationshipEndpoint(entity_id="child", attribute_id="fk"),
        to=RelationshipEndpoint(entity_id="parent", attribute_id="pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
    )


def test_erd06_flags_mandatory_with_nullable_fk() -> None:
    parent, child = _two_entities_with_fk(fk_nullable=True)
    assert _ids(_pen([parent, child], [_mandatory_rel()]), "ERD-06") == ["ERD-06"]


def test_erd06_clean_when_fk_not_null() -> None:
    parent, child = _two_entities_with_fk(fk_nullable=False)
    assert _ids(_pen([parent, child], [_mandatory_rel()]), "ERD-06") == []


def test_erd06_clean_when_relationship_optional() -> None:
    parent, child = _two_entities_with_fk(fk_nullable=True)
    rel = Relationship(
        from_=RelationshipEndpoint(entity_id="child", attribute_id="fk"),
        to=RelationshipEndpoint(entity_id="parent", attribute_id="pk"),
        cardinality=Cardinality(from_min=0, from_max="many", to_min=0, to_max=1),  # optional
    )
    assert _ids(_pen([parent, child], [rel]), "ERD-06") == []


# ── Rules gate wiring ─────────────────────────────────────────────────────────

def test_rules_gate_surfaces_new_warnings() -> None:
    ent = Entity(id="e1", name="customer", display_name="Customer",
                 attributes=[_attr("a1", "name")])  # no PK + orphan
    pen = apply_rules_gate(_pen([ent]))
    rule_ids = {w.rule_id for w in pen.review.warnings}
    assert "ERD-07" in rule_ids
