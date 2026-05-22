"""
sync_engine — ERD→DFD propagation and conflict detection.

validate(pen)              → list[Conflict]   (empty = safe to save)
propagate_erd_to_dfd(pen)  → PenFile          (mutates pen in place, returns pen)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from models.pen import PenFile
from generators.dfd_builder import build_dfd_from_erd, _auto_layout_dfd


# ─────────────────────────────────────────────
# Conflict model
# ─────────────────────────────────────────────

# Conflict type constants
STORE_MAPS_MISSING_ENTITY    = "STORE_MAPS_MISSING_ENTITY"
FLOW_MISSING_FROM_NODE       = "FLOW_MISSING_FROM_NODE"
FLOW_MISSING_TO_NODE         = "FLOW_MISSING_TO_NODE"
PROCESS_ORPHANED_RELATIONSHIP = "PROCESS_ORPHANED_RELATIONSHIP"
FLOW_ORPHANED_RELATIONSHIP   = "FLOW_ORPHANED_RELATIONSHIP"
FLOW_MANUAL_STORE_TO_STORE   = "FLOW_MANUAL_STORE_TO_STORE"
DIRECT_M2M_NO_JOIN           = "DIRECT_M2M_NO_JOIN"


@dataclass
class Conflict:
    type: str
    severity: Literal["blocking", "warning"]
    message: str
    object_id: str
    context: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "message": self.message,
            "object_id": self.object_id,
            "context": self.context,
        }


# ─────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────

def validate(pen: PenFile) -> list[Conflict]:
    """
    Run all conflict checks on the PenFile.
    Returns empty list if it's safe to save.
    """
    conflicts: list[Conflict] = []
    dfd = pen.dfd

    # Build node ID sets for DFD graph
    all_node_ids: set[str] = set()
    all_node_ids.update(e.id for e in dfd.external_entities)
    all_node_ids.update(p.id for p in dfd.processes)
    all_node_ids.update(s.id for s in dfd.data_stores)

    # ERD index
    erd_entity_ids = {e.id for e in pen.erd.entities}
    erd_rel_ids = {r.id for r in pen.erd.relationships}
    store_ids = {s.id for s in dfd.data_stores}

    # ── STORE_MAPS_MISSING_ENTITY (blocking) ──────────────────────────────────
    for store in dfd.data_stores:
        if store.mapped_erd_entity is not None and store.mapped_erd_entity not in erd_entity_ids:
            if store.user_modified:
                conflicts.append(Conflict(
                    type=STORE_MAPS_MISSING_ENTITY,
                    severity="blocking",
                    message=(
                        f"DataStore '{store.name}' references entity "
                        f"'{store.mapped_erd_entity}' which no longer exists in the ERD."
                    ),
                    object_id=store.id,
                    context={"missing_entity_id": store.mapped_erd_entity},
                ))
            # auto-gen orphans are silently dropped by build_dfd_from_erd; not flagged here

    # ── FLOW_MISSING_FROM_NODE / FLOW_MISSING_TO_NODE (blocking) ─────────────
    for flow in dfd.data_flows:
        if flow.from_ not in all_node_ids:
            conflicts.append(Conflict(
                type=FLOW_MISSING_FROM_NODE,
                severity="blocking",
                message=(
                    f"DataFlow '{flow.id}' references missing 'from' node '{flow.from_}'."
                ),
                object_id=flow.id,
                context={"missing_node_id": flow.from_},
            ))
        if flow.to not in all_node_ids:
            conflicts.append(Conflict(
                type=FLOW_MISSING_TO_NODE,
                severity="blocking",
                message=(
                    f"DataFlow '{flow.id}' references missing 'to' node '{flow.to}'."
                ),
                object_id=flow.id,
                context={"missing_node_id": flow.to},
            ))

    # ── PROCESS_ORPHANED_RELATIONSHIP (warning) ───────────────────────────────
    for proc in dfd.processes:
        if (
            proc.mapped_relationship_id is not None
            and proc.mapped_relationship_id not in erd_rel_ids
            and proc.user_modified
        ):
            conflicts.append(Conflict(
                type=PROCESS_ORPHANED_RELATIONSHIP,
                severity="warning",
                message=(
                    f"Process '{proc.name}' references deleted relationship "
                    f"'{proc.mapped_relationship_id}'."
                ),
                object_id=proc.id,
                context={"missing_rel_id": proc.mapped_relationship_id},
            ))

    # ── FLOW_ORPHANED_RELATIONSHIP (warning) ──────────────────────────────────
    for flow in dfd.data_flows:
        if (
            flow.mapped_relationship_id is not None
            and flow.mapped_relationship_id not in erd_rel_ids
        ):
            conflicts.append(Conflict(
                type=FLOW_ORPHANED_RELATIONSHIP,
                severity="warning",
                message=(
                    f"DataFlow '{flow.id}' references deleted relationship "
                    f"'{flow.mapped_relationship_id}'."
                ),
                object_id=flow.id,
                context={"missing_rel_id": flow.mapped_relationship_id},
            ))

    # ── FLOW_MANUAL_STORE_TO_STORE (warning) ──────────────────────────────────
    for flow in dfd.data_flows:
        if (
            flow.mapped_relationship_id is None
            and flow.from_ in store_ids
            and flow.to in store_ids
        ):
            conflicts.append(Conflict(
                type=FLOW_MANUAL_STORE_TO_STORE,
                severity="warning",
                message=(
                    f"DataFlow '{flow.id}' connects two DataStores directly "
                    f"(no Process in between). This is unusual DFD topology."
                ),
                object_id=flow.id,
                context={"from_store": flow.from_, "to_store": flow.to},
            ))

    # ── DIRECT_M2M_NO_JOIN (blocking — pending or rejected M2M without join) ─────
    # Any M2M relationship must either have a join table entity resolving it,
    # or a proposal (pending/rejected) to create one. Undecided proposals block save.
    unresolved_m2m_proposals: dict[tuple[str, str], str] = {}
    for p in pen.review.proposals:
        if p.proposal_type == "many_to_many_join" and p.status in ("pending", "rejected"):
            from_t = str(p.context.get("from_table", ""))
            to_t = str(p.context.get("to_table", ""))
            if from_t and to_t:
                unresolved_m2m_proposals[tuple(sorted([from_t, to_t]))] = p.status

    if unresolved_m2m_proposals:
        entity_map = {e.id: e for e in pen.erd.entities}
        for rel in pen.erd.relationships:
            if rel.cardinality.from_max != "many" or rel.cardinality.to_max != "many":
                continue
            from_ent = entity_map.get(rel.from_.entity_id)
            to_ent = entity_map.get(rel.to.entity_id)
            if not from_ent or not to_ent:
                continue

            # Only block if no join entity already resolves this pair
            join_exists = any(
                e.id not in (from_ent.id, to_ent.id) and
                any(r2.from_.entity_id == e.id and r2.to.entity_id == from_ent.id
                    for r2 in pen.erd.relationships) and
                any(r2.from_.entity_id == e.id and r2.to.entity_id == to_ent.id
                    for r2 in pen.erd.relationships)
                for e in pen.erd.entities
            )
            if join_exists:
                continue

            pair = tuple(sorted([from_ent.name, to_ent.name]))
            if pair in unresolved_m2m_proposals:
                status_word = "pending" if unresolved_m2m_proposals[pair] == "pending" else "rejected"
                conflicts.append(Conflict(
                    type=DIRECT_M2M_NO_JOIN,
                    severity="blocking",
                    message=(
                        f"The many-to-many relationship between '{from_ent.name}' and "
                        f"'{to_ent.name}' has no join table, and the '{status_word}' "
                        f"proposal has not been resolved. Accept or delete the "
                        f"relationship."
                    ),
                    object_id=rel.id,
                    context={"from_entity": from_ent.name, "to_entity": to_ent.name},
                ))

    return conflicts


# ─────────────────────────────────────────────
# Propagation
# ─────────────────────────────────────────────

def propagate_erd_to_dfd(pen: PenFile) -> PenFile:
    """
    Rebuild pen.dfd from pen.erd, write back dfd_process_id on Relationships,
    and update layout.dfd positions for new nodes.

    Mutates pen in place. Returns pen.
    """
    # 1. Rebuild DFD
    new_dfd = build_dfd_from_erd(pen.erd, existing_dfd=pen.dfd)
    pen.dfd = new_dfd

    # 2. Write-back: set Relationship.dfd_process_id for auto-gen processes
    rel_index = {r.id: r for r in pen.erd.relationships}
    for proc in pen.dfd.processes:
        if proc.mapped_relationship_id is not None:
            rel = rel_index.get(proc.mapped_relationship_id)
            if rel is not None:
                rel.dfd_process_id = proc.id

    # 3. Auto-layout new DFD nodes (preserves existing positions)
    _auto_layout_dfd(pen.dfd, pen.layout)

    return pen
