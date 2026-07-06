"""
sql_import — SQL DDL text → PenFile (DATA-DFM-017).

Parses CREATE TABLE / ALTER TABLE ADD CONSTRAINT / CREATE INDEX /
CREATE TYPE ... AS ENUM / COMMENT ON TABLE into ERD objects via sqlglot,
which normalizes postgres / mysql / sqlite spellings into one AST.

Rules (REQ-DATA-067..070):
- Per-statement error isolation: one bad statement becomes a warning, never a
  whole-import failure. SqlImportError is raised only when zero tables parse.
- Types map through generators.sql_types onto the pg_type canon; lossy
  mappings emit type_fallback warnings.
- FKs resolve in a second pass over collected tables, so forward references
  and trailing ALTER TABLE both work. Cardinality: FK column unique → 1:1,
  else N:1; from_min=0 when the FK column is nullable.
- Finishes through the standard ingest recipe pieces it owns (auto-layout +
  propagate_erd_to_dfd); the route runs apply_rules_gate + ProjectStore.
"""
from __future__ import annotations

import re
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from pydantic import BaseModel, Field

from models.pen import (
    PenFile, SourceRef, Entity, Attribute, IndexDef, Relationship,
    RelationshipEndpoint, RelationshipPostgres, Cardinality,
)
from generators.pen_builder import _auto_layout
from generators.sync_engine import propagate_erd_to_dfd
from generators.sql_types import affinity

IMPORT_DIALECTS = ["postgres", "mysql", "sqlite"]

_FK_ACTION_MAP = {
    "CASCADE": "cascade",
    "SET NULL": "set_null",
    "SET DEFAULT": "set_default",
    "RESTRICT": "restrict",
    "NO ACTION": "no_action",
}

_ENUM_TYPE_RE = re.compile(
    r'CREATE\s+TYPE\s+(?:[\w"]+\.)?("?[\w]+"?)\s+AS\s+ENUM\s*\(([^)]*)\)',
    re.IGNORECASE,
)
_QUOTED_VALUE_RE = re.compile(r"'((?:[^']|'')*)'")

# exp.Alter in sqlglot >= 25, exp.AlterTable before
_ALTER_CLS = getattr(exp, "Alter", None) or getattr(exp, "AlterTable")
_UUID_CLS = getattr(exp, "Uuid", None)


def _default_sql(node: exp.Expression) -> str:
    """Render a DEFAULT expression, keeping the PEN convention for the
    canonical PK/audit defaults (sqlglot would emit GEN_RANDOM_UUID() /
    CURRENT_TIMESTAMP, which are valid but inconsistent with pen_builder)."""
    if _UUID_CLS is not None and isinstance(node, _UUID_CLS):
        return "gen_random_uuid()"
    if isinstance(node, exp.CurrentTimestamp):
        return "now()"
    return node.sql(dialect="postgres", normalize_functions=False)


class SqlImportError(ValueError):
    """No usable CREATE TABLE statements were found."""


class ImportWarningItem(BaseModel):
    code: str      # type_fallback | unsupported_statement | composite_key_collapsed | ...
    message: str
    statement: str | None = None  # offending SQL, truncated


class SqlImportResult(BaseModel):
    pen: PenFile
    warnings: list[ImportWarningItem] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)


# ── Statement splitting (quote/comment-aware, so one bad statement can be
#    isolated instead of poisoning the whole parse) ──────────────────────────

