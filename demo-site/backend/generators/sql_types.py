"""
sql_types — canonical pg_type list and the sqlglot type-affinity table.

Shared by the SQL importer (sql_import.py) and exporters. The affinity table
collapses every dialect's type zoo onto the small canonical set the PEN model
uses (models/pen.py Attribute.pg_type), because sqlglot already normalizes
spellings (VARCHAR2 / CHARACTER VARYING / NVARCHAR → VARCHAR etc.) at parse
time. Lossy mappings are reported by the importer as type_fallback warnings.
"""
from __future__ import annotations

from sqlglot import exp

PG_CANONICAL_TYPES: list[str] = [
    "uuid", "text", "integer", "bigint", "numeric",
    "boolean", "date", "timestamptz", "jsonb",
]

# Keyed by sqlglot exp.DataType.Type member NAME so missing members in a given
# sqlglot version simply don't register instead of crashing at import time.
_AFFINITY_BY_NAME: dict[str, str] = {
    # integers
    "TINYINT": "integer", "SMALLINT": "integer", "INT": "integer",
    "MEDIUMINT": "integer", "SMALLSERIAL": "integer", "SERIAL": "integer",
    "BIGINT": "bigint", "BIGSERIAL": "bigint",
    "INT128": "bigint", "INT256": "bigint",
    # numerics
    "DECIMAL": "numeric", "BIGDECIMAL": "numeric", "MONEY": "numeric",
    "SMALLMONEY": "numeric", "FLOAT": "numeric", "DOUBLE": "numeric",
    # booleans
    "BOOLEAN": "boolean", "BIT": "boolean",
    # text
    "CHAR": "text", "NCHAR": "text", "VARCHAR": "text", "NVARCHAR": "text",
    "TEXT": "text", "TINYTEXT": "text", "MEDIUMTEXT": "text", "LONGTEXT": "text",
    "ENUM": "text", "SET": "text",
    # dates / times
    "DATE": "date", "DATE32": "date",
    "TIMESTAMP": "timestamptz", "TIMESTAMPTZ": "timestamptz",
    "TIMESTAMPLTZ": "timestamptz", "TIMESTAMPNTZ": "timestamptz",
    "DATETIME": "timestamptz", "DATETIME2": "timestamptz", "DATETIME64": "timestamptz",
    "SMALLDATETIME": "timestamptz",
    "TIME": "timestamptz", "TIMETZ": "timestamptz",
    # ids / documents
    "UUID": "uuid", "UNIQUEIDENTIFIER": "uuid",
    "JSON": "jsonb", "JSONB": "jsonb",
    # binary — no PEN equivalent, importer warns
    "BINARY": "text", "VARBINARY": "text", "BLOB": "text",
    "TINYBLOB": "text", "MEDIUMBLOB": "text", "LONGBLOB": "text",
    "IMAGE": "text", "BYTEA": "text",
}

TYPE_AFFINITY: dict[exp.DataType.Type, str] = {
    member: _AFFINITY_BY_NAME[name]
    for name, member in exp.DataType.Type.__members__.items()
    if name in _AFFINITY_BY_NAME
}

# Type names whose mapping loses information the user should hear about.
LOSSY_TYPE_NAMES: frozenset[str] = frozenset({
    "TIME", "TIMETZ",
    "BINARY", "VARBINARY", "BLOB", "TINYBLOB", "MEDIUMBLOB", "LONGBLOB",
    "IMAGE", "BYTEA",
    "SERIAL", "SMALLSERIAL", "BIGSERIAL",
})


def affinity(dtype: exp.DataType) -> tuple[str, bool]:
    """Map a sqlglot DataType to (pg_type, lossy).

    numeric(p,s) precision is preserved verbatim — it is valid PostgreSQL and
    the exporter emits pg_type raw, so it round-trips. All other parameters
    (varchar lengths etc.) are dropped.
    """
    type_enum = dtype.this
    name = type_enum.name if type_enum is not None else "UNKNOWN"

    if name == "DECIMAL" and dtype.expressions:
        params = ", ".join(e.sql(dialect="postgres") for e in dtype.expressions)
        return f"numeric({params})", False

    pg = TYPE_AFFINITY.get(type_enum)
    if pg is None:
        return "text", True  # user-defined / unknown → text + warning
    return pg, name in LOSSY_TYPE_NAMES
