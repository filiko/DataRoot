"""
OpsService — applies typed operations to a PenFile.

This is the safe editing path for assistant-driven updates.
Each op validates, propagates ERD->DFD if needed, and increments revision.
"""
from __future__ import annotations

import uuid
from typing import Any

from models.pen import (
    PenFile, Entity, Attribute, IndexDef, Relationship,
    RelationshipEndpoint, Cardinality, RelationshipPostgres,
    LayoutNode, LayoutEdge, DiagramLayout, DfdModel,
)
from generators.proposals import _join_table_name, _singularize


def _find_entity(pen: PenFile, entity_id: str) -> Entity | None:
    return next((e for e in pen.erd.entities if e.id == entity_id), None)


def _find_entity_by_name(pen: PenFile, name: str) -> Entity | None:
    return next((e for e in pen.erd.entities if e.name == name), None)


def _find_relationship(pen: PenFile, rel_id: str) -> Relationship | None:
    return next((r for r in pen.erd.relationships if r.id == rel_id), None)


def _find_primary_key(entity: Entity) -> Attribute:
    pk = next((a for a in entity.attributes if a.key_role == "primary"), None)
    if not pk:
        raise ValueError(f"Entity '{entity.name}' has no primary key")
    return pk


def _dfd_for_scope(pen: PenFile, scope: dict[str, Any] | None) -> DfdModel:
    scope = scope or {"diagram": "dfd", "level": "root"}
    if scope.get("diagram", "dfd") != "dfd":
        raise ValueError("DFD operation requires a DFD scope")

    level = scope.get("level", "root")
    if level == "root":
        return pen.dfd
    if level != "process":
        raise ValueError(f"Unsupported DFD scope level: {level}")

    process_id = scope.get("process_id")
    if not process_id:
        raise ValueError("Level 1 DFD scope requires process_id")
    process = next((p for p in pen.dfd.processes if p.id == process_id), None)
    if not process:
        raise ValueError(f"Process not found for Level 1 DFD: {process_id}")
    if process.level_1_diagram is None:
        raise ValueError(f"Process has no Level 1 DFD: {process_id}")
    return process.level_1_diagram


def _layout_for_scope(pen: PenFile, scope: dict[str, Any] | None) -> DiagramLayout:
    scope = scope or {"diagram": "dfd", "level": "root"}
    diagram = scope.get("diagram", "dfd")
    if diagram == "erd":
        return pen.layout.erd
    if diagram != "dfd":
        raise ValueError(f"Unsupported diagram scope: {diagram}")

    level = scope.get("level", "root")
    if level == "root":
        return pen.layout.dfd
    if level != "process":
        raise ValueError(f"Unsupported DFD scope level: {level}")

    process_id = scope.get("process_id")
    if not process_id:
        raise ValueError("Level 1 DFD scope requires process_id")
    return pen.layout.dfd_level_1.setdefault(process_id, DiagramLayout())


def _dfd_node_ids(dfd: DfdModel) -> set[str]:
    ids: set[str] = set()
    ids.update(node.id for node in dfd.external_entities)
    ids.update(node.id for node in dfd.processes)
    ids.update(node.id for node in dfd.data_stores)
    return ids


def _find_layout_edge(layout: DiagramLayout, edge_id: str) -> LayoutEdge | None:
    return next((edge for edge in layout.edges if edge.id == edge_id), None)


def _upsert_layout_edge(
    layout: DiagramLayout,
    edge_id: str,
    source_handle: str | None,
    target_handle: str | None,
) -> None:
    edge = _find_layout_edge(layout, edge_id)
    if edge is None:
        layout.edges.append(LayoutEdge(
            id=edge_id,
            route="orthogonal",
            source_handle=source_handle,
            target_handle=target_handle,
        ))
        return
    edge.source_handle = source_handle
    edge.target_handle = target_handle


def _validate_handle(handle: str | None, expected_type: str) -> None:
    if handle is not None and not handle.startswith(f"{expected_type}-"):
        raise ValueError(f"{expected_type}_handle has invalid id: {handle}")


