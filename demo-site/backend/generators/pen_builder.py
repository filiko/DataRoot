"""
pen_builder — converts SourceTableModel[] + ReviewProposal[] into a PenFile.

This is the bridge between the deterministic parsing pipeline and the canonical model.

Rules:
- Every source table → one Entity with its literal columns
- UUID primary key is auto-added to every entity (business IDs stored as UNIQUE)
- Audit timestamps (created_at, updated_at) auto-added if postgres.add_audit_timestamps
- Accepted entity_split proposals → new Entity + FK Relationship
- Accepted foreign_key proposals → FK Relationship
- Accepted enum_to_lookup proposals → new lookup Entity + FK
- Proposals with status="pending" go into review.proposals for the UI
"""
from __future__ import annotations

import uuid as _uuid
import re

from models.source import SourceTableModel, SourceColumn
from models.pen import (
    PenFile, SourceRef, ErdModel, Entity, Attribute, Relationship,
    RelationshipEndpoint, RelationshipPostgres, Cardinality, ReviewProposal,
    LayoutNode, DiagramLayout,
)
from generators.proposals import generate_proposals, _singularize, _join_table_name
from generators.sync_engine import propagate_erd_to_dfd


_ID_SUFFIX = re.compile(r"(_id|_ID|Id|ID)$")

# Mapping from profiler inferred_type → PostgreSQL type
_PG_TYPE_MAP: dict[str, str] = {
    "uuid":     "uuid",
    "email":    "text",
    "integer":  "integer",
    "float":    "numeric",
    "boolean":  "boolean",
    "date":     "date",
    "datetime": "timestamptz",
    "phone":    "text",
    "string":   "text",
}


def _pg_type(inferred: str) -> str:
    return _PG_TYPE_MAP.get(inferred, "text")


def _make_pk_attribute(entity_name: str) -> Attribute:
    return Attribute(
        id=f"attr_{entity_name}_id",
        name="id",
        display_name="id",
        pg_type="uuid",
        key_role="primary",
        nullable=False,
        default="gen_random_uuid()",
        confidence=1.0,
        review_status="accepted",
    )


def _make_audit_attributes(entity_name: str) -> list[Attribute]:
    return [
        Attribute(
            id=f"attr_{entity_name}_created_at",
            name="created_at",
            display_name="created_at",
            pg_type="timestamptz",
            key_role="audit",
            nullable=False,
            default="now()",
            review_status="accepted",
        ),
        Attribute(
            id=f"attr_{entity_name}_updated_at",
            name="updated_at",
            display_name="updated_at",
            pg_type="timestamptz",
            key_role="audit",
            nullable=False,
            default="now()",
            review_status="accepted",
        ),
    ]


def _source_col_to_attribute(col: SourceColumn, entity_name: str) -> Attribute:
    """Convert a SourceColumn into an Attribute with correct key_role and pg_type."""
    key_role = "none"
    pg_type = _pg_type(col.inferred_type)

    if "primary_key_candidate" in col.role_candidates:
        # Don't make source IDs the actual PK — store as business_key UNIQUE
        key_role = "business_key"
    elif "foreign_key_candidate" in col.role_candidates:
        key_role = "foreign"
        pg_type = "uuid"  # FKs will reference UUID PKs
    elif col.possible_semantic_type == "email":
        key_role = "unique"
    elif "enum_candidate" in col.role_candidates:
        key_role = "none"  # plain column; lookup table proposal handles the rest
    elif "audit" in col.role_candidates:
        key_role = "audit"

    return Attribute(
        id=f"attr_{entity_name}_{col.canonical_name}",
        name=col.canonical_name,
        display_name=col.source_name,
        pg_type=pg_type,
        key_role=key_role,
        nullable=col.null_rate > 0,
        source_columns=[col.source_name],
        confidence=0.9,
        review_status="accepted",
    )


def _entity_from_source_table(table: SourceTableModel, add_audit: bool = True) -> Entity:
    """Build a literal Entity from a SourceTableModel."""
    name = table.detected_table_name

    attributes: list[Attribute] = []

    # 1. UUID primary key
    attributes.append(_make_pk_attribute(name))

    # 2. Source columns
    for col in table.columns:
        attr = _source_col_to_attribute(col, name)
        attributes.append(attr)

    # 3. Audit timestamps
    if add_audit:
        attributes.extend(_make_audit_attributes(name))

    return Entity(
        id=f"ent_{name}",
        kind="strong_entity",
        name=name,
        display_name=table.detected_table_name.replace("_", " ").title(),
        attributes=attributes,
        source_evidence=[
            {"source_id": table.source_id, "columns": [c.source_name for c in table.columns]}
        ],
        confidence=0.95,
        review_status="accepted",
    )


