"""
SQL exporter — pen.erd + pen.postgres → PostgreSQL schema.sql

Rules:
- Reads ONLY erd.entities, erd.relationships, and postgres settings
- Layout and styles are completely ignored
- Uses SQLGlot to validate generated DDL before returning
- Only exports entities with review_status != "rejected"
"""
from __future__ import annotations

import sqlglot

from models.pen import PenFile, Entity, Attribute, Relationship


# ── Attribute → column DDL ────────────────────────────────────────────────────

def _col_def(attr: Attribute) -> str:
    parts = [f'    "{attr.name}"', attr.pg_type]

    if attr.key_role == "primary":
        parts.append("NOT NULL")
    elif not attr.nullable:
        parts.append("NOT NULL")

    if attr.default is not None:
        parts.append(f"DEFAULT {attr.default}")

    if attr.key_role == "unique":
        parts.append("UNIQUE")

    if attr.check_constraint:
        parts.append(f"CHECK ({attr.check_constraint})")

    return " ".join(parts)


# ── Entity → CREATE TABLE ─────────────────────────────────────────────────────

def _create_table(entity: Entity) -> str:
    lines: list[str] = []
    pk_attr: Attribute | None = None
    col_defs: list[str] = []

    for attr in entity.attributes:
        if attr.review_status == "rejected":
            continue
        # Skip FK attrs here — we add them as constraints separately
        if attr.key_role == "foreign":
            # Still include the column definition (type, nullable)
            col_def = f'    "{attr.name}" {attr.pg_type}'
            if not attr.nullable:
                col_def += " NOT NULL"
            col_defs.append(col_def)
        else:
            col_defs.append(_col_def(attr))

        if attr.key_role == "primary":
            pk_attr = attr

    # Primary key constraint
    if pk_attr:
        col_defs.append(f'    PRIMARY KEY ("{pk_attr.name}")')

    lines.append(f'CREATE TABLE IF NOT EXISTS "{entity.name}" (')
    lines.append(",\n".join(col_defs))
    lines.append(");")

    return "\n".join(lines)


# ── Relationship → ALTER TABLE ADD CONSTRAINT ─────────────────────────────────

def _fk_constraint(rel: Relationship, pen: PenFile) -> str | None:
    if rel.postgres is None:
        return None

    # Resolve entity and attribute names
    from_entity = next((e for e in pen.erd.entities if e.id == rel.from_.entity_id), None)
    to_entity = next((e for e in pen.erd.entities if e.id == rel.to.entity_id), None)
    from_attr = next((a for e in pen.erd.entities for a in e.attributes if a.id == rel.from_.attribute_id), None)
    to_attr = next((a for e in pen.erd.entities for a in e.attributes if a.id == rel.to.attribute_id), None)

    if not all([from_entity, to_entity, from_attr, to_attr]):
        return None

    on_delete = rel.postgres.on_delete.upper().replace("_", " ")
    on_update = rel.postgres.on_update.upper().replace("_", " ")

    return (
        f'ALTER TABLE "{from_entity.name}"\n'
        f'    ADD CONSTRAINT "{rel.postgres.constraint_name}"\n'
        f'    FOREIGN KEY ("{from_attr.name}")\n'
        f'    REFERENCES "{to_entity.name}" ("{to_attr.name}")\n'
        f'    ON DELETE {on_delete}\n'
        f'    ON UPDATE {on_update};'
    )


# ── Main export ───────────────────────────────────────────────────────────────

def export_sql(pen: PenFile) -> str:
    """Generate PostgreSQL schema.sql from the pen file."""
    sections: list[str] = []

    # Extensions
    for ext in pen.postgres.extensions:
        sections.append(f"CREATE EXTENSION IF NOT EXISTS {ext};")
    if pen.postgres.extensions:
        sections.append("")

    # Tables (accepted entities only, topologically ordered — PKs first)
    accepted_entities = [e for e in pen.erd.entities if e.review_status != "rejected"]

    # Simple topo sort: entities without FK deps come first
    fk_targets = {rel.to.entity_id for rel in pen.erd.relationships if rel.review_status != "rejected"}
    ordered = [e for e in accepted_entities if e.id not in fk_targets or
               not any(r.from_.entity_id == e.id for r in pen.erd.relationships)]

    # Add remaining entities
    remaining = [e for e in accepted_entities if e not in ordered]
    ordered.extend(remaining)

    for entity in ordered:
        sections.append(_create_table(entity))
        sections.append("")

    # FK constraints
    fk_stmts: list[str] = []
    for rel in pen.erd.relationships:
        if rel.review_status == "rejected":
            continue
        stmt = _fk_constraint(rel, pen)
        if stmt:
            fk_stmts.append(stmt)

    if fk_stmts:
        sections.append("-- Foreign key constraints")
        sections.extend(fk_stmts)

    sql = "\n".join(sections)

    # Validate with SQLGlot (raises if fundamentally broken)
    try:
        sqlglot.parse(sql, dialect="postgres", error_level=sqlglot.ErrorLevel.WARN)
    except Exception as e:
        # Don't crash — return with a comment warning
        sql = f"-- SQLGlot validation warning: {e}\n\n" + sql

    return sql


