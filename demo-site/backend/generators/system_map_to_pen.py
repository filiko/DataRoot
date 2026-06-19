"""P3 — project a System Map into a PenFile so it surfaces in the demo.

Turns the source-agnostic System Map (src/dataroot/systemmap) into the diagram
PenFile the demo renders: DataObjects → ERD entities (+ fields), shared-identifier
references → ERD relationships, connectors + detected cross-system seams →
pen.dfd.connectors, and System Map business rules → pen.dfd.business_rules with
their cross-system grounding status. See docs/business-rule-verification.md and
docs/data-access-map.md §6.
"""
from __future__ import annotations

import re

from dataroot.systemmap import (
    SystemMap,
    detect_cross_system_seams,
    ground_business_rules,
)
from dataroot.systemmap.models import Connector as SMConnector
from dataroot.systemmap.seams import _normalize, _referenced_base

from models.pen import (
    Attribute,
    BusinessRule,
    Cardinality,
    Connector,
    Entity,
    PenFile,
    ProjectMeta,
    Relationship,
    RelationshipEndpoint,
)

_PG_TYPE = {
    "string": "text", "str": "text", "text": "text", "uuid": "uuid",
    "number": "numeric", "float": "numeric", "decimal": "numeric",
    "integer": "integer", "int": "integer", "bigint": "bigint",
    "boolean": "boolean", "bool": "boolean", "enum": "text",
    "timestamp": "timestamptz", "datetime": "timestamptz", "date": "date",
    "json": "jsonb", "object": "jsonb", "array": "jsonb",
}