def _auto_layout(entities: list[Entity]) -> DiagramLayout:
    """Assign simple left-to-right layout positions."""
    nodes: list[LayoutNode] = []
    cols = 3
    for i, ent in enumerate(entities):
        col = i % cols
        row = i // cols
        h = 80 + len(ent.attributes) * 24
        nodes.append(LayoutNode(
            id=ent.id,
            x=40 + col * 340,
            y=40 + row * (h + 60),
            width=280,
            height=h,
        ))
    return DiagramLayout(nodes=nodes, edges=[])


def build_pen_file(
    tables: list[SourceTableModel],
    project_name: str = "Untitled Project",
    source_paths: list[str] | None = None,
) -> PenFile:
    """
    Main entry point.
    Returns a PenFile with:
    - entities derived from each source table (literal mode)
    - pending proposals in review.proposals
    """
    pen = PenFile()
    pen.project.name = project_name

    # Register source files
    source_paths = source_paths or []
    for i, table in enumerate(tables):
        ext = table.file_name.rsplit(".", 1)[-1].lower() if "." in table.file_name else "csv"
        src_type = "xlsx" if ext in ("xlsx", "xls") else "csv"
        ref = SourceRef(
            id=f"src_{i}",
            type=src_type,
            name=table.file_name,
            raw_path=source_paths[i] if i < len(source_paths) else None,
        )
        if not any(s.name == ref.name for s in pen.sources):
            pen.sources.append(ref)

    # Build entities from source tables
    entities: list[Entity] = []
    for table in tables:
        ent = _entity_from_source_table(table, add_audit=pen.postgres.add_audit_timestamps)
        entities.append(ent)

    pen.erd.entities = entities

    # Generate proposals (all start as "pending")
    proposals = generate_proposals(tables)
    pen.review.proposals = proposals

    # Auto-layout ERD
    pen.layout.erd = _auto_layout(entities)

    # Build initial DFD (DataStores only — no relationships yet at this stage)
    propagate_erd_to_dfd(pen)

    return pen


def apply_proposal(pen: PenFile, proposal_id: str, answer_index: int) -> PenFile:
    """
    Apply a review proposal answer to the PenFile.

    answer_index:
      0 = accept (first option — the suggested change)
      1 = reject (keep as-is)
      2 = not sure (mark for later)
    """
    proposal = next((p for p in pen.review.proposals if p.id == proposal_id), None)
    if proposal is None:
        raise ValueError(f"Proposal {proposal_id} not found")

    if answer_index == 1:
        proposal.status = "rejected"
        return pen

    if answer_index == 2:
        # Keep as pending / not sure
        return pen

    # answer_index == 0 → accept
    proposal.status = "accepted"

    if proposal.proposal_type == "entity_split":
        _apply_entity_split(pen, proposal)
    elif proposal.proposal_type == "foreign_key":
        _apply_foreign_key(pen, proposal)
    elif proposal.proposal_type == "enum_to_lookup":
        _apply_enum_to_lookup(pen, proposal)
    elif proposal.proposal_type == "many_to_many_join":
        _apply_many_to_many_join(pen, proposal)

    # Propagate ERD changes to DFD and write back dfd_process_id
    propagate_erd_to_dfd(pen)

    return pen


def _find_entity(pen: PenFile, name: str) -> Entity | None:
    return next((e for e in pen.erd.entities if e.name == name), None)


