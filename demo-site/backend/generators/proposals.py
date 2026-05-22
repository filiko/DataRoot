"""
Normalization signal detection — purely deterministic rules.
Reads SourceTableModel[] → produces ReviewProposal[] for the pen file.

Signals detected:
1. entity_split   — column group {name, email, phone} repeating across many rows
2. foreign_key    — _id column or matching column name across sheets
3. enum_to_lookup — low-cardinality string column
4. many_to_many   — repeating group + no natural PK on either side
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from models.source import SourceTableModel, SourceColumn
from models.pen import ReviewProposal, PenFile

_ID_SUFFIX = re.compile(r"(_id|_ID|Id|ID)$")

# Column-name groups that suggest a denormalized entity embedded in another table
_ENTITY_GROUPS: list[tuple[str, list[re.Pattern]]] = [
    ("customer", [
        re.compile(r"customer|client|buyer|user|member|account", re.I),
    ]),
    ("product", [
        re.compile(r"product|item|sku|good|article|merchandise", re.I),
    ]),
    ("supplier", [
        re.compile(r"supplier|vendor|provider|manufacturer", re.I),
    ]),
    ("employee", [
        re.compile(r"employee|staff|worker|agent|rep|representative", re.I),
    ]),
    ("address", [
        re.compile(r"address|street|city|state|zip|postal|country", re.I),
    ]),
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cols_matching_entity(cols: list[SourceColumn], patterns: list[re.Pattern]) -> list[SourceColumn]:
    return [c for c in cols if any(p.search(c.source_name) for p in patterns)]


def _col_names(cols: list[SourceColumn]) -> list[str]:
    return [c.source_name for c in cols]


# ── Signal: entity split ──────────────────────────────────────────────────────

def detect_entity_splits(table: SourceTableModel) -> list[ReviewProposal]:
    proposals: list[ReviewProposal] = []

    for entity_label, patterns in _ENTITY_GROUPS:
        matched = _cols_matching_entity(table.columns, patterns)
        if len(matched) < 2:
            continue

        # Check that none of the matched columns is already a FK
        has_fk = any("foreign_key" in c.role_candidates for c in matched)

        # Avoid proposing if there's already a clean FK column for this entity
        fk_col_name = f"{entity_label}_id"
        existing_fk = any(c.canonical_name == fk_col_name for c in table.columns)
        if existing_fk and not has_fk:
            continue

        col_display = ", ".join(c.source_name for c in matched[:5])
        row_word = "rows" if table.row_count != 1 else "row"

        proposals.append(ReviewProposal(
            proposal_type="entity_split",
            title=f"Create a '{entity_label}s' table",
            question=(
                f"The columns [{col_display}] appear together across "
                f"{table.row_count:,} {row_word} in '{table.detected_table_name}'. "
                f"Should these be split into a separate '{entity_label}s' table?"
            ),
            options=[
                f"Yes — create a '{entity_label}s' table with a FK in '{table.detected_table_name}'",
                f"No — keep these columns directly on '{table.detected_table_name}'",
                "Not sure",
            ],
            context={
                "source_table": table.detected_table_name,
                "entity_label": entity_label,
                "matched_columns": [c.canonical_name for c in matched],
            },
            source_evidence=[table.source_id],
            confidence=0.75 + min(len(matched) * 0.05, 0.15),
        ))

    return proposals


# ── Signal: enum → lookup table ───────────────────────────────────────────────

_NON_ENUM_SEMANTIC = {"email", "phone", "person_name", "address", "identifier", "date", "amount"}


def detect_enum_candidates(table: SourceTableModel) -> list[ReviewProposal]:
    proposals: list[ReviewProposal] = []

    for col in table.columns:
        if "enum_candidate" not in col.role_candidates:
            continue
        # Skip columns whose semantic type is clearly not a fixed-list category
        if col.possible_semantic_type in _NON_ENUM_SEMANTIC:
            continue
        # Skip columns that are likely entity identifiers (names, emails)
        if "entity_identifier" in col.role_candidates:
            continue

        values_display = ", ".join(f'"{v}"' for v in col.unique_values[:6])
        if col.cardinality and col.cardinality > 6:
            values_display += f", … ({col.cardinality} total)"

        proposals.append(ReviewProposal(
            proposal_type="enum_to_lookup",
            title=f"'{col.source_name}' — fixed list or open-ended?",
            question=(
                f"'{col.source_name}' in '{table.detected_table_name}' contains "
                f"{col.cardinality or '?'} distinct values: {values_display}. "
                f"Is this list fixed, or can users add new values?"
            ),
            options=[
                f"Fixed list — store as reference/lookup table",
                f"Open-ended — keep as a plain text column",
                "Not sure",
            ],
            context={
                "source_table": table.detected_table_name,
                "column": col.canonical_name,
                "values": col.unique_values,
            },
            source_evidence=[table.source_id],
            confidence=0.82,
        ))

    return proposals


# ── Signal: cross-sheet FK candidates ────────────────────────────────────────

def detect_cross_sheet_fks(tables: list[SourceTableModel]) -> list[ReviewProposal]:
    """
    Two-stage FK detection:
    Stage 1: strip _id suffix → match target table name (same heuristic as before).
    Stage 2: verify target table has a column with the same canonical name that is a
             primary_key_candidate or business_identifier — confidence=0.9 if verified,
             0.5 if only name-matched.
    """
    proposals: list[ReviewProposal] = []

    # Index unique/pk candidate columns by canonical name
    pk_candidates: dict[str, tuple[SourceTableModel, SourceColumn]] = {}
    for table in tables:
        for col in table.columns:
            if "primary_key_candidate" in col.role_candidates or "business_identifier" in col.role_candidates:
                key = col.canonical_name
                if key not in pk_candidates:
                    pk_candidates[key] = (table, col)

    seen: set[str] = set()
    for table in tables:
        for col in table.columns:
            if "foreign_key_candidate" not in col.role_candidates:
                continue
            ref_name = _ID_SUFFIX.sub("", col.canonical_name)
            for pk_key, (pk_table, pk_col) in pk_candidates.items():
                if pk_table.detected_table_name == table.detected_table_name:
                    continue

                # Stage 1: table name match
                stage1 = (pk_table.detected_table_name.startswith(ref_name) or
                          ref_name in pk_table.detected_table_name)
                if not stage1:
                    continue

                # Stage 2: verify target table has a PK/business_key column with matching name
                pk_verified = any(
                    c.canonical_name == col.canonical_name and
                    ("primary_key_candidate" in c.role_candidates or
                     "business_identifier" in c.role_candidates)
                    for c in pk_table.columns
                )

                sig = f"{table.source_id}:{col.canonical_name}->{pk_table.source_id}:{pk_col.canonical_name}"
                if sig in seen:
                    continue
                seen.add(sig)

                confidence = 0.9 if pk_verified else 0.5

                proposals.append(ReviewProposal(
                    proposal_type="foreign_key",
                    title=f"FK: {table.detected_table_name}.{col.canonical_name} → {pk_table.detected_table_name}.{pk_col.canonical_name}",
                    question=(
                        f"'{col.source_name}' in '{table.detected_table_name}' looks like it references "
                        f"'{pk_col.source_name}' in '{pk_table.detected_table_name}'. "
                        f"Should a foreign key constraint be created?"
                    ),
                    options=[
                        "Yes — add a FK constraint",
                        "No — these are not related",
                        "Not sure",
                    ],
                    context={
                        "from_table": table.detected_table_name,
                        "from_column": col.canonical_name,
                        "to_table": pk_table.detected_table_name,
                        "to_column": pk_col.canonical_name,
                        "on_delete": "restrict",
                        "pk_verified": pk_verified,
                    },
                    source_evidence=[table.source_id, pk_table.source_id],
                    confidence=confidence,
                ))

    return proposals


# ── Signal: many-to-many detection ────────────────────────────────────────────

def _singularize(name: str) -> str:
    """
    Singularize a snake_case table name for FK column generation.
    Handles the most common English plural patterns used in database naming.
    """
    if name.endswith("ies") and len(name) > 3:
        return name[:-3] + "y"          # categories → category
    if name.endswith(("ses", "xes", "ches", "shes")):
        return name[:-2]                # addresses → address, boxes → box
    if name.endswith("ves") and len(name) > 4:
        return name[:-3] + "f"          # shelves → shelf (rare in DB context)
    if name.endswith("s") and not name.endswith("ss") and len(name) > 2:
        return name[:-1]                # orders → order, customers → customer
    return name


def _join_table_name(t1: str, t2: str) -> str:
    """Alphabetical singular pair: customers + products → customer_product."""
    s1 = _singularize(t1)
    s2 = _singularize(t2)
    return "_".join(sorted([s1, s2]))


def _infer_ref_table_names(table: SourceTableModel, all_tables: list[SourceTableModel]) -> set[str]:
    """Return the set of table names that this table's FK columns point to."""
    refs: set[str] = set()
    for col in table.columns:
        if "foreign_key_candidate" not in col.role_candidates:
            continue
        ref_name = _ID_SUFFIX.sub("", col.canonical_name)
        for other in all_tables:
            if other.detected_table_name == table.detected_table_name:
                continue
            if (other.detected_table_name.startswith(ref_name) or
                    ref_name in other.detected_table_name):
                refs.add(other.detected_table_name)
    return refs