# pen Connector.kind has no etl/sync; fold them into seam.
_CONNECTOR_KIND = {
    "seam": "seam", "webhook": "webhook", "fan_out": "fan_out",
    "middleware": "middleware", "shared_service": "shared_service",
    "auth": "auth", "etl": "seam", "sync": "seam",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_") or "x"


def _pg_type(field_type: str) -> str:
    return _PG_TYPE.get((field_type or "").lower(), "text")


def system_map_to_pen(system_map: SystemMap, project_name: str = "System Map") -> PenFile:
    pen = PenFile(project=ProjectMeta(name=project_name))

    systems = {s.id: s for s in system_map.systems}
    objects = {o.id: o for o in system_map.data_objects}
    fields_by_object: dict[str, list] = {}
    for f in system_map.data_fields:
        fields_by_object.setdefault(f.object_id, []).append(f)

    # ── Objects → ERD entities (+ fields → attributes) ───────────────────────
    entity_id_for_object: dict[str, str] = {}
    attr_id_for_field: dict[str, str] = {}
    pk_attr_for_object: dict[str, str] = {}
    entities: list[Entity] = []

    for obj in system_map.data_objects:
        ent_id = f"ent_{_slug(obj.name)}"
        entity_id_for_object[obj.id] = ent_id
        norm = _normalize(obj.name)
        attrs: list[Attribute] = []
        pk_id: str | None = None
        for fld in fields_by_object.get(obj.id, []):
            attr_id = f"attr_{_slug(obj.name)}_{_slug(fld.name)}"
            attr_id_for_field[fld.id] = attr_id
            # Primary key: the object's own identity field (id / <object>_id).
            base = _referenced_base(fld.name)
            is_pk = fld.name.lower() == "id" or (base is not None and base == norm)
            attrs.append(Attribute(
                id=attr_id, name=fld.name, pg_type=_pg_type(fld.type),
                key_role="primary" if is_pk else "none",
                nullable=fld.nullable, review_status="accepted",
            ))
            if is_pk and pk_id is None:
                pk_id = attr_id
        if pk_id is None:
            pk_id = f"attr_{_slug(obj.name)}_id"
            attrs.insert(0, Attribute(id=pk_id, name="id", pg_type="uuid",
                                      key_role="primary", nullable=False, review_status="accepted"))
        pk_attr_for_object[obj.id] = pk_id
        owner = systems.get(obj.system_id)
        entities.append(Entity(
            id=ent_id, name=_slug(obj.name), display_name=obj.name,
            domain=(owner.name if owner else obj.system_id),
            attributes=attrs, review_status="accepted",
        ))
    pen.erd.entities = entities

    # ── Shared-identifier references → ERD relationships ──────────────────────
    by_norm_name = {}
    for obj in system_map.data_objects:
        by_norm_name.setdefault(_normalize(obj.name), obj)
    relationships: list[Relationship] = []
    for obj in system_map.data_objects:
        for fld in fields_by_object.get(obj.id, []):
            base = _referenced_base(fld.name)
            if not base:
                continue
            target = by_norm_name.get(base)
            if target is None or target.id == obj.id:
                continue  # not a reference to another object
            # Mark the referencing attribute as a foreign key.
            fk_attr_id = attr_id_for_field.get(fld.id)
            for a in (e for e in entities if e.id == entity_id_for_object[obj.id]):
                for attr in a.attributes:
                    if attr.id == fk_attr_id and attr.key_role == "none":
                        attr.key_role = "foreign"
            relationships.append(Relationship(
                id=f"rel_{_slug(obj.name)}_{_slug(fld.name)}",
                name=f"references {target.name}",
                from_=RelationshipEndpoint(entity_id=entity_id_for_object[obj.id], attribute_id=fk_attr_id),
                to=RelationshipEndpoint(entity_id=entity_id_for_object[target.id], attribute_id=pk_attr_for_object[target.id]),
                cardinality=Cardinality(from_min=0, from_max="many", to_min=0 if fld.nullable else 1, to_max=1),
                review_status="accepted",
            ))
    pen.erd.relationships = relationships

    # ── Connectors (existing + detected seams) → pen connectors ──────────────
    def _to_pen_connector(c: SMConnector) -> Connector:
        from_name = systems[c.from_system].name if c.from_system in systems else (c.from_system or "")
        to_names = [systems[s].name if s in systems else s for s in c.to_systems]
        return Connector(
            id=c.id, name=c.name, kind=_CONNECTOR_KIND.get(c.kind, "seam"),
            trigger=c.trigger, effect=c.effect,
            from_context=from_name or None, to_contexts=to_names,
            contract=c.contract, enforced_at=list(c.enforced_at),
            spec_source=c.spec_source,
            status="wired" if c.status == "wired" else "deferred",
            review_status=c.review_status,
        )

    detected = detect_cross_system_seams(system_map)
    pen.dfd.connectors = [_to_pen_connector(c) for c in (list(system_map.connectors) + detected)]

    # ── Business rules → pen business rules with grounding status ─────────────
    grounding = {g.rule_id: g for g in ground_business_rules(system_map)}
    pen_rules: list[BusinessRule] = []
    for rule in system_map.business_rules:
        g = grounding.get(rule.id)
        entity_id = entity_id_for_object.get(rule.scope.id) if rule.scope.kind == "object" else None
        status = rule.status
        verified_by = None
        if g is not None:
            if g.classification == "cross_system_grounded":
                status, verified_by = "enforced", f"grounding: {g.detail}"
            elif g.classification == "cross_system_gap":
                status, verified_by = "gap", f"grounding: {g.detail}"
            elif g.classification == "unverifiable":
                status, verified_by = "deferred", f"grounding: {g.detail}"
            else:  # single_system — keep the rule's own status
                verified_by = f"grounding: {g.detail}"
        pen_rules.append(BusinessRule(
            id=rule.id, entity_id=entity_id, title=rule.title, statement=rule.statement,
            category=rule.category, condition=rule.condition, enforced_at=list(rule.enforced_at),
            spec_source=rule.spec_source, verified_by=verified_by,
            severity=rule.severity, status=status, review_status=rule.review_status,
        ))
    pen.dfd.business_rules = pen_rules

    return pen