def _split_statements(sql_text: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql_text)
    while i < n:
        ch = sql_text[i]
        two = sql_text[i:i + 2]
        if ch in ("'", '"', "`"):
            end = i + 1
            while end < n:
                if sql_text[end] == ch:
                    if ch == "'" and sql_text[end:end + 2] == "''":
                        end += 2
                        continue
                    break
                end += 1
            buf.append(sql_text[i:end + 1])
            i = end + 1
        elif two == "--":
            end = sql_text.find("\n", i)
            i = n if end == -1 else end
        elif two == "/*":
            end = sql_text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif ch == "$":
            m = re.match(r"\$[\w]*\$", sql_text[i:])
            if m:  # dollar-quoted string
                tag = m.group(0)
                end = sql_text.find(tag, i + len(tag))
                end = n if end == -1 else end + len(tag)
                buf.append(sql_text[i:end])
                i = end
            else:
                buf.append(ch)
                i += 1
        elif ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
        else:
            buf.append(ch)
            i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _snippet(stmt: str, limit: int = 120) -> str:
    flat = " ".join(stmt.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def _detect_dialect(statements: list[str]) -> str:
    best, best_score = IMPORT_DIALECTS[0], (-1, 0)
    for dialect in IMPORT_DIALECTS:
        tables = errors = 0
        for stmt in statements:
            try:
                node = sqlglot.parse_one(stmt, read=dialect)
            except ParseError:
                errors += 1
                continue
            if isinstance(node, exp.Create) and (node.kind or "").upper() == "TABLE":
                tables += 1
        score = (tables, -errors)
        if score > best_score:
            best, best_score = dialect, score
    return best


# ── Import ────────────────────────────────────────────────────────────────────

class _Importer:
    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}          # table name → Entity
        self.enum_types: dict[str, list[str]] = {}      # custom enum type → values
        self.unique_cols: set[tuple[str, str]] = set()  # (table, column)
        self.fk_specs: list[dict[str, Any]] = []
        self.warnings: list[ImportWarningItem] = []
        self.relationships: list[Relationship] = []
        self.stats = {"tables": 0, "columns": 0, "fks": 0, "indexes": 0,
                      "enums": 0, "statements_skipped": 0}

    def warn(self, code: str, message: str, stmt: str | None = None) -> None:
        self.warnings.append(ImportWarningItem(
            code=code, message=message,
            statement=_snippet(stmt) if stmt else None,
        ))

    # — helpers ————————————————————————————————————————————————————————

    def _entity_for(self, table_name: str) -> Entity | None:
        return self.entities.get(table_name.lower())

    @staticmethod
    def _attr_by_name(entity: Entity, col: str) -> Attribute | None:
        return next((a for a in entity.attributes if a.name.lower() == col.lower()), None)

    @staticmethod
    def _pk_attr(entity: Entity) -> Attribute | None:
        return next((a for a in entity.attributes if a.key_role == "primary"), None)

    @staticmethod
    def _fk_actions(*nodes: exp.Expression | None) -> tuple[str, str]:
        on_delete, on_update = "restrict", "no_action"
        for node in nodes:
            if node is None:
                continue
            for key, is_delete in (("delete", True), ("update", False)):
                val = node.args.get(key)
                if val is not None:
                    text = (val if isinstance(val, str) else
                            getattr(val, "name", None) or val.sql()).upper()
                    mapped = _FK_ACTION_MAP.get(text)
                    if mapped:
                        if is_delete:
                            on_delete = mapped
                        else:
                            on_update = mapped
            for opt in node.args.get("options") or []:
                text = (opt if isinstance(opt, str) else opt.sql()).upper()
                for action, mapped in _FK_ACTION_MAP.items():
                    if f"ON DELETE {action}" in text:
                        on_delete = mapped
                    if f"ON UPDATE {action}" in text:
                        on_update = mapped
        return on_delete, on_update

    @staticmethod
    def _identifier_names(node: exp.Expression) -> list[str]:
        names = [c.name for c in node.find_all(exp.Column)]
        if not names:
            names = [i.name for i in node.find_all(exp.Identifier)]
        return names

    # — CREATE TABLE ————————————————————————————————————————————————————

    def handle_create_table(self, create: exp.Create, stmt: str) -> None:
        schema = create.this
        if not isinstance(schema, exp.Schema):
            self.warn("unsupported_statement",
                      "CREATE TABLE without a column list (e.g. CREATE TABLE AS) is not imported.",
                      stmt)
            self.stats["statements_skipped"] += 1
            return
        table_name = schema.this.name
        if not table_name or table_name.lower() in self.entities:
            return

        entity = Entity(
            id=f"ent_{table_name}",
            kind="strong_entity",
            name=table_name,
            display_name=table_name.replace("_", " ").title(),
            confidence=1.0,
            review_status="accepted",
        )
        pk_cols: list[str] = []

        for item in schema.expressions:
            if isinstance(item, exp.ColumnDef):
                attr = self._column(item, entity, stmt)
                entity.attributes.append(attr)
                self.stats["columns"] += 1
                if attr.key_role == "primary":
                    pk_cols.append(attr.name)
            elif isinstance(item, exp.PrimaryKey):
                pk_cols.extend(self._identifier_names(item))
            elif isinstance(item, exp.ForeignKey):
                self._collect_fk(item, table_name, None, stmt)
            elif isinstance(item, exp.Constraint):
                cname = item.name or None
                for inner in item.expressions:
                    if isinstance(inner, exp.PrimaryKey):
                        pk_cols.extend(self._identifier_names(inner))
                    elif isinstance(inner, exp.ForeignKey):
                        self._collect_fk(inner, table_name, cname, stmt)
                    elif isinstance(inner, exp.UniqueColumnConstraint):
                        for col in self._identifier_names(inner):
                            self.unique_cols.add((table_name.lower(), col.lower()))
                    else:
                        self.warn("constraint_skipped",
                                  f"Table constraint on {table_name} not imported: "
                                  f"{_snippet(inner.sql(), 60)}", stmt)
            elif isinstance(item, exp.UniqueColumnConstraint):
                for col in self._identifier_names(item):
                    self.unique_cols.add((table_name.lower(), col.lower()))
            else:
                self.warn("constraint_skipped",
                          f"Table item on {table_name} not imported: "
                          f"{_snippet(item.sql(), 60)}", stmt)

        # Apply PK roles (composite PK collapses to first column + warning)
        seen: list[str] = []
        for col in pk_cols:
            if col.lower() not in [s.lower() for s in seen]:
                seen.append(col)
        for i, col in enumerate(seen):
            attr = self._attr_by_name(entity, col)
            if attr is None:
                continue
            attr.nullable = False
            if i == 0:
                attr.key_role = "primary"
            elif attr.key_role == "none":
                attr.key_role = "business_key"
        if len(seen) > 1:
            self.warn("composite_key_collapsed",
                      f"{table_name}: composite primary key ({', '.join(seen)}) collapsed — "
                      f"'{seen[0]}' kept as primary, the rest marked business_key.", stmt)

        self.entities[table_name.lower()] = entity
        self.stats["tables"] += 1

    def _column(self, coldef: exp.ColumnDef, entity: Entity, stmt: str) -> Attribute:
        name = coldef.name
        dtype = coldef.args.get("kind")

        enum_values: list[str] | None = None
        if dtype is None:
            pg_type, lossy = "text", False  # SQLite allows typeless columns
        else:
            type_text = dtype.sql(dialect="postgres").lower().strip('"')
            if dtype.this == exp.DataType.Type.ENUM and dtype.expressions:
                enum_values = [lit.name for lit in dtype.expressions]
                pg_type, lossy = "text", False
                self.stats["enums"] += 1
            elif type_text in self.enum_types:
                enum_values = self.enum_types[type_text]
                pg_type, lossy = "text", False
                self.stats["enums"] += 1
            else:
                pg_type, lossy = affinity(dtype)
        if lossy:
            self.warn("type_fallback",
                      f"{entity.name}.{name}: type '{dtype.sql()}' mapped to {pg_type}.",
                      stmt)

        attr = Attribute(
            id=f"attr_{entity.name}_{name}",
            name=name,
            display_name=name,
            pg_type=pg_type,
            enum_values=enum_values,
            confidence=1.0,
            review_status="accepted",
        )

        for constraint in coldef.args.get("constraints") or []:
            kind = constraint.kind if isinstance(constraint, exp.ColumnConstraint) else constraint
            if isinstance(kind, exp.PrimaryKeyColumnConstraint):
                attr.key_role = "primary"
                attr.nullable = False
            elif isinstance(kind, exp.NotNullColumnConstraint):
                attr.nullable = bool(kind.args.get("allow_null"))
            elif isinstance(kind, exp.UniqueColumnConstraint):
                if attr.key_role == "none":
                    attr.key_role = "unique"
                self.unique_cols.add((entity.name.lower(), name.lower()))
            elif isinstance(kind, exp.DefaultColumnConstraint):
                attr.default = _default_sql(kind.this)
            elif isinstance(kind, exp.CheckColumnConstraint):
                attr.check_constraint = kind.this.sql(dialect="postgres", normalize_functions=False)
            elif isinstance(kind, (exp.GeneratedAsIdentityColumnConstraint,
                                   exp.AutoIncrementColumnConstraint)):
                if attr.pg_type not in ("integer", "bigint"):
                    attr.pg_type = "integer"
                self.warn("auto_increment",
                          f"{entity.name}.{name}: auto-increment/identity kept as "
                          f"{attr.pg_type}; PEN has no increment flag.", stmt)
            elif isinstance(kind, exp.Reference):
                self._collect_inline_reference(kind, entity.name, name, stmt)
            elif isinstance(kind, exp.CommentColumnConstraint):
                pass  # cosmetic, no PEN field
            else:
                self.warn("constraint_skipped",
                          f"{entity.name}.{name}: constraint not imported: "
                          f"{_snippet(constraint.sql(), 60)}", stmt)
        return attr

    # — FK collection (resolved later, pass 2) ————————————————————————————

    def _collect_inline_reference(self, ref: exp.Reference, child_table: str,
                                  child_col: str, stmt: str) -> None:
        target = ref.this
        if isinstance(target, exp.Schema):
            parent_table = target.this.name
            parent_cols = [i.name for i in target.expressions]
        else:
            parent_table = target.name
            parent_cols = []
        on_delete, on_update = self._fk_actions(ref)
        self.fk_specs.append({
            "child_table": child_table, "child_cols": [child_col],
            "parent_table": parent_table, "parent_cols": parent_cols,
            "name": None, "on_delete": on_delete, "on_update": on_update,
            "stmt": stmt,
        })

    def _collect_fk(self, fk: exp.ForeignKey, child_table: str,
                    constraint_name: str | None, stmt: str) -> None:
        child_cols = [i.name for i in fk.expressions]
        ref = fk.args.get("reference")
        if ref is None:
            self.warn("fk_unresolved",
                      f"{child_table}: FOREIGN KEY without REFERENCES skipped.", stmt)
            return
        target = ref.this
        if isinstance(target, exp.Schema):
            parent_table = target.this.name
            parent_cols = [i.name for i in target.expressions]
        else:
            parent_table = target.name
            parent_cols = []
        on_delete, on_update = self._fk_actions(fk, ref)
        self.fk_specs.append({
            "child_table": child_table, "child_cols": child_cols,
            "parent_table": parent_table, "parent_cols": parent_cols,
            "name": constraint_name, "on_delete": on_delete, "on_update": on_update,
            "stmt": stmt,
        })

    # — other statements ————————————————————————————————————————————————

    def handle_create_index(self, create: exp.Create, stmt: str) -> None:
        index = create.this
        table_node = index.args.get("table") or index.find(exp.Table)
        name = index.name or (index.this.name if index.this is not None else "")
        if table_node is None:
            self.warn("index_unresolved", f"CREATE INDEX {name}: no table found.", stmt)
            return
        entity = self._entity_for(table_node.name)
        if entity is None:
            self.warn("index_unresolved",
                      f"CREATE INDEX {name}: table '{table_node.name}' not in this script.",
                      stmt)
            return
        params = index.args.get("params")
        col_source = params if params is not None else index
        columns = self._identifier_names(col_source)
        attr_ids: list[str] = []
        for col in columns:
            attr = self._attr_by_name(entity, col)
            if attr is None:
                self.warn("index_unresolved",
                          f"Index {name}: column '{col}' not found on {entity.name}.", stmt)
                return
            attr_ids.append(attr.id)
        unique = bool(create.args.get("unique"))
        entity.indexes.append(IndexDef(
            name=name or f"idx_{entity.name}_{'_'.join(columns)}",
            attribute_ids=attr_ids,
            unique=unique,
        ))
        if unique and len(columns) == 1:
            self.unique_cols.add((entity.name.lower(), columns[0].lower()))
        self.stats["indexes"] += 1

    def handle_alter(self, alter: exp.Expression, stmt: str) -> None:
        table = alter.this
        child_table = table.name if table is not None else ""
        fks = list(alter.find_all(exp.ForeignKey))
        if not fks:
            self.warn("unsupported_statement",
                      "ALTER TABLE action not imported (only ADD CONSTRAINT ... FOREIGN KEY is).",
                      stmt)
            self.stats["statements_skipped"] += 1
            return
        constraints = list(alter.find_all(exp.Constraint))
        names = [c.name for c in constraints] if len(constraints) == len(fks) else [None] * len(fks)
        for fk, cname in zip(fks, names):
            self._collect_fk(fk, child_table, cname, stmt)

    def handle_comment(self, comment: exp.Comment, stmt: str) -> None:
        if (comment.args.get("kind") or "").upper() != "TABLE":
            self.warn("unsupported_statement", "Only COMMENT ON TABLE is imported.", stmt)
            return
        entity = self._entity_for(comment.this.name)
        if entity is None:
            self.warn("unsupported_statement",
                      f"COMMENT ON TABLE {comment.this.name}: table not in this script.", stmt)
            return
        text = comment.expression
        entity.description = text.name if text is not None else None

    # — pass 2: FK resolution ————————————————————————————————————————————

    def resolve_fks(self) -> None:
        for spec in self.fk_specs:
            child = self._entity_for(spec["child_table"])
            parent = self._entity_for(spec["parent_table"])
            if child is None or parent is None:
                missing = spec["child_table"] if child is None else spec["parent_table"]
                self.warn("fk_unresolved",
                          f"Foreign key {spec['child_table']} → {spec['parent_table']} "
                          f"skipped: table '{missing}' not in this script.", spec["stmt"])
                continue

            child_cols, parent_cols = spec["child_cols"], spec["parent_cols"]
            if len(child_cols) > 1:
                self.warn("composite_fk_collapsed",
                          f"{child.name} → {parent.name}: composite FK "
                          f"({', '.join(child_cols)}) collapsed to '{child_cols[0]}'.",
                          spec["stmt"])
            child_attr = self._attr_by_name(child, child_cols[0]) if child_cols else None
            if parent_cols:
                parent_attr = self._attr_by_name(parent, parent_cols[0])
            else:
                parent_attr = self._pk_attr(parent)
            if child_attr is None or parent_attr is None:
                self.warn("fk_unresolved",
                          f"Foreign key {child.name} → {parent.name} skipped: "
                          f"column not found.", spec["stmt"])
                continue

            if child_attr.key_role in ("none", "business_key", "unique"):
                child_attr.key_role = "foreign"

            # Cardinality heuristic: unique FK column → 1:1, else N:1
            is_unique = (
                child_attr.key_role == "primary"
                or (child.name.lower(), child_attr.name.lower()) in self.unique_cols
            )
            from_min = 0 if child_attr.nullable else 1
            if is_unique:
                cardinality = Cardinality(from_min=from_min, from_max=1, to_min=1, to_max=1)
            else:
                cardinality = Cardinality(from_min=from_min, from_max="many", to_min=1, to_max=1)

            constraint_name = spec["name"] or f"fk_{child.name}_{child_attr.name}_{parent.name}"
            self.relationships.append(Relationship(**{
                "from": RelationshipEndpoint(entity_id=child.id, attribute_id=child_attr.id),
                "to": RelationshipEndpoint(entity_id=parent.id, attribute_id=parent_attr.id),
                "cardinality": cardinality,
                "postgres": RelationshipPostgres(
                    constraint_name=constraint_name,
                    on_delete=spec["on_delete"],
                    on_update=spec["on_update"],
                ),
                "evidence": [_snippet(spec["stmt"])],
                "confidence": 1.0,
                "review_status": "accepted",
            }))
            self.stats["fks"] += 1


