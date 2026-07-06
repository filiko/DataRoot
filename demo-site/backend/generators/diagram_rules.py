"""
diagram_rules — structural rule engine for ERD + DFD diagrams.

See diagram_rules.md (sibling file) for the authoritative rule catalog.
Each rule has a stable id (e.g. "DFD-01") and one detector function here.

Public entry points
-------------------
- detect_violations(pen)        → list[RuleViolation]
- regenerate_derived_dfd(pen)   → list[WarningEntry]   (mutates pen.dfd)
- apply_rules_gate(pen)         → PenFile              (mutates pen)

apply_rules_gate is the single function callers should use at ingest time
and on every patch. It:
  1) calls propagate_erd_to_dfd  (rebuild derived DFD from ERD)
  2) detects violations
  3) applies safe auto-regeneration (delete autogen orphans only)
  4) re-detects, converts remaining violations to WarningEntry,
     stores them in pen.review.warnings (replacing prior rule warnings)
  5) NEVER mutates pen.sources or pen.erd.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from models.pen import (
    PenFile, Entity, Relationship, DataStore, Process, ExternalEntity,
    DataFlow, WarningEntry,
)
from generators.sync_engine import (
    validate, propagate_erd_to_dfd,
    FLOW_MISSING_FROM_NODE, FLOW_MISSING_TO_NODE,
    FLOW_MANUAL_STORE_TO_STORE, DIRECT_M2M_NO_JOIN,
)


# ─────────────────────────────────────────────
# Violation model
# ─────────────────────────────────────────────

NodeKind = Literal[
    "entity", "relationship", "attribute",
    "data_store", "process", "external_entity", "data_flow",
    "global",
]


@dataclass
class RuleViolation:
    rule_id: str
    severity: Literal["blocking", "warning"]
    node_kind: NodeKind
    node_id: str | None
    node_name: str | None
    message: str
    auto_regenerable: bool
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "node_kind": self.node_kind,
            "node_id": self.node_id,
            "node_name": self.node_name,
            "message": self.message,
            "auto_regenerable": self.auto_regenerable,
            "context": self.context,
        }

    def to_warning_entry(self) -> WarningEntry:
        return WarningEntry(
            rule_id=self.rule_id,
            severity=self.severity,
            node_kind=self.node_kind,
            node_id=self.node_id,
            node_name=self.node_name,
            message=self.message,
            context=self.context,
        )


# ─────────────────────────────────────────────
# Graph helpers
# ─────────────────────────────────────────────

@dataclass
class _GraphIndex:
    """Pre-computed counts so each detector is O(N) instead of O(N*M)."""
    in_degree: dict[str, int] = field(default_factory=dict)
    out_degree: dict[str, int] = field(default_factory=dict)
    entity_rel_count: dict[str, int] = field(default_factory=dict)

    @classmethod
    def build(cls, pen: PenFile) -> "_GraphIndex":
        idx = cls()
        for f in pen.dfd.data_flows:
            idx.in_degree[f.to] = idx.in_degree.get(f.to, 0) + 1
            idx.out_degree[f.from_] = idx.out_degree.get(f.from_, 0) + 1
        for r in pen.erd.relationships:
            idx.entity_rel_count[r.from_.entity_id] = (
                idx.entity_rel_count.get(r.from_.entity_id, 0) + 1
            )
            idx.entity_rel_count[r.to.entity_id] = (
                idx.entity_rel_count.get(r.to.entity_id, 0) + 1
            )
        return idx

    def degree(self, node_id: str) -> tuple[int, int]:
        return self.in_degree.get(node_id, 0), self.out_degree.get(node_id, 0)

    def rel_count(self, entity_id: str) -> int:
        return self.entity_rel_count.get(entity_id, 0)


# ─────────────────────────────────────────────
# Detectors — one per rule
# ─────────────────────────────────────────────

def _detect_erd_01_orphan_entity(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for ent in pen.erd.entities:
        if ent.review_status == "rejected":
            continue
        if idx.rel_count(ent.id) == 0:
            out.append(RuleViolation(
                rule_id="ERD-01",
                severity="warning",
                node_kind="entity",
                node_id=ent.id,
                node_name=ent.display_name or ent.name,
                message=(
                    f"Entity '{ent.display_name or ent.name}' has no relationships. "
                    f"It will not appear in the DFD until you connect it or mark it rejected."
                ),
                auto_regenerable=False,
                context={"entity_id": ent.id},
            ))
    return out


def _detect_erd_03_self_m2m(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    ent_index = {e.id: e for e in pen.erd.entities}
    for rel in pen.erd.relationships:
        if rel.review_status == "rejected":
            continue
        if rel.from_.entity_id != rel.to.entity_id:
            continue
        if rel.cardinality.from_max != "many" or rel.cardinality.to_max != "many":
            continue
        ent = ent_index.get(rel.from_.entity_id)
        name = ent.display_name if ent else rel.from_.entity_id
        out.append(RuleViolation(
            rule_id="ERD-03",
            severity="warning",
            node_kind="relationship",
            node_id=rel.id,
            node_name=rel.name,
            message=(
                f"Self-referential many-to-many on '{name}' has no join entity. "
                f"This is rarely intended."
            ),
            auto_regenerable=False,
            context={"entity_id": rel.from_.entity_id, "rel_id": rel.id},
        ))
    return out


def _detect_erd_04_orphan_fk(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    referenced_attrs: set[str] = set()
    for rel in pen.erd.relationships:
        referenced_attrs.add(rel.from_.attribute_id)
        referenced_attrs.add(rel.to.attribute_id)

    for ent in pen.erd.entities:
        if ent.review_status == "rejected":
            continue
        for attr in ent.attributes:
            if attr.key_role == "foreign" and attr.id not in referenced_attrs:
                out.append(RuleViolation(
                    rule_id="ERD-04",
                    severity="warning",
                    node_kind="attribute",
                    node_id=attr.id,
                    node_name=attr.name,
                    message=(
                        f"Attribute '{ent.name}.{attr.name}' is marked foreign key "
                        f"but no relationship references it."
                    ),
                    auto_regenerable=False,
                    context={"entity_id": ent.id, "attr_id": attr.id},
                ))
    return out


def _detect_erd_05_index_integrity(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for ent in pen.erd.entities:
        if ent.review_status == "rejected":
            continue
        live_attrs = {a.id for a in ent.attributes if a.review_status != "rejected"}
        for index in ent.indexes:
            dangling = [aid for aid in index.attribute_ids if aid not in live_attrs]
            if dangling:
                out.append(RuleViolation(
                    rule_id="ERD-05",
                    severity="warning",
                    node_kind="entity",
                    node_id=ent.id,
                    node_name=ent.display_name or ent.name,
                    message=(
                        f"Index '{index.name}' on '{ent.name}' references a missing or "
                        f"rejected column. It will be skipped in SQL export."
                    ),
                    auto_regenerable=False,
                    context={"entity_id": ent.id, "index_id": index.id,
                             "dangling_attribute_ids": dangling},
                ))
    return out


def _detect_dfd_01_floating_store(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []

    for store in pen.dfd.data_stores:
        in_d, out_d = idx.degree(store.id)
        if in_d + out_d > 0:
            continue

        # Decide auto-regeneration: only if autogen AND mapped entity has no rels
        auto = False
        if not store.user_modified:
            if store.mapped_erd_entity is None:
                auto = True
            else:
                auto = idx.rel_count(store.mapped_erd_entity) == 0

        out.append(RuleViolation(
            rule_id="DFD-01",
            severity="warning",
            node_kind="data_store",
            node_id=store.id,
            node_name=store.name,
            message=(
                f"Data store '{store.name}' has no incoming or outgoing flows."
            ),
            auto_regenerable=auto,
            context={"store_id": store.id, "user_modified": store.user_modified},
        ))
    return out


def _detect_dfd_02_black_hole(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for proc in pen.dfd.processes:
        in_d, out_d = idx.degree(proc.id)
        if in_d > 0 and out_d == 0:
            auto = (
                not proc.user_modified
                and proc.mapped_relationship_id is not None
            )
            out.append(RuleViolation(
                rule_id="DFD-02",
                severity="warning",
                node_kind="process",
                node_id=proc.id,
                node_name=proc.name,
                message=(
                    f"Process '{proc.name}' has inputs but no outputs (black hole)."
                ),
                auto_regenerable=auto,
                context={"process_id": proc.id, "in_degree": in_d},
            ))
    return out


def _detect_dfd_03_miracle(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for proc in pen.dfd.processes:
        in_d, out_d = idx.degree(proc.id)
        if out_d > 0 and in_d == 0:
            auto = (
                not proc.user_modified
                and proc.mapped_relationship_id is not None
            )
            out.append(RuleViolation(
                rule_id="DFD-03",
                severity="warning",
                node_kind="process",
                node_id=proc.id,
                node_name=proc.name,
                message=(
                    f"Process '{proc.name}' has outputs but no inputs (miracle)."
                ),
                auto_regenerable=auto,
                context={"process_id": proc.id, "out_degree": out_d},
            ))
    return out


def _detect_dfd_04_grey_hole(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    """Heuristic: outputs reference attribute ids none of the inputs provide."""
    out: list[RuleViolation] = []
    flows = pen.dfd.data_flows

    # Skip the expensive scan for processes we already know are black/miracle.
    candidates = [
        p for p in pen.dfd.processes
        if idx.in_degree.get(p.id, 0) > 0 and idx.out_degree.get(p.id, 0) > 0
    ]
    if not candidates:
        return out

    for proc in candidates:
        in_flows = [f for f in flows if f.to == proc.id]
        out_flows = [f for f in flows if f.from_ == proc.id]
        if not in_flows or not out_flows:
            continue  # covered by DFD-02/03

        in_attrs: set[str] = set()
        for f in in_flows:
            in_attrs.update(f.mapped_erd_attributes)
        out_attrs: set[str] = set()
        for f in out_flows:
            out_attrs.update(f.mapped_erd_attributes)

        # Only flag when both sides actually have attribute mappings
        if not in_attrs or not out_attrs:
            continue
        unsourced = out_attrs - in_attrs
        if not unsourced:
            continue

        out.append(RuleViolation(
            rule_id="DFD-04",
            severity="warning",
            node_kind="process",
            node_id=proc.id,
            node_name=proc.name,
            message=(
                f"Process '{proc.name}' produces data the inputs cannot supply "
                f"({len(unsourced)} unsourced attribute(s))."
            ),
            auto_regenerable=False,
            context={"process_id": proc.id, "unsourced_attr_ids": sorted(unsourced)},
        ))
    return out


def _detect_dfd_05_disconnected_process(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for proc in pen.dfd.processes:
        in_d, out_d = idx.degree(proc.id)
        if in_d == 0 and out_d == 0:
            auto = (
                not proc.user_modified
                and proc.mapped_relationship_id is None
            )
            out.append(RuleViolation(
                rule_id="DFD-05",
                severity="warning",
                node_kind="process",
                node_id=proc.id,
                node_name=proc.name,
                message=f"Process '{proc.name}' is disconnected (no flows).",
                auto_regenerable=auto,
                context={"process_id": proc.id},
            ))
    return out


def _detect_dfd_06_floating_external(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for ext in pen.dfd.external_entities:
        in_d, out_d = idx.degree(ext.id)
        if in_d + out_d > 0:
            continue
        auto = ext.source == "auto"
        out.append(RuleViolation(
            rule_id="DFD-06",
            severity="warning",
            node_kind="external_entity",
            node_id=ext.id,
            node_name=ext.name,
            message=f"External entity '{ext.name}' has no flows.",
            auto_regenerable=auto,
            context={"external_id": ext.id, "source": ext.source},
        ))
    return out


def _detect_dfd_08_external_to_external(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    ext_ids = {e.id for e in pen.dfd.external_entities}
    for f in pen.dfd.data_flows:
        if f.from_ in ext_ids and f.to in ext_ids:
            out.append(RuleViolation(
                rule_id="DFD-08",
                severity="warning",
                node_kind="data_flow",
                node_id=f.id,
                node_name=f.data_name,
                message=(
                    f"Data flow '{f.data_name or f.id}' connects two external "
                    f"entities directly. Flows must cross the system boundary "
                    f"through a process."
                ),
                auto_regenerable=False,
                context={"from": f.from_, "to": f.to},
            ))
    return out


def _detect_dfd_10_read_only_store(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for store in pen.dfd.data_stores:
        in_d, out_d = idx.degree(store.id)
        if in_d == 0 and out_d > 0:
            out.append(RuleViolation(
                rule_id="DFD-10",
                severity="warning",
                node_kind="data_store",
                node_id=store.id,
                node_name=store.name,
                message=(
                    f"Data store '{store.name}' is read-only — nothing writes to it."
                ),
                auto_regenerable=False,
                context={"store_id": store.id},
            ))
    return out


def _detect_dfd_11_write_only_store(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    out: list[RuleViolation] = []
    for store in pen.dfd.data_stores:
        in_d, out_d = idx.degree(store.id)
        if out_d == 0 and in_d > 0:
            out.append(RuleViolation(
                rule_id="DFD-11",
                severity="warning",
                node_kind="data_store",
                node_id=store.id,
                node_name=store.name,
                message=(
                    f"Data store '{store.name}' is write-only — nothing reads from it."
                ),
                auto_regenerable=False,
                context={"store_id": store.id},
            ))
    return out


# Conflict id → rule_id passthrough for sync_engine-detected rules
_SYNC_ENGINE_RULE_MAP = {
    DIRECT_M2M_NO_JOIN: "ERD-02",
    FLOW_MANUAL_STORE_TO_STORE: "DFD-07",
    FLOW_MISSING_FROM_NODE: "DFD-09",
    FLOW_MISSING_TO_NODE: "DFD-09",
}


def _detect_from_sync_engine(pen: PenFile, idx: _GraphIndex) -> list[RuleViolation]:
    """Wrap conflicts already produced by sync_engine.validate()."""
    out: list[RuleViolation] = []
    for c in validate(pen):
        rule_id = _SYNC_ENGINE_RULE_MAP.get(c.type)
        if rule_id is None:
            continue
        # DFD-09 (broken flow endpoint) is auto-regenerable by deletion
        auto = c.type in (FLOW_MISSING_FROM_NODE, FLOW_MISSING_TO_NODE)
        node_kind: NodeKind
        if c.type in (FLOW_MISSING_FROM_NODE, FLOW_MISSING_TO_NODE,
                      FLOW_MANUAL_STORE_TO_STORE):
            node_kind = "data_flow"
        else:
            node_kind = "relationship"
        out.append(RuleViolation(
            rule_id=rule_id,
            severity=c.severity,
            node_kind=node_kind,
            node_id=c.object_id,
            node_name=None,
            message=c.message,
            auto_regenerable=auto,
            context=c.context,
        ))
    return out


# ─────────────────────────────────────────────
# Top-level detection
# ─────────────────────────────────────────────

_ALL_DETECTORS = [
    _detect_erd_01_orphan_entity,
    _detect_erd_03_self_m2m,
    _detect_erd_04_orphan_fk,
    _detect_erd_05_index_integrity,
    _detect_dfd_01_floating_store,
    _detect_dfd_02_black_hole,
    _detect_dfd_03_miracle,
    _detect_dfd_04_grey_hole,
    _detect_dfd_05_disconnected_process,
    _detect_dfd_06_floating_external,
    _detect_dfd_08_external_to_external,
    _detect_dfd_10_read_only_store,
    _detect_dfd_11_write_only_store,
    _detect_from_sync_engine,
]


def detect_violations(pen: PenFile) -> list[RuleViolation]:
    idx = _GraphIndex.build(pen)
    out: list[RuleViolation] = []
    for d in _ALL_DETECTORS:
        out.extend(d(pen, idx))
    return out


# ─────────────────────────────────────────────
# Auto-regeneration
# ─────────────────────────────────────────────

def _apply_auto_fix(pen: PenFile, v: RuleViolation) -> bool:
    """Apply the safe fix for a single violation. Returns True if anything changed.

    Only DFD-side overlay objects are touched; ERD and sources are never mutated.
    """
    if not v.auto_regenerable:
        return False

    rule = v.rule_id

    if rule == "DFD-01":  # floating store — remove
        before = len(pen.dfd.data_stores)
        pen.dfd.data_stores = [s for s in pen.dfd.data_stores if s.id != v.node_id]
        return len(pen.dfd.data_stores) < before

    if rule in ("DFD-02", "DFD-03", "DFD-05"):  # process pathologies — remove process + its flows
        before = len(pen.dfd.processes)
        pen.dfd.processes = [p for p in pen.dfd.processes if p.id != v.node_id]
        pen.dfd.data_flows = [
            f for f in pen.dfd.data_flows
            if f.from_ != v.node_id and f.to != v.node_id
        ]
        return len(pen.dfd.processes) < before

    if rule == "DFD-06":  # floating external — remove
        before = len(pen.dfd.external_entities)
        pen.dfd.external_entities = [
            e for e in pen.dfd.external_entities if e.id != v.node_id
        ]
        return len(pen.dfd.external_entities) < before

    if rule == "DFD-09":  # broken flow endpoint — drop the dangling flow
        before = len(pen.dfd.data_flows)
        pen.dfd.data_flows = [f for f in pen.dfd.data_flows if f.id != v.node_id]
        return len(pen.dfd.data_flows) < before

    return False


def regenerate_derived_dfd(pen: PenFile) -> list[WarningEntry]:
    """
    Rebuild the derived DFD from ERD, then prune any DFD-side anti-patterns the
    engine can safely fix. Convert remaining issues to WarningEntry records and
    return them.

    The pen is mutated in place. ERD and sources are never touched.
    """
    # 1. Rebuild derived DFD (already preserves user_modified objects)
    propagate_erd_to_dfd(pen)

    # 2. Single auto-fix pass. Detection is O(N*M) over the diagram graph;
    # one pass converges in practice (subsequent issues only arise from
    # cascade deletions, which we accept as warnings the user can address
    # next save). A second pass doubles work without buying much fidelity.
    violations = detect_violations(pen)
    fixed_any = False
    for v in violations:
        if _apply_auto_fix(pen, v):
            fixed_any = True

    # 3. Re-detect only if we actually changed the graph; otherwise reuse
    # the violations we already have.
    final = detect_violations(pen) if fixed_any else violations
    return [v.to_warning_entry() for v in final]


def apply_rules_gate(pen: PenFile) -> PenFile:
    """
    Single entry point used at ingest time and on every patch.

    Side-effects: regenerates derived DFD, replaces pen.review.warnings with
    fresh structured rule warnings (legacy non-rule warnings are dropped on
    purpose — they are migrated by the WarningEntry validator on first load).
    """
    warnings = regenerate_derived_dfd(pen)
    dismissed = set(getattr(pen.review, "dismissed_warnings", []))
    pen.review.warnings = [
        warning for warning in warnings
        if _warning_key(warning) not in dismissed
    ]
    return pen


def _warning_key(warning: WarningEntry) -> str:
    node_ref = warning.node_id or warning.node_name or warning.message
    return f"{warning.rule_id}:{warning.node_kind}:{node_ref}"
