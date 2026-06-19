"""V2 — cross-system seam detection + business-rule system grounding.

The linchpin of cross-system verification (docs/business-rule-verification.md §6):
a rule like "an order must reference a valid device" is only verifiable when the
two objects live in different systems *and* a connector bridges them. This module

  1. detects cross-system **seams** from shared identifiers (e.g. a field
     `Order.device_id` in SaaS C that names the `Device` object in SaaS B), and
  2. **grounds** each business rule — single-system, cross-system-grounded (a
     connector links the systems), cross-system-gap (none does), or unverifiable.

Per decision #5, detected seams are proposed at `review_status="needs_review"` —
never auto-asserted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from dataroot.systemmap.ids import stable_id
from dataroot.systemmap.models import (
    Connector,
    DataField,
    DataObject,
    Evidence,
    SystemMap,
)

# A field that names a foreign reference: device_id, customer_ref, order_key, …
# A separator before the suffix is REQUIRED so identifier-ish words like "uuid",
# "grid", "valid", "paid" do NOT parse as "<base>_id". "uuid" is dropped from the
# suffix set entirely — a bare uuid field identifies its own row, it is not a
# foreign reference to another object.
_REF_SUFFIX = re.compile(
    r"^(?P<base>[a-z0-9]+(?:[_\s][a-z0-9]+)*)[_\s](?P<suffix>id|ids|ref|refs|key|fk)$",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    """Lowercase, strip non-alphanumerics, naive singularization for name matching."""
    n = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    if n.endswith("ies"):
        n = n[:-3] + "y"
    elif n.endswith("ses"):
        n = n[:-2]
    elif n.endswith("s") and not n.endswith("ss"):
        n = n[:-1]
    return n


def _referenced_base(field_name: str) -> str | None:
    """For `device_id` → `device`; None if the field isn't a foreign-reference name."""
    m = _REF_SUFFIX.match(field_name or "")
    if not m:
        return None
    base = _normalize(m.group("base"))
    return base or None


def _connector_covers(conn: Connector, from_system: str, to_system: str, marker: str) -> bool:
    """True if an existing connector already represents this seam."""
    links = conn.from_system == from_system and to_system in conn.to_systems
    links_sym = conn.from_system == to_system and from_system in conn.to_systems
    if not (links or links_sym):
        return False
    contract = (conn.contract or "").lower()
    # Only suppress when the connector's contract actually names this field. A
    # blank or unrelated contract must NOT swallow a real, distinct seam.
    return bool(contract) and marker.lower() in contract


def detect_cross_system_seams(system_map: SystemMap) -> list[Connector]:
    """Detect shared-identifier seams between objects in DIFFERENT systems and
    return proposed seam connectors (needs_review), excluding seams an existing
    connector already covers."""
    objects = {o.id: o for o in system_map.data_objects}
    by_norm_name: dict[str, DataObject] = {}
    for o in system_map.data_objects:
        by_norm_name.setdefault(_normalize(o.name), o)
    fields_by_object: dict[str, list[DataField]] = {}
    for f in system_map.data_fields:
        fields_by_object.setdefault(f.object_id, []).append(f)
    systems = {s.id: s for s in system_map.systems}

    proposed: list[Connector] = []
    seen_pairs: set[tuple[str, str, str]] = set()

    for obj in system_map.data_objects:
        for fld in fields_by_object.get(obj.id, []):
            base = _referenced_base(fld.name)
            if not base:
                continue
            target = by_norm_name.get(base)
            if target is None or target.id == obj.id:
                continue
            if target.system_id == obj.system_id:
                continue  # same-system reference, not a cross-system seam
            key = (obj.id, fld.name, target.id)
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            marker = fld.name
            if any(_connector_covers(c, obj.system_id, target.system_id, marker)
                   for c in system_map.connectors):
                continue  # already represented by a hand-authored/existing connector

            from_sys = systems.get(obj.system_id)
            to_sys = systems.get(target.system_id)
            src_kind = fld.evidence[0].kind if fld.evidence else "manual"
            ev = Evidence(
                id=stable_id("ev_seam", fld.id, target.id),
                kind=src_kind,
                locator=f"seam://{obj.name}.{fld.name}->{target.name}",
                excerpt=f"'{obj.name}.{fld.name}' names the '{target.name}' object in another system.",
                confidence=0.75,
            )
            proposed.append(Connector(
                id=stable_id("connector_seam", fld.id, target.id),
                name=f"{obj.name}.{fld.name} → {target.name}",
                kind="seam",
                trigger=f"{(from_sys.name if from_sys else obj.system_id)} '{obj.name}' carries {fld.name}",
                effect=f"can be joined to '{target.name}' in {(to_sys.name if to_sys else target.system_id)}",
                from_system=obj.system_id,
                to_systems=[target.system_id],
                contract=f"{obj.name}.{fld.name} -> {target.name}",
                evidence=[ev],
                confidence=0.75,
                review_status="needs_review",
                status="wired",
            ))
    return proposed