def _find_or_create_fk_attribute(
    pen: PenFile,
    child_entity: Entity,
    parent_entity: Entity,
) -> Attribute:
    """
    Find an existing FK attribute on child_entity pointing to parent_entity's PK,
    or create a new one.
    """
    parent_pk = next(
        (a for a in parent_entity.attributes if a.key_role == "primary"),
        None,
    )
    if not parent_pk:
        raise ValueError(
            f"Parent entity '{parent_entity.name}' has no primary key. "
            f"Cannot create foreign key relationship."
        )

    existing_fk = next(
        (
            a for a in child_entity.attributes
            if a.key_role == "foreign"
            and any(
                parent_entity.id in str(e.source_id)
                for e in a.evidence
            )
        ),
        None,
    )
    if existing_fk:
        return existing_fk

    fk_attr = Attribute(
        id=f"attr_{uuid.uuid4().hex[:8]}",
        name=f"{parent_entity.name}_id",
        display_name=f"{parent_entity.display_name} ID",
        pg_type=parent_pk.pg_type,
        key_role="foreign",
        nullable=True,
    )
    child_entity.attributes.append(fk_attr)
    return fk_attr


class OpsService:
    @staticmethod
    def apply_op(pen: PenFile, op: str, payload: dict[str, Any]) -> PenFile:
        """Apply a single typed operation to a PenFile. Returns updated PenFile."""
        handler = {
            "entity.add": OpsService._entity_add,
            "entity.update": OpsService._entity_update,
            "entity.delete": OpsService._entity_delete,
            "attribute.add": OpsService._attribute_add,
            "attribute.update": OpsService._attribute_update,
            "attribute.delete": OpsService._attribute_delete,
            "index.add": OpsService._index_add,
            "index.update": OpsService._index_update,
            "index.delete": OpsService._index_delete,
            "relationship.add": OpsService._relationship_add,
            "relationship.update": OpsService._relationship_update,
            "relationship.delete": OpsService._relationship_delete,
            "relationship.m2m_convert": OpsService._relationship_m2m_convert,
            "dfd.flow.rename": OpsService._dfd_flow_rename,
            "dfd.flow.reconnect": OpsService._dfd_flow_reconnect,
            "dfd.flow.delete": OpsService._dfd_flow_delete,
            "layout.move_node": OpsService._layout_move_node,
            "proposal.answer": OpsService._proposal_answer,
            "postgres.update_settings": OpsService._postgres_update_settings,
        }.get(op)

        if not handler:
            raise ValueError(f"Unknown operation: {op}")
        return handler(pen, payload)

    @staticmethod
    def _entity_add(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        name = payload["name"]
        display_name = payload.get("display_name", name.replace("_", " ").title())
        entity = Entity(
            id=f"ent_{uuid.uuid4().hex[:8]}",
            name=name,
            display_name=display_name,
            attributes=[],
        )
        for attr_data in payload.get("attributes", []):
            attr = Attribute(
                id=f"attr_{uuid.uuid4().hex[:8]}",
                name=attr_data["name"],
                display_name=attr_data.get("display_name", attr_data["name"].replace("_", " ").title()),
                pg_type=attr_data.get("pg_type", "text"),
                key_role=attr_data.get("key_role", "none"),
                nullable=attr_data.get("nullable", True),
            )
            entity.attributes.append(attr)
        pen.erd.entities.append(entity)
        return pen

    @staticmethod
    def _entity_update(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['id']}")
        if "name" in payload:
            entity.name = payload["name"]
        if "display_name" in payload:
            entity.display_name = payload["display_name"]
        if "description" in payload:
            entity.description = payload["description"]
        if "color" in payload:
            entity.color = payload["color"]
        return pen

    @staticmethod
    def _entity_delete(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity_id = payload["id"]
        pen.erd.entities = [e for e in pen.erd.entities if e.id != entity_id]
        pen.erd.relationships = [
            r for r in pen.erd.relationships
            if r.from_.entity_id != entity_id and r.to.entity_id != entity_id
        ]
        pen.dfd.data_stores = [
            s for s in pen.dfd.data_stores if s.mapped_erd_entity != entity_id
        ]
        return pen

    @staticmethod
    def _attribute_add(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        attr = Attribute(
            id=f"attr_{uuid.uuid4().hex[:8]}",
            name=payload["name"],
            display_name=payload.get("display_name", payload["name"].replace("_", " ").title()),
            pg_type=payload.get("pg_type", "text"),
            key_role=payload.get("key_role", "none"),
            nullable=payload.get("nullable", True),
        )
        entity.attributes.append(attr)
        return pen

    @staticmethod
    def _attribute_update(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        attr = next((a for a in entity.attributes if a.id == payload["attribute_id"]), None)
        if not attr:
            raise ValueError(f"Attribute not found: {payload['attribute_id']}")
        if "name" in payload:
            attr.name = payload["name"]
        if "display_name" in payload:
            attr.display_name = payload["display_name"]
        if "pg_type" in payload:
            attr.pg_type = payload["pg_type"]
        if "nullable" in payload:
            attr.nullable = payload["nullable"]
        if "key_role" in payload:
            attr.key_role = payload["key_role"]
        if "enum_values" in payload:
            attr.enum_values = payload["enum_values"]
        return pen

    @staticmethod
    def _attribute_delete(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        entity.attributes = [
            a for a in entity.attributes if a.id != payload["attribute_id"]
        ]
        pen.erd.relationships = [
            r for r in pen.erd.relationships
            if r.from_.attribute_id != payload["attribute_id"]
            and r.to.attribute_id != payload["attribute_id"]
        ]
        for index in list(entity.indexes):
            if payload["attribute_id"] in index.attribute_ids:
                index.attribute_ids = [
                    aid for aid in index.attribute_ids if aid != payload["attribute_id"]
                ]
                if not index.attribute_ids:
                    entity.indexes.remove(index)
        return pen

    @staticmethod
    def _index_entity_and_attrs(pen: PenFile, payload: dict[str, Any]) -> tuple[Entity, list[str]]:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        attr_ids = payload.get("attribute_ids", [])
        known = {a.id for a in entity.attributes}
        missing = [aid for aid in attr_ids if aid not in known]
        if missing:
            raise ValueError(f"Attributes not found on '{entity.name}': {', '.join(missing)}")
        return entity, attr_ids

    @staticmethod
    def _index_add(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity, attr_ids = OpsService._index_entity_and_attrs(pen, payload)
        if not attr_ids:
            raise ValueError("index.add requires at least one attribute_id")
        entity.indexes.append(IndexDef(
            name=payload.get("name") or f"idx_{entity.name}_{uuid.uuid4().hex[:6]}",
            attribute_ids=attr_ids,
            unique=payload.get("unique", False),
        ))
        return pen

    @staticmethod
    def _index_update(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        index = next((i for i in entity.indexes if i.id == payload["index_id"]), None)
        if not index:
            raise ValueError(f"Index not found: {payload['index_id']}")
        if "name" in payload:
            index.name = payload["name"]
        if "unique" in payload:
            index.unique = payload["unique"]
        if "attribute_ids" in payload:
            _, attr_ids = OpsService._index_entity_and_attrs(pen, payload)
            if not attr_ids:
                raise ValueError("index.update requires at least one attribute_id")
            index.attribute_ids = attr_ids
        return pen

    @staticmethod
    def _index_delete(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        entity = _find_entity(pen, payload["entity_id"])
        if not entity:
            raise ValueError(f"Entity not found: {payload['entity_id']}")
        entity.indexes = [i for i in entity.indexes if i.id != payload["index_id"]]
        return pen

    @staticmethod
    def _relationship_add(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        """
        Add a relationship with correct FK semantics.
        Creates or finds the FK attribute on the child entity automatically.
        """
        from_entity_name = payload["from_entity"]
        to_entity_name = payload["to_entity"]
        cardinality = payload.get("cardinality", {"from_min": 0, "from_max": "many", "to_min": 1, "to_max": 1})

        from_entity = _find_entity_by_name(pen, from_entity_name)
        to_entity = _find_entity_by_name(pen, to_entity_name)
        if not from_entity:
            raise ValueError(f"Entity not found: {from_entity_name}")
        if not to_entity:
            raise ValueError(f"Entity not found: {to_entity_name}")

        to_pk = next((a for a in to_entity.attributes if a.key_role == "primary"), None)
        if not to_pk:
            raise ValueError(f"Entity '{to_entity_name}' has no primary key")

        fk_attr = _find_or_create_fk_attribute(pen, from_entity, to_entity)

        rel = Relationship(
            id=f"rel_{uuid.uuid4().hex[:8]}",
            name=payload.get("name"),
            from_=RelationshipEndpoint(entity_id=from_entity.id, attribute_id=fk_attr.id),
            to=RelationshipEndpoint(entity_id=to_entity.id, attribute_id=to_pk.id),
            cardinality=Cardinality(**cardinality),
            postgres=RelationshipPostgres(
                constraint_name=f"fk_{from_entity.name}_{to_entity.name}",
                on_delete="restrict",
                on_update="no_action",
            ) if cardinality.get("to_max") != 1 else None,
        )
        pen.erd.relationships.append(rel)
        return pen

    @staticmethod
    def _relationship_delete(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        pen.erd.relationships = [
            r for r in pen.erd.relationships if r.id != payload["id"]
        ]
        pen.dfd.processes = [
            p for p in pen.dfd.processes if p.mapped_relationship_id != payload["id"]
        ]
        pen.dfd.data_flows = [
            f for f in pen.dfd.data_flows if f.mapped_relationship_id != payload["id"]
        ]
        return pen

    @staticmethod
    def _relationship_update(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        rel = _find_relationship(pen, payload["id"])
        if not rel:
            raise ValueError(f"Relationship not found: {payload['id']}")
        if "name" in payload:
            rel.name = payload["name"]
        if "cardinality" in payload:
            rel.cardinality = Cardinality(**payload["cardinality"])
        return pen

    @staticmethod
    def _relationship_m2m_convert(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        rel = _find_relationship(pen, payload["id"])
        if not rel:
            raise ValueError(f"Relationship not found: {payload['id']}")

        from_entity = _find_entity(pen, rel.from_.entity_id)
        to_entity = _find_entity(pen, rel.to.entity_id)
        if not from_entity or not to_entity:
            raise ValueError("Relationship endpoints must reference existing entities")
        if from_entity.id == to_entity.id:
            raise ValueError("Self-referential many-to-many conversion is not supported")

        from_pk = _find_primary_key(from_entity)
        to_pk = _find_primary_key(to_entity)
        join_name = _join_table_name(from_entity.name, to_entity.name)
        if _find_entity_by_name(pen, join_name):
            raise ValueError(f"Join entity already exists: {join_name}")

        from_fk_col = f"{_singularize(from_entity.name)}_id"
        to_fk_col = f"{_singularize(to_entity.name)}_id"
        from_fk_attr = Attribute(
            id=f"attr_{join_name}_{from_fk_col}",
            name=from_fk_col,
            display_name=from_fk_col.replace("_", " ").title(),
            pg_type=from_pk.pg_type,
            key_role="foreign",
            nullable=False,
            review_status="accepted",
        )
        to_fk_attr = Attribute(
            id=f"attr_{join_name}_{to_fk_col}",
            name=to_fk_col,
            display_name=to_fk_col.replace("_", " ").title(),
            pg_type=to_pk.pg_type,
            key_role="foreign",
            nullable=False,
            review_status="accepted",
        )
        join_entity = Entity(
            id=f"ent_{join_name}",
            kind="strong_entity",
            name=join_name,
            display_name=join_name.replace("_", " ").title(),
            attributes=[
                Attribute(
                    id=f"attr_{join_name}_id",
                    name="id",
                    display_name="id",
                    pg_type="uuid",
                    key_role="primary",
                    nullable=False,
                    default="gen_random_uuid()",
                    confidence=1.0,
                    review_status="accepted",
                ),
                from_fk_attr,
                to_fk_attr,
                Attribute(
                    id=f"attr_{join_name}_created_at",
                    name="created_at",
                    display_name="created_at",
                    pg_type="timestamptz",
                    key_role="audit",
                    nullable=False,
                    default="now()",
                    review_status="accepted",
                ),
                Attribute(
                    id=f"attr_{join_name}_updated_at",
                    name="updated_at",
                    display_name="updated_at",
                    pg_type="timestamptz",
                    key_role="audit",
                    nullable=False,
                    default="now()",
                    review_status="accepted",
                ),
            ],
            proposal_reason=f"Intermediary table for {from_entity.display_name} and {to_entity.display_name}",
            confidence=1.0,
            review_status="accepted",
        )

        direct_rel_ids = {
            r.id for r in pen.erd.relationships
            if (
                (r.from_.entity_id == from_entity.id and r.to.entity_id == to_entity.id) or
                (r.from_.entity_id == to_entity.id and r.to.entity_id == from_entity.id)
            )
        }
        pen.erd.relationships = [
            r for r in pen.erd.relationships if r.id not in direct_rel_ids
        ]
        pen.layout.erd.edges = [
            e for e in pen.layout.erd.edges if e.id not in direct_rel_ids
        ]
        pen.dfd.processes = [
            p for p in pen.dfd.processes if p.mapped_relationship_id not in direct_rel_ids
        ]
        pen.dfd.data_flows = [
            f for f in pen.dfd.data_flows if f.mapped_relationship_id not in direct_rel_ids
        ]

        rel_to_from = Relationship(
            id=f"rel_{uuid.uuid4().hex[:8]}",
            name="belongs to",
            from_=RelationshipEndpoint(entity_id=join_entity.id, attribute_id=from_fk_attr.id),
            to=RelationshipEndpoint(entity_id=from_entity.id, attribute_id=from_pk.id),
            cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
            postgres=RelationshipPostgres(
                constraint_name=f"fk_{join_name}_{from_fk_col}",
                on_delete="cascade",
                on_update="cascade",
            ),
            evidence=[f"Converted relationship '{rel.name or rel.id}' to a join table"],
            confidence=1.0,
            review_status="accepted",
        )
        rel_to_to = Relationship(
            id=f"rel_{uuid.uuid4().hex[:8]}",
            name="belongs to",
            from_=RelationshipEndpoint(entity_id=join_entity.id, attribute_id=to_fk_attr.id),
            to=RelationshipEndpoint(entity_id=to_entity.id, attribute_id=to_pk.id),
            cardinality=Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
            postgres=RelationshipPostgres(
                constraint_name=f"fk_{join_name}_{to_fk_col}",
                on_delete="cascade",
                on_update="cascade",
            ),
            evidence=[f"Converted relationship '{rel.name or rel.id}' to a join table"],
            confidence=1.0,
            review_status="accepted",
        )
        pen.erd.entities.append(join_entity)
        pen.erd.relationships.extend([rel_to_from, rel_to_to])
        pen.layout.erd.edges.extend([
            LayoutEdge(id=rel_to_from.id, route="orthogonal"),
            LayoutEdge(id=rel_to_to.id, route="orthogonal"),
        ])

        from_node = next((n for n in pen.layout.erd.nodes if n.id == from_entity.id), None)
        to_node = next((n for n in pen.layout.erd.nodes if n.id == to_entity.id), None)
        if from_node and to_node:
            x = (from_node.x + to_node.x) / 2
            y = max(from_node.y, to_node.y) + 220
        else:
            index = len(pen.erd.entities) - 1
            x = 40 + (index % 3) * 340
            y = 40 + (index // 3) * 240
        pen.layout.erd.nodes.append(LayoutNode(
            id=join_entity.id,
            x=x,
            y=y,
            width=280,
            height=80 + len(join_entity.attributes) * 24,
        ))

        pair = tuple(sorted([from_entity.name, to_entity.name]))
        for proposal in pen.review.proposals:
            if proposal.proposal_type != "many_to_many_join":
                continue
            ctx = proposal.context
            proposal_pair = tuple(sorted([
                str(ctx.get("from_table", "")),
                str(ctx.get("to_table", "")),
            ]))
            if proposal_pair == pair:
                proposal.status = "accepted"

        return pen

    @staticmethod
    def _dfd_flow_rename(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        dfd = _dfd_for_scope(pen, payload.get("scope"))
        flow_id = payload["id"]
        flow = next((item for item in dfd.data_flows if item.id == flow_id), None)
        if flow is None:
            raise ValueError(f"DataFlow not found: {flow_id}")

        flow.data_name = str(payload.get("data_name", "")).strip() or None
        flow.user_modified = True
        return pen

    @staticmethod
    def _dfd_flow_reconnect(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        scope = payload.get("scope")
        dfd = _dfd_for_scope(pen, scope)
        layout = _layout_for_scope(pen, scope)
        flow_id = payload["id"]
        source_id = payload["from"]
        target_id = payload["to"]
        source_handle = payload.get("source_handle")
        target_handle = payload.get("target_handle")

        flow = next((item for item in dfd.data_flows if item.id == flow_id), None)
        if flow is None:
            raise ValueError(f"DataFlow not found: {flow_id}")

        node_ids = _dfd_node_ids(dfd)
        if source_id not in node_ids:
            raise ValueError(f"DataFlow source node not found: {source_id}")
        if target_id not in node_ids:
            raise ValueError(f"DataFlow target node not found: {target_id}")
        _validate_handle(source_handle, "source")
        _validate_handle(target_handle, "target")

        flow.from_ = source_id
        flow.to = target_id
        flow.user_modified = True
        _upsert_layout_edge(layout, flow_id, source_handle, target_handle)
        return pen

    @staticmethod
    def _dfd_flow_delete(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        scope = payload.get("scope")
        dfd = _dfd_for_scope(pen, scope)
        layout = _layout_for_scope(pen, scope)
        flow_id = payload["id"]
        if not any(flow.id == flow_id for flow in dfd.data_flows):
            raise ValueError(f"DataFlow not found: {flow_id}")

        dfd.data_flows = [flow for flow in dfd.data_flows if flow.id != flow_id]
        layout.edges = [edge for edge in layout.edges if edge.id != flow_id]
        return pen

    @staticmethod
    def _layout_move_node(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        diagram = payload.get("diagram", "erd")
        node_id = payload["id"]
        x = payload["x"]
        y = payload["y"]

        layout = pen.layout.erd if diagram == "erd" else pen.layout.dfd
        existing = next((n for n in layout.nodes if n.id == node_id), None)
        if existing:
            existing.x = x
            existing.y = y
        else:
            layout.nodes.append(LayoutNode(id=node_id, x=x, y=y))
        return pen

    @staticmethod
    def _proposal_answer(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        proposal_id = payload["proposal_id"]
        answer_index = payload["answer_index"]
        proposal = next((p for p in pen.review.proposals if p.id == proposal_id), None)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        status_map = {0: "accepted", 1: "rejected", 2: "rejected"}
        proposal.status = status_map.get(answer_index, "rejected")
        return pen

    @staticmethod
    def _postgres_update_settings(pen: PenFile, payload: dict[str, Any]) -> PenFile:
        if "schema_name" in payload:
            pen.postgres.schema_name = payload["schema_name"]
        if "extensions" in payload:
            pen.postgres.extensions = payload["extensions"]
        if "add_audit_timestamps" in payload:
            pen.postgres.add_audit_timestamps = payload["add_audit_timestamps"]
        if "default_primary_key" in payload:
            dpk = payload["default_primary_key"]
            pen.postgres.default_primary_key.type = dpk.get("type", "uuid")
            pen.postgres.default_primary_key.default = dpk.get("default", "gen_random_uuid()")
        return pen