def _apply_entity_split(pen: PenFile, proposal: ReviewProposal) -> None:
    ctx = proposal.context
    source_table_name: str = ctx["source_table"]
    entity_label: str = ctx["entity_label"]
    matched_columns: list[str] = ctx["matched_columns"]
    new_entity_name = f"{entity_label}s"

    source_entity = _find_entity(pen, source_table_name)
    if source_entity is None:
        return

    # Create new entity with UUID PK + matched columns + audit timestamps
    new_attrs: list[Attribute] = [_make_pk_attribute(new_entity_name)]
    moved_attr_ids: list[str] = []
    for attr in source_entity.attributes:
        if attr.name in matched_columns:
            new_attr = attr.model_copy()
            new_attr.id = f"attr_{new_entity_name}_{attr.name}"
            new_attrs.append(new_attr)
            moved_attr_ids.append(attr.id)
    new_attrs.extend(_make_audit_attributes(new_entity_name))

    new_entity = Entity(
        id=f"ent_{new_entity_name}",
        kind="strong_entity",
        name=new_entity_name,
        display_name=entity_label.title() + "s",
        attributes=new_attrs,
        proposal_reason=proposal.title,
        confidence=proposal.confidence,
        review_status="accepted",
    )
    pen.erd.entities.append(new_entity)

    # Remove matched columns from source entity, add FK column
    source_entity.attributes = [a for a in source_entity.attributes if a.id not in moved_attr_ids]
    fk_attr = Attribute(
        id=f"attr_{source_table_name}_{entity_label}_id",
        name=f"{entity_label}_id",
        display_name=f"{entity_label.title()} ID",
        pg_type="uuid",
        key_role="foreign",
        nullable=False,
        review_status="accepted",
    )
    # Insert FK after the PK column
    source_entity.attributes.insert(1, fk_attr)

    # Create relationship
    rel = Relationship(**{
        "from": RelationshipEndpoint(entity_id=source_entity.id, attribute_id=fk_attr.id),
        "to": RelationshipEndpoint(entity_id=new_entity.id, attribute_id=f"attr_{new_entity_name}_id"),
        "name": "splits into",
        "cardinality": Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
        "postgres": RelationshipPostgres(
            constraint_name=f"fk_{source_table_name}_{entity_label}_id",
            on_delete="restrict",
        ),
        "evidence": [proposal.question],
        "confidence": proposal.confidence,
        "review_status": "accepted",
    })
    pen.erd.relationships.append(rel)

    # Update layout
    existing_ids = {n.id for n in pen.layout.erd.nodes}
    if new_entity.id not in existing_ids:
        all_entities = pen.erd.entities
        pen.layout.erd = _auto_layout(all_entities)


def _apply_foreign_key(pen: PenFile, proposal: ReviewProposal) -> None:
    ctx = proposal.context
    from_entity = _find_entity(pen, ctx["from_table"])
    to_entity = _find_entity(pen, ctx["to_table"])
    if not from_entity or not to_entity:
        return

    from_attr = next((a for a in from_entity.attributes if a.name == ctx["from_column"]), None)
    to_attr = next((a for a in to_entity.attributes if a.name == "id"), None)
    if not from_attr or not to_attr:
        return

    from_attr.key_role = "foreign"
    from_attr.pg_type = "uuid"

    # Infer verb from FK column name: "customer_id" → "belongs to"
    col_stem = ctx["from_column"].removesuffix("_id").removesuffix("_fk")
    rel_verb = "belongs to"

    rel = Relationship(**{
        "from": RelationshipEndpoint(entity_id=from_entity.id, attribute_id=from_attr.id),
        "to": RelationshipEndpoint(entity_id=to_entity.id, attribute_id=to_attr.id),
        "name": rel_verb,
        "cardinality": Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
        "postgres": RelationshipPostgres(
            constraint_name=f"fk_{ctx['from_table']}_{ctx['from_column']}",
            on_delete=ctx.get("on_delete", "restrict"),
        ),
        "evidence": [proposal.question],
        "confidence": proposal.confidence,
        "review_status": "accepted",
    })
    pen.erd.relationships.append(rel)


def _apply_enum_to_lookup(pen: PenFile, proposal: ReviewProposal) -> None:
    ctx = proposal.context
    source_table_name = ctx["source_table"]
    col_name = ctx["column"]
    values = ctx.get("values", [])

    lookup_entity_name = f"{col_name}_types"
    lookup_entity = Entity(
        id=f"ent_{lookup_entity_name}",
        kind="lookup_table",
        name=lookup_entity_name,
        display_name=col_name.replace("_", " ").title() + " Types",
        attributes=[
            _make_pk_attribute(lookup_entity_name),
            Attribute(
                id=f"attr_{lookup_entity_name}_name",
                name="name",
                display_name="Name",
                pg_type="text",
                key_role="unique",
                nullable=False,
            ),
        ],
        proposal_reason=proposal.title,
        confidence=proposal.confidence,
        review_status="accepted",
    )
    pen.erd.entities.append(lookup_entity)

    # Update source entity column to be a FK
    source_entity = _find_entity(pen, source_table_name)
    if source_entity:
        col_attr = next((a for a in source_entity.attributes if a.name == col_name), None)
        if col_attr:
            col_attr.name = f"{col_name}_id"
            col_attr.pg_type = "uuid"
            col_attr.key_role = "foreign"

        rel = Relationship(**{
            "from": RelationshipEndpoint(entity_id=source_entity.id, attribute_id=col_attr.id if col_attr else ""),
            "to": RelationshipEndpoint(entity_id=lookup_entity.id, attribute_id=f"attr_{lookup_entity_name}_id"),
            "cardinality": Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
            "postgres": RelationshipPostgres(
                constraint_name=f"fk_{source_table_name}_{col_name}_id",
                on_delete="restrict",
            ),
            "evidence": [proposal.question],
            "confidence": proposal.confidence,
            "review_status": "accepted",
        })
        pen.erd.relationships.append(rel)

    pen.layout.erd = _auto_layout(pen.erd.entities)