# ── Business-rule system grounding ────────────────────────────────────────────

GroundingClass = Literal[
    "single_system",
    "cross_system_grounded",
    "cross_system_gap",
    "unverifiable",
]


@dataclass
class RuleGrounding:
    rule_id: str
    classification: GroundingClass
    systems: list[str] = field(default_factory=list)
    connector_id: str | None = None
    detail: str = ""


def _systems_linked(system_map: SystemMap, all_connectors: list[Connector], a: str, b: str) -> str | None:
    """Return a connector id that links systems a↔b, or None."""
    for c in all_connectors:
        if (c.from_system == a and b in c.to_systems) or (c.from_system == b and a in c.to_systems):
            return c.id
    return None


def ground_business_rules(system_map: SystemMap) -> list[RuleGrounding]:
    """Classify each business rule against the System Map. Cross-system rules
    (the rule's scoped object names another object in a different system) are
    grounded only when a connector links the two systems."""
    objects = {o.id: o for o in system_map.data_objects}
    surfaces = {s.id: s for s in system_map.access_surfaces}
    system_has_surface = {s.system_id for s in system_map.access_surfaces}
    # Existing connectors + freshly detected seams form the connectivity graph.
    all_connectors = list(system_map.connectors) + detect_cross_system_seams(system_map)

    out: list[RuleGrounding] = []
    for rule in system_map.business_rules:
        owning_system = _owning_system(rule.scope, objects, surfaces)
        if owning_system is None:
            out.append(RuleGrounding(rule.id, "unverifiable", detail="rule scope is not tied to a system"))
            continue

        # Cross-system iff the statement names another object in a different system.
        target = _other_system_object_in_statement(rule.statement, owning_system, objects)
        if target is None:
            out.append(RuleGrounding(rule.id, "single_system", systems=[owning_system],
                                     detail="governs data within one system"))
            continue

        other_system = target.system_id
        if other_system not in system_has_surface and not any(
            o.system_id == other_system for o in system_map.data_objects
        ):
            out.append(RuleGrounding(rule.id, "unverifiable", systems=[owning_system, other_system],
                                     detail=f"the '{target.name}' system is referenced but not mapped"))
            continue

        conn_id = _systems_linked(system_map, all_connectors, owning_system, other_system)
        if conn_id:
            out.append(RuleGrounding(rule.id, "cross_system_grounded", systems=[owning_system, other_system],
                                     connector_id=conn_id,
                                     detail=f"cross-system reference to '{target.name}' is bridged by a connector"))
        else:
            out.append(RuleGrounding(rule.id, "cross_system_gap", systems=[owning_system, other_system],
                                     detail=f"references '{target.name}' in another system, but no connector links them"))
    return out


def _owning_system(scope, objects: dict, surfaces: dict) -> str | None:
    if scope.kind == "system":
        return scope.id
    if scope.kind == "object":
        obj = objects.get(scope.id)
        return obj.system_id if obj else None
    if scope.kind == "surface":
        surf = surfaces.get(scope.id)
        return surf.system_id if surf else None
    return None


def _other_system_object_in_statement(statement: str, owning_system: str, objects: dict) -> DataObject | None:
    text = (statement or "").lower()
    for obj in objects.values():
        if obj.system_id == owning_system:
            continue
        norm = _normalize(obj.name)
        if norm and re.search(rf"\b{re.escape(obj.name.lower())}s?\b", text):
            return obj
    return None
