"""SQL DDL importer tests (DATA-DFM-017, REQ-DATA-067..070)."""
from pathlib import Path

import pytest
import sqlglot

from generators.sql import export_sql
from generators.sql_import import SqlImportError, import_sql
from models.pen import Entity, PenFile

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "ddl"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _entity(pen: PenFile, name: str) -> Entity:
    ent = next((e for e in pen.erd.entities if e.name == name), None)
    assert ent is not None, f"entity {name} missing (have: {[e.name for e in pen.erd.entities]})"
    return ent


def _attr(entity: Entity, name: str):
    attr = next((a for a in entity.attributes if a.name == name), None)
    assert attr is not None, f"attribute {name} missing on {entity.name}"
    return attr


# ── postgres, inline FKs ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def postgres_inline_result():
    return import_sql(_load("postgres_inline_fk.sql"), dialect="postgres")


class TestPostgresInline:
    @pytest.fixture
    def result(self, postgres_inline_result):
        return postgres_inline_result

    def test_tables_and_columns(self, result):
        pen = result.pen
        assert result.stats["tables"] == 3
        customers = _entity(pen, "customers")
        assert _attr(customers, "id").key_role == "primary"
        assert _attr(customers, "id").default == "gen_random_uuid()"
        email = _attr(customers, "email")
        assert email.key_role == "unique"
        assert email.nullable is False
        assert _attr(customers, "full_name").pg_type == "text"  # varchar(255) affinity
        assert _attr(customers, "created_at").pg_type == "timestamptz"

    def test_numeric_precision_preserved(self, result):
        total = _attr(_entity(result.pen, "orders"), "total")
        assert total.pg_type == "numeric(10, 2)"
        assert total.check_constraint == "total >= 0"

    def test_enum_type_resolved(self, result):
        status = _attr(_entity(result.pen, "orders"), "status")
        assert status.pg_type == "text"
        assert status.enum_values == ["pending", "paid", "shipped"]

    def test_relationships(self, result):
        pen = result.pen
        assert result.stats["fks"] == 2
        orders = _entity(pen, "orders")
        customers = _entity(pen, "customers")
        rel = next(r for r in pen.erd.relationships if r.from_.entity_id == orders.id)
        assert rel.to.entity_id == customers.id
        assert rel.postgres.on_delete == "cascade"
        assert _attr(orders, "customer_id").key_role == "foreign"
        # N:1 — FK column is not unique
        assert rel.cardinality.from_max == "many"
        assert rel.cardinality.from_min == 1  # NOT NULL FK

    def test_unique_fk_is_one_to_one(self, result):
        pen = result.pen
        profiles = _entity(pen, "customer_profiles")
        rel = next(r for r in pen.erd.relationships if r.from_.entity_id == profiles.id)
        assert rel.cardinality.from_max == 1

    def test_indexes(self, result):
        pen = result.pen
        orders = _entity(pen, "orders")
        assert any(i.name == "idx_orders_customer" for i in orders.indexes)
        customers = _entity(pen, "customers")
        email_idx = next(i for i in customers.indexes if i.name == "idx_customers_email")
        assert email_idx.unique is True
        assert email_idx.attribute_ids == [_attr(customers, "email").id]

    def test_table_comment(self, result):
        assert _entity(result.pen, "orders").description == "Customer purchase orders"

    def test_layout_and_dfd_propagated(self, result):
        pen = result.pen
        layout_ids = {n.id for n in pen.layout.erd.nodes}
        assert {e.id for e in pen.erd.entities} <= layout_ids
        store_targets = {s.mapped_erd_entity for s in pen.dfd.data_stores}
        assert {e.id for e in pen.erd.entities} <= store_targets


# ── postgres, trailing ALTER TABLE + forward reference ───────────────────────

def test_alter_table_fk_with_forward_reference():
    result = import_sql(_load("postgres_alter_fk.sql"), dialect="postgres")
    pen = result.pen
    assert result.stats["fks"] == 1
    line_items = _entity(pen, "line_items")
    invoices = _entity(pen, "invoices")
    rel = pen.erd.relationships[0]
    assert rel.from_.entity_id == line_items.id
    assert rel.to.entity_id == invoices.id
    assert rel.postgres.constraint_name == "fk_line_items_invoice"
    assert rel.postgres.on_delete == "cascade"
    assert _attr(line_items, "invoice_id").key_role == "foreign"


# ── mysql ─────────────────────────────────────────────────────────────────────

def test_mysql_dialect():
    result = import_sql(_load("mysql.sql"), dialect="mysql")
    pen = result.pen
    authors = _entity(pen, "authors")
    books = _entity(pen, "books")
    assert _attr(authors, "id").key_role == "primary"
    assert _attr(authors, "id").pg_type == "integer"
    country = _attr(authors, "country")
    assert country.enum_values == ["us", "uk", "other"]
    rel = pen.erd.relationships[0]
    assert rel.from_.entity_id == books.id
    assert rel.postgres.constraint_name == "fk_books_author"
    assert rel.postgres.on_delete == "cascade"
    assert any(w.code == "auto_increment" for w in result.warnings)


# ── sqlite ────────────────────────────────────────────────────────────────────

def test_sqlite_dialect():
    result = import_sql(_load("sqlite.sql"), dialect="sqlite")
    pen = result.pen
    tracks = _entity(pen, "tracks")
    assert _attr(tracks, "playlist_id").key_role == "foreign"
    assert result.stats["fks"] == 1


# ── auto-detect ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fixture,expected_table", [
    ("postgres_inline_fk.sql", "customers"),
    ("mysql.sql", "authors"),
    ("sqlite.sql", "playlists"),
])
def test_auto_detect(fixture, expected_table):
    result = import_sql(_load(fixture), dialect="auto")
    _entity(result.pen, expected_table)


# ── messy input: warnings, never fatal ────────────────────────────────────────

def test_messy_script_warns_but_imports():
    result = import_sql(_load("messy.sql"), dialect="postgres")
    pen = result.pen
    assert result.stats["tables"] == 2
    assert {e.name for e in pen.erd.entities} == {"widgets", "crates"}
    skipped = {w.code for w in result.warnings}
    assert "unsupported_statement" in skipped
    rel = pen.erd.relationships[0]
    assert rel.postgres.on_delete == "set_null"
    assert rel.cardinality.from_min == 0  # nullable FK


def test_zero_tables_raises():
    with pytest.raises(SqlImportError):
        import_sql("SELECT 1; INSERT INTO x VALUES (1);", dialect="postgres")


def test_garbage_statement_is_isolated():
    sql = "CREATE TABLE ok (id uuid PRIMARY KEY);\nTHIS IS NOT SQL AT ALL;\n"
    result = import_sql(sql, dialect="postgres")
    assert result.stats["tables"] == 1
    assert any(w.code in ("parse_error", "unsupported_statement") for w in result.warnings)


# ── round trip: import → export re-parses clean under postgres ───────────────

@pytest.mark.parametrize("fixture", [
    "postgres_inline_fk.sql", "postgres_alter_fk.sql", "mysql.sql", "sqlite.sql",
])
def test_round_trip(fixture):
    pen = import_sql(_load(fixture), dialect="auto").pen
    sql = export_sql(pen)
    assert not sql.startswith("-- SQLGlot validation warning")
    parsed = sqlglot.parse(sql, dialect="postgres")
    creates = [p for p in parsed if p is not None and isinstance(p, sqlglot.exp.Create)]
    assert len(creates) >= len(pen.erd.entities)