def _apply_many_to_many_join(pen: PenFile, proposal: ReviewProposal) -> None:
    ctx = proposal.context
    from_table_name: str = ctx["from_table"]
    to_table_name: str = ctx["to_table"]

    from_entity = _find_entity(pen, from_table_name)
    to_entity = _find_entity(pen, to_table_name)
    if not from_entity or not to_entity:
        return

    # Re-derive names from actual entity objects — more reliable than context strings
    # which were built with naive singularization at proposal-generation time.
    join_name = _join_table_name(from_entity.name, to_entity.name)
    from_fk_col = f"{_singularize(from_entity.name)}_id"
    to_fk_col = f"{_singularize(to_entity.name)}_id"

    # Create join entity with UUID PK + two FK attrs + audit timestamps
    join_entity = Entity(
        id=f"ent_{join_name}",
        kind="strong_entity",
        name=join_name,
        display_name=join_name.replace("_", " ").title(),
        attributes=[
            _make_pk_attribute(join_name),
            Attribute(
                id=f"attr_{join_name}_{from_fk_col}",
                name=from_fk_col,
                display_name=from_fk_col.replace("_", " ").title(),
                pg_type="uuid",
                key_role="foreign",
                nullable=False,
                review_status="accepted",
            ),
            Attribute(
                id=f"attr_{join_name}_{to_fk_col}",
                name=to_fk_col,
                display_name=to_fk_col.replace("_", " ").title(),
                pg_type="uuid",
                key_role="foreign",
                nullable=False,
                review_status="accepted",
            ),
            *_make_audit_attributes(join_name),
        ],
        proposal_reason=proposal.title,
        confidence=proposal.confidence,
        review_status="accepted",
    )
    pen.erd.entities.append(join_entity)

    # Remove any direct relationships between the two entities (the old M2M links)
    pen.erd.relationships = [
        r for r in pen.erd.relationships
        if not (
            (r.from_.entity_id == from_entity.id and r.to.entity_id == to_entity.id) or
            (r.from_.entity_id == to_entity.id and r.to.entity_id == from_entity.id)
        )
    ]

    # join → from_entity (many-to-one)
    rel_to_from = Relationship(**{
        "from": RelationshipEndpoint(
            entity_id=join_entity.id,
            attribute_id=f"attr_{join_name}_{from_fk_col}",
        ),
        "to": RelationshipEndpoint(
            entity_id=from_entity.id,
            attribute_id=f"attr_{from_entity.name}_id",
        ),
        "name": "belongs to",
        "cardinality": Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
        "postgres": RelationshipPostgres(
            constraint_name=f"fk_{join_name}_{from_fk_col}",
            on_delete="cascade",
        ),
        "evidence": [proposal.question],
        "confidence": proposal.confidence,
        "review_status": "accepted",
    })
    pen.erd.relationships.append(rel_to_from)

    # join → to_entity (many-to-one)
    rel_to_to = Relationship(**{
        "from": RelationshipEndpoint(
            entity_id=join_entity.id,
            attribute_id=f"attr_{join_name}_{to_fk_col}",
        ),
        "to": RelationshipEndpoint(
            entity_id=to_entity.id,
            attribute_id=f"attr_{to_entity.name}_id",
        ),
        "name": "belongs to",
        "cardinality": Cardinality(from_min=0, from_max="many", to_min=1, to_max=1),
        "postgres": RelationshipPostgres(
            constraint_name=f"fk_{join_name}_{to_fk_col}",
            on_delete="cascade",
        ),
        "evidence": [proposal.question],
        "confidence": proposal.confidence,
        "review_status": "accepted",
    })
    pen.erd.relationships.append(rel_to_to)

    pen.layout.erd = _auto_layout(pen.erd.entities)
