"""
dfd_builder — generates a DfdModel from an ErdModel.

Rules:
- One DataStore per accepted Entity (matched by mapped_erd_entity == entity.id)
- One Process + two DataFlows per accepted Relationship
- ExternalEntities are never auto-created or auto-wired (user connects them manually)
- user_modified=True stores/processes preserve their name/description on re-build
- Orphaned auto-gen objects (entity deleted) are silently removed
- Orphaned user-modified stores become STORE_MAPS_MISSING_ENTITY blocking conflicts (detected in sync_engine)
"""
from __future__ import annotations

from models.pen import (
    ErdModel, DfdModel, Entity, Relationship,
    DataStore, Process, DataFlow, LayoutNode, Layout,
)


# ─────────────────────────────────────────────
# Name inference
# ─────────────────────────────────────────────

def _find_entity(entities: list[Entity], entity_id: str) -> Entity | None:
    return next((e for e in entities if e.id == entity_id), None)


def infer_process_name(rel: Relationship, entities: list[Entity]) -> str:
    """
    Derive a human-readable Process name from a Relationship.

    If rel.name (verb) is present:  "{verb.rstrip('s').capitalize()} {from_entity.display_name}"
      e.g. verb="places", from="Orders" → "Place Orders"
    Otherwise: "{from_entity.display_name} → {to_entity.display_name}"
    """
    from_entity = _find_entity(entities, rel.from_.entity_id)
    verb = (rel.name or "").strip()
    from_name = from_entity.display_name if from_entity else "Entity"

    if verb:
        return f"{verb.rstrip('s').capitalize()} {from_name}"

    to_entity = _find_entity(entities, rel.to.entity_id)
    to_name = to_entity.display_name if to_entity else "Entity"
    return f"{from_name} → {to_name}"


# ─────────────────────────────────────────────
# Layout helper
# ─────────────────────────────────────────────

def _generated_store_id(entity_id: str) -> str:
    return f"store_{entity_id}"


def _generated_process_id(rel_id: str) -> str:
    return f"proc_{rel_id}"


def _generated_flow_id(rel_id: str, direction: str) -> str:
    return f"flow_{rel_id}_{direction}"


def _find_existing_flow(
    flows: list[DataFlow],
    rel_id: str,
    proc_id: str,
    direction: str,
) -> DataFlow | None:
    rel_flows = [flow for flow in flows if flow.mapped_relationship_id == rel_id]
    if direction == "store_to_process":
        return next((flow for flow in rel_flows if flow.to == proc_id), None)
    if direction == "process_to_store":
        return next((flow for flow in rel_flows if flow.from_ == proc_id), None)
    return None


def _build_relationship_flow(
    existing_flow: DataFlow | None,
    rel: Relationship,
    direction: str,
    from_id: str,
    to_id: str,
    generated_name: str,
) -> DataFlow:
    if existing_flow is not None:
        flow = existing_flow.model_copy()
        flow.from_ = from_id
        flow.to = to_id
        if not flow.user_modified:
            flow.data_name = generated_name
        return flow

    return DataFlow(**{
        "id": _generated_flow_id(rel.id, direction),
        "from": from_id,
        "to": to_id,
        "data_name": generated_name,
        "mapped_relationship_id": rel.id,
    })


def _auto_layout_dfd(dfd: DfdModel, layout: Layout) -> None:
    """
    Assign grid positions for new DFD nodes; preserve existing positions.
    DataStores go in a left column, Processes in a right column.
    Modifies layout.dfd in place.
    """
    existing_ids = {n.id for n in layout.dfd.nodes}
    new_nodes: list[LayoutNode] = list(layout.dfd.nodes)

    # Layout DataStores in left column
    stores = dfd.data_stores
    for i, store in enumerate(stores):
        if store.id not in existing_ids:
            new_nodes.append(LayoutNode(
                id=store.id,
                x=40.0,
                y=40.0 + i * 160.0,
                width=200.0,
                height=80.0,
            ))

    # Layout Processes in right column
    processes = dfd.processes
    for i, proc in enumerate(processes):
        if proc.id not in existing_ids:
            new_nodes.append(LayoutNode(
                id=proc.id,
                x=320.0,
                y=40.0 + i * 160.0,
                width=200.0,
                height=80.0,
            ))

    layout.dfd.nodes = new_nodes