def import_sql(
    sql_text: str,
    dialect: str = "auto",
    project_name: str = "Imported Schema",
    source_name: str = "pasted DDL",
) -> SqlImportResult:
    """Parse SQL DDL into a PenFile. Raises SqlImportError if no tables parse."""
    statements = _split_statements(sql_text)
    if not statements:
        raise SqlImportError("The SQL text contains no statements.")

    if dialect in ("auto", "", None):
        dialect = _detect_dialect(statements)
    read = "mysql" if dialect == "mariadb" else dialect

    imp = _Importer()

    # Pre-scan: CREATE TYPE ... AS ENUM (regex — parser support varies)
    enum_stmt_idx: set[int] = set()
    for i, stmt in enumerate(statements):
        m = _ENUM_TYPE_RE.search(stmt)
        if m:
            type_name = m.group(1).strip('"').lower()
            values = [v.replace("''", "'") for v in _QUOTED_VALUE_RE.findall(m.group(2))]
            if values:
                imp.enum_types[type_name] = values
                enum_stmt_idx.add(i)

    # Pass 1: walk statements
    for i, stmt in enumerate(statements):
        if i in enum_stmt_idx:
            continue
        try:
            node = sqlglot.parse_one(stmt, read=read)
        except ParseError as e:
            imp.warn("parse_error", f"Statement could not be parsed: {e.errors[0]['description'] if e.errors else e}", stmt)
            imp.stats["statements_skipped"] += 1
            continue
        if node is None:
            continue
        if isinstance(node, exp.Create):
            kind = (node.kind or "").upper()
            if kind == "TABLE":
                imp.handle_create_table(node, stmt)
            elif kind == "INDEX":
                imp.handle_create_index(node, stmt)
            else:
                imp.warn("unsupported_statement", f"CREATE {kind} is not imported.", stmt)
                imp.stats["statements_skipped"] += 1
        elif isinstance(node, _ALTER_CLS):
            imp.handle_alter(node, stmt)
        elif isinstance(node, exp.Comment):
            imp.handle_comment(node, stmt)
        else:
            imp.warn("unsupported_statement",
                     f"{node.key.upper() if node.key else 'Statement'} is not imported.", stmt)
            imp.stats["statements_skipped"] += 1

    if not imp.entities:
        raise SqlImportError("No CREATE TABLE statements could be parsed from the SQL text.")

    # Pass 2: resolve FKs (handles forward refs + trailing ALTER TABLE)
    imp.resolve_fks()

    pen = PenFile()
    pen.project.name = project_name
    pen.sources.append(SourceRef(id="src_0", type="text", name=source_name))
    pen.erd.entities = list(imp.entities.values())
    pen.erd.relationships = imp.relationships
    pen.postgres.extensions = []  # imported schemas manage their own extensions
    pen.layout.erd = _auto_layout(pen.erd.entities)
    propagate_erd_to_dfd(pen)

    return SqlImportResult(pen=pen, warnings=imp.warnings, stats=imp.stats)