def detect_many_to_many(tables: list[SourceTableModel]) -> list[ReviewProposal]:
    """
    Detect implicit M2M: two tables that each have FK columns referencing the other.
    Emits a 'many_to_many_join' proposal to create a join table.
    Only fires for tables not already acting as a bridge (bridge tables have their own sheet).
    """
    proposals: list[ReviewProposal] = []

    fk_map: dict[str, set[str]] = {
        t.detected_table_name: _infer_ref_table_names(t, tables)
        for t in tables
    }

    seen_pairs: set[tuple[str, str]] = set()
    for t_name, refs in fk_map.items():
        for ref_name in refs:
            if ref_name not in fk_map:
                continue
            if t_name not in fk_map[ref_name]:
                continue
            # Mutual FK — implicit many-to-many
            pair = tuple(sorted([t_name, ref_name]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            join_name = _join_table_name(pair[0], pair[1])
            sorted_singulars = sorted([_singularize(pair[0]), _singularize(pair[1])])
            from_s, to_s = sorted_singulars[0], sorted_singulars[1]

            proposals.append(ReviewProposal(
                proposal_type="many_to_many_join",
                title=f"Many-to-many: create join table '{join_name}'",
                question=(
                    f"'{pair[0]}' and '{pair[1]}' reference each other with foreign keys, "
                    f"suggesting a many-to-many relationship. "
                    f"Should a join table '{join_name}' be created to resolve this?"
                ),
                options=[
                    f"Accept — create '{join_name}' join table",
                    "Reject — keep as-is",
                    "Not sure",
                ],
                context={
                    "join_name": join_name,
                    "from_table": pair[0],
                    "to_table": pair[1],
                    "from_fk_attr": f"{from_s}_id",
                    "to_fk_attr": f"{to_s}_id",
                },
                confidence=0.80,
            ))

    return proposals


# ── Signal: ERD-level M2M detection (blank canvas path) ───────────────────────

def generate_erd_m2m_proposals(pen: PenFile) -> list[ReviewProposal]:
    """
    Scan ERD relationships for direct many-to-many cardinality and emit pending
    many_to_many_join proposals for any pair that doesn't already have a join entity
    or an existing proposal.

    Called from the PATCH handler to cover the blank-canvas path where no source
    tables exist to run detect_many_to_many() against.
    """
    proposals: list[ReviewProposal] = []

    # Pairs that already have a pending proposal
    existing_pairs: set[tuple[str, str]] = {
        tuple(sorted([str(p.context.get("from_table", "")), str(p.context.get("to_table", ""))]))
        for p in pen.review.proposals
        if p.proposal_type == "many_to_many_join" and p.status == "pending"
    }

    entity_map = {e.id: e for e in pen.erd.entities}
    seen_pairs: set[tuple[str, str]] = set()

    for rel in pen.erd.relationships:
        if rel.cardinality.from_max != "many" or rel.cardinality.to_max != "many":
            continue
        from_ent = entity_map.get(rel.from_.entity_id)
        to_ent = entity_map.get(rel.to.entity_id)
        if not from_ent or not to_ent:
            continue

        pair = tuple(sorted([from_ent.name, to_ent.name]))
        if pair in seen_pairs or pair in existing_pairs:
            continue
        seen_pairs.add(pair)

        # Skip if a join entity already exists (entity with FK rels to both sides)
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

        join_name = _join_table_name(pair[0], pair[1])
        sorted_sings = sorted([_singularize(pair[0]), _singularize(pair[1])])
        from_s, to_s = sorted_sings[0], sorted_sings[1]

        proposals.append(ReviewProposal(
            proposal_type="many_to_many_join",
            title=f"Many-to-many: create join table '{join_name}'",
            question=(
                f"'{from_ent.name}' and '{to_ent.name}' are linked many-to-many. "
                f"Should a join table '{join_name}' be created to resolve this?"
            ),
            options=[
                f"Accept — create '{join_name}' join table",
                "Reject — keep as-is",
                "Not sure",
            ],
            context={
                "join_name": join_name,
                "from_table": pair[0],
                "to_table": pair[1],
                "from_fk_attr": f"{from_s}_id",
                "to_fk_attr": f"{to_s}_id",
            },
            confidence=0.90,
        ))

    return proposals


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_proposals(tables: list[SourceTableModel]) -> list[ReviewProposal]:
    """Run all signal detectors and return de-duplicated proposals."""
    proposals: list[ReviewProposal] = []

    for table in tables:
        proposals.extend(detect_entity_splits(table))
        proposals.extend(detect_enum_candidates(table))

    proposals.extend(detect_cross_sheet_fks(tables))
    proposals.extend(detect_many_to_many(tables))

    return proposals