# ─────────────────────────────────────────────
# Core builder
# ─────────────────────────────────────────────

def build_dfd_from_erd(
    erd: ErdModel,
    existing_dfd: DfdModel | None = None,
) -> DfdModel:
    """
    Build or update a DfdModel from an ErdModel.

    - Matching is always by stable ID, never by name.
    - user_modified=True objects have their name/description preserved.
    - Returns a new DfdModel (caller replaces pen.dfd with it).
    """
    existing = existing_dfd or DfdModel()

    # ── Index existing objects by their ERD mapping IDs ──────────────────────
    store_by_entity: dict[str, DataStore] = {
        s.mapped_erd_entity: s
        for s in existing.data_stores
        if s.mapped_erd_entity is not None
    }
    proc_by_rel: dict[str, Process] = {
        p.mapped_relationship_id: p
        for p in existing.processes
        if p.mapped_relationship_id is not None
    }
    # User-created stores (no ERD mapping) — preserve as-is
    user_stores = [s for s in existing.data_stores if s.mapped_erd_entity is None]
    # User-created processes (no ERD mapping) — preserve as-is
    user_procs = [p for p in existing.processes if p.mapped_relationship_id is None]

    # Accepted entity IDs set (for orphan detection)
    accepted_entity_ids = {
        e.id for e in erd.entities if e.review_status != "rejected"
    }

    # ── Step 1 — DataStores (one per accepted Entity) ─────────────────────────
    new_stores: list[DataStore] = []

    for entity in erd.entities:
        if entity.review_status == "rejected":
            continue

        existing_store = store_by_entity.get(entity.id)
        if existing_store is not None:
            if existing_store.user_modified:
                # Preserve name/description; keep the object as-is
                new_stores.append(existing_store)
            else:
                # Sync name to entity display_name
                existing_store.name = entity.display_name
                new_stores.append(existing_store)
        else:
            # Create new DataStore
            new_stores.append(DataStore(
                id=_generated_store_id(entity.id),
                name=entity.display_name,
                mapped_erd_entity=entity.id,
                user_modified=False,
            ))

    # Orphaned user-modified stores (entity was deleted): keep them
    # (sync_engine will flag them as STORE_MAPS_MISSING_ENTITY)
    for entity_id, store in store_by_entity.items():
        if entity_id not in accepted_entity_ids and store.user_modified:
            new_stores.append(store)
    # (Auto-gen orphaned stores are silently dropped by not including them above)

    # Include user-created stores (no ERD mapping)
    new_stores.extend(user_stores)

    # Build lookup: entity_id → store (for wiring flows)
    store_id_by_entity: dict[str, str] = {
        s.mapped_erd_entity: s.id
        for s in new_stores
        if s.mapped_erd_entity is not None
    }

    # ── Step 2 — Processes + DataFlows (one per accepted Relationship) ────────
    new_processes: list[Process] = []
    new_flows: list[DataFlow] = []

    # Accepted relationship IDs set (for orphan detection)
    accepted_rel_ids = {
        r.id for r in erd.relationships if r.review_status != "rejected"
    }

    for rel in erd.relationships:
        if rel.review_status == "rejected":
            continue

        from_store_id = store_id_by_entity.get(rel.from_.entity_id)
        to_store_id = store_id_by_entity.get(rel.to.entity_id)

        # Can only build flows if both endpoint stores exist
        if from_store_id is None or to_store_id is None:
            continue

        existing_proc = proc_by_rel.get(rel.id)
        if existing_proc is not None:
            if existing_proc.user_modified:
                # Preserve name/description; re-wire flows if stores were recreated
                new_processes.append(existing_proc)
                from_entity = _find_entity(erd.entities, rel.from_.entity_id)
                to_entity = _find_entity(erd.entities, rel.to.entity_id)
                verb = (rel.name or "").strip()
                flow1_name = verb or (from_entity.display_name if from_entity else "Data")
                flow2_name = to_entity.display_name if to_entity else "Data"

                new_flows.append(_build_relationship_flow(
                    _find_existing_flow(existing.data_flows, rel.id, existing_proc.id, "store_to_process"),
                    rel,
                    "store_to_process",
                    from_store_id,
                    existing_proc.id,
                    flow1_name,
                ))
                new_flows.append(_build_relationship_flow(
                    _find_existing_flow(existing.data_flows, rel.id, existing_proc.id, "process_to_store"),
                    rel,
                    "process_to_store",
                    existing_proc.id,
                    to_store_id,
                    flow2_name,
                ))
            else:
                # Update name (not user-modified)
                existing_proc.name = infer_process_name(rel, erd.entities)
                new_processes.append(existing_proc)
                # Re-create the two auto-gen flows
                from_entity = _find_entity(erd.entities, rel.from_.entity_id)
                to_entity = _find_entity(erd.entities, rel.to.entity_id)
                verb = (rel.name or "").strip()
                flow1_name = verb or (from_entity.display_name if from_entity else "Data")
                flow2_name = to_entity.display_name if to_entity else "Data"

                new_flows.append(_build_relationship_flow(
                    _find_existing_flow(existing.data_flows, rel.id, existing_proc.id, "store_to_process"),
                    rel,
                    "store_to_process",
                    from_store_id,
                    existing_proc.id,
                    flow1_name,
                ))
                new_flows.append(_build_relationship_flow(
                    _find_existing_flow(existing.data_flows, rel.id, existing_proc.id, "process_to_store"),
                    rel,
                    "process_to_store",
                    existing_proc.id,
                    to_store_id,
                    flow2_name,
                ))
        else:
            # Create new Process + 2 DataFlows
            proc = Process(
                id=_generated_process_id(rel.id),
                name=infer_process_name(rel, erd.entities),
                mapped_relationship_id=rel.id,
                user_modified=False,
            )
            new_processes.append(proc)

            from_entity = _find_entity(erd.entities, rel.from_.entity_id)
            to_entity = _find_entity(erd.entities, rel.to.entity_id)
            verb = (rel.name or "").strip()
            flow1_name = verb or (from_entity.display_name if from_entity else "Data")
            flow2_name = to_entity.display_name if to_entity else "Data"

            new_flows.append(_build_relationship_flow(
                None,
                rel,
                "store_to_process",
                from_store_id,
                proc.id,
                flow1_name,
            ))
            new_flows.append(_build_relationship_flow(
                None,
                rel,
                "process_to_store",
                proc.id,
                to_store_id,
                flow2_name,
            ))

    # Orphaned user-modified processes (rel was deleted): keep them
    # (sync_engine will flag as PROCESS_ORPHANED_RELATIONSHIP warning)
    for rel_id, proc in proc_by_rel.items():
        if rel_id not in accepted_rel_ids and proc.user_modified:
            new_processes.append(proc)

    # Include user-created processes (no ERD mapping)
    new_processes.extend(user_procs)

    # ── Step 3 — Preserve user-created DataFlows ─────────────────────────────
    # User-created flows have mapped_relationship_id == None
    user_flows = [f for f in existing.data_flows if f.mapped_relationship_id is None]
    new_flows.extend(user_flows)

    # Preserve all ExternalEntities unchanged
    return DfdModel(
        level=existing.level,
        notation=existing.notation,
        system_boundary=existing.system_boundary,
        external_entities=existing.external_entities,
        processes=new_processes,
        data_stores=new_stores,
        data_flows=new_flows,
        business_rules=existing.business_rules,
        connectors=existing.connectors,
    )