# ── Mermaid ERD (lives here for convenience, own file wraps it) ───────────────

def export_mermaid(pen: PenFile) -> str:
    """Generate Mermaid erDiagram from the pen file."""
    lines: list[str] = ["erDiagram"]

    accepted_entities = [e for e in pen.erd.entities if e.review_status != "rejected"]

    for entity in accepted_entities:
        lines.append(f'    {entity.name.upper()} {{')
        for attr in entity.attributes:
            if attr.review_status == "rejected":
                continue
            pg = attr.pg_type
            role_marker = ""
            if attr.key_role == "primary":
                role_marker = " PK"
            elif attr.key_role == "foreign":
                role_marker = " FK"
            elif attr.key_role == "unique":
                role_marker = ""
            lines.append(f'        {pg} {attr.name}{role_marker}')
        lines.append("    }")

    for rel in pen.erd.relationships:
        if rel.review_status == "rejected":
            continue
        from_entity = next((e for e in pen.erd.entities if e.id == rel.from_.entity_id), None)
        to_entity = next((e for e in pen.erd.entities if e.id == rel.to.entity_id), None)
        if not from_entity or not to_entity:
            continue

        # Crow's foot notation (Mermaid convention):
        # Left side = from entity (the FK holder), right side = to entity (PK holder)
        # }o = zero or more, }| = one or more, || = exactly one, |o = zero or one
        from_min = rel.cardinality.from_min
        from_max = rel.cardinality.from_max

        # Left token describes cardinality on the "from" (FK) side
        if from_max == "many":
            left_outer = "}"
        else:
            left_outer = "|"
        left_inner = "|" if from_min >= 1 else "o"

        # Right token describes cardinality on the "to" (PK) side
        to_min = rel.cardinality.to_min
        to_max = rel.cardinality.to_max
        right_inner = "|" if to_max == 1 else "{"
        right_outer = "|" if to_min >= 1 else "o"

        card = f"{left_outer}{left_inner}--{right_outer}{right_inner}"
        label = rel.name or "has"
        lines.append(f'    {from_entity.name.upper()} {card} {to_entity.name.upper()} : "{label}"')

    return "\n".join(lines)


def export_dbml(pen: PenFile) -> str:
    """Generate DBML from the pen file."""
    lines: list[str] = [f'// Generated by DFDMaker', '']

    accepted_entities = [e for e in pen.erd.entities if e.review_status != "rejected"]

    for entity in accepted_entities:
        lines.append(f'Table {entity.name} {{')
        for attr in entity.attributes:
            if attr.review_status == "rejected":
                continue
            col = f'  {attr.name} {attr.pg_type}'
            notes: list[str] = []
            if attr.key_role == "primary":
                notes.append("pk")
            if not attr.nullable and attr.key_role != "primary":
                notes.append("not null")
            if attr.default:
                notes.append(f'default: `{attr.default}`')
            if notes:
                col += f' [{", ".join(notes)}]'
            lines.append(col)
        lines.append("}")
        lines.append("")

    # References
    for rel in pen.erd.relationships:
        if rel.review_status == "rejected":
            continue
        from_entity = next((e for e in pen.erd.entities if e.id == rel.from_.entity_id), None)
        to_entity = next((e for e in pen.erd.entities if e.id == rel.to.entity_id), None)
        from_attr = next((a for e in pen.erd.entities for a in e.attributes if a.id == rel.from_.attribute_id), None)
        to_attr = next((a for e in pen.erd.entities for a in e.attributes if a.id == rel.to.attribute_id), None)
        if not all([from_entity, to_entity, from_attr, to_attr]):
            continue

        from_max = rel.cardinality.from_max
        to_max = rel.cardinality.to_max

        if from_max == "many" and (to_max == 1 or to_max == "1"):
            ref_type = ">"
        elif from_max == 1 and to_max == "many":
            ref_type = "<"
        elif from_max == "many" and to_max == "many":
            ref_type = "<>"
        else:
            ref_type = "-"

        lines.append(
            f'Ref: {from_entity.name}.{from_attr.name} {ref_type} {to_entity.name}.{to_attr.name}'
        )

    return "\n".join(lines)
