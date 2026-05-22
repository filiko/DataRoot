"""
Column profiler — deterministic type inference and role detection.
Called by both Excel and CSV parsers with raw column data.
"""
from __future__ import annotations

import re
from typing import Any

from slugify import slugify


# ── Type inference ────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
_DATE_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}$"
    r"|^\d{2}[-/]\d{2}[-/]\d{4}$"
)
_DATETIME_RE = re.compile(
    r"^\d{4}[-/]\d{2}[-/]\d{2}[\sT]\d{2}:\d{2}"
)
_PHONE_RE = re.compile(r"^[\+\d\s\(\)\-\.]{7,20}$")


def _try_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return True
    if isinstance(v, str):
        return v.lower() in ("true", "false", "yes", "no", "1", "0", "y", "n")
    return False


def _infer_single(v: Any) -> str:
    if v is None or (isinstance(v, float) and v != v):  # NaN
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "float"
    if hasattr(v, "date"):  # datetime / date objects from openpyxl
        if hasattr(v, "hour"):
            return "datetime"
        return "date"
    s = str(v).strip()
    if not s:
        return "null"
    if _UUID_RE.match(s):
        return "uuid"
    if _EMAIL_RE.match(s):
        return "email"
    if _DATETIME_RE.match(s):
        return "datetime"
    if _DATE_RE.match(s):
        return "date"
    try:
        int(s.replace(",", "").replace("_", ""))
        return "integer"
    except ValueError:
        pass
    try:
        float(s.replace(",", "").replace("_", ""))
        return "float"
    except ValueError:
        pass
    if _try_bool(s):
        return "boolean"
    if _PHONE_RE.match(s) and any(c.isdigit() for c in s):
        return "phone"
    return "string"


def infer_column_type(values: list[Any]) -> str:
    """Return the dominant non-null type for a list of cell values."""
    type_counts: dict[str, int] = {}
    for v in values:
        t = _infer_single(v)
        if t != "null":
            type_counts[t] = type_counts.get(t, 0) + 1
    if not type_counts:
        return "string"
    # Priority: uuid > email > datetime > date > boolean > integer > float > phone > string
    priority = ["uuid", "email", "datetime", "date", "boolean", "integer", "float", "phone", "string"]
    for p in priority:
        if p in type_counts:
            # Only use this type if it accounts for >70% of non-null values
            total = sum(type_counts.values())
            if type_counts[p] / total > 0.70:
                return p
    return "string"


# ── Semantic type hint ────────────────────────────────────────────────────────

_ID_SUFFIXES = re.compile(r"(_id|_ID|Id|ID)$")
_NAME_WORDS = re.compile(r"\b(name|first|last|full|given|surname)\b", re.I)
_EMAIL_WORDS = re.compile(r"\b(email|e-?mail|address)\b", re.I)
_PHONE_WORDS = re.compile(r"\b(phone|mobile|cell|fax|tel)\b", re.I)
_AMOUNT_WORDS = re.compile(r"\b(amount|total|price|cost|fee|revenue|salary|balance)\b", re.I)
_STATUS_WORDS = re.compile(r"\b(status|state|stage|phase|condition)\b", re.I)
_DATE_WORDS = re.compile(r"\b(date|day|time|at|on|created|updated|modified|timestamp)\b", re.I)
_ADDR_WORDS = re.compile(r"\b(address|street|city|state|zip|postal|country|region)\b", re.I)


def guess_semantic_type(col_name: str, inferred_type: str) -> str | None:
    n = col_name.lower()
    if inferred_type == "email" or _EMAIL_WORDS.search(n):
        return "email"
    if inferred_type == "uuid" or _ID_SUFFIXES.search(col_name):
        return "identifier"
    if _PHONE_WORDS.search(n) or inferred_type == "phone":
        return "phone"
    if _NAME_WORDS.search(n):
        return "person_name"
    if _AMOUNT_WORDS.search(n):
        return "amount"
    if _STATUS_WORDS.search(n):
        return "status"
    if inferred_type in ("date", "datetime") or _DATE_WORDS.search(n):
        return "date"
    if _ADDR_WORDS.search(n):
        return "address"
    return None


# ── Role candidates ───────────────────────────────────────────────────────────

def detect_role_candidates(
    col_name: str,
    inferred_type: str,
    null_rate: float,
    unique_rate: float,
    cardinality: int | None,
    row_count: int,
) -> list[str]:
    roles: list[str] = []
    n = col_name.lower()

    if unique_rate >= 0.99 and null_rate == 0.0:
        if _ID_SUFFIXES.search(col_name) or "id" in n.split("_"):
            roles.append("primary_key_candidate")
        else:
            roles.append("business_identifier")

    if _ID_SUFFIXES.search(col_name) and unique_rate < 0.99:
        roles.append("foreign_key_candidate")

    if cardinality is not None and cardinality <= 20 and inferred_type == "string" and unique_rate < 0.95:
        roles.append("enum_candidate")

    if inferred_type == "email" or guess_semantic_type(col_name, inferred_type) in ("email", "person_name"):
        roles.append("entity_identifier")

    if _DATE_WORDS.search(n) and ("created" in n or "updated" in n or "modified" in n):
        roles.append("audit")

    if not roles:
        roles.append("attribute")

    return roles


# ── Canonical name ────────────────────────────────────────────────────────────

def to_canonical_name(raw: str) -> str:
    """Convert any column header to a snake_case identifier."""
    # Use slugify with underscore separator, then clean up
    name = slugify(str(raw), separator="_", lowercase=True)
    # Remove leading digits
    name = re.sub(r"^[0-9_]+", "", name)
    return name or "column"


# ── Full column profile ───────────────────────────────────────────────────────

def profile_column(col_name: str, values: list[Any]) -> dict:
    """
    Given raw cell values for one column, return a dict matching SourceColumn fields.
    """
    non_null = [v for v in values if v is not None and str(v).strip() != ""]
    row_count = len(values)
    null_count = row_count - len(non_null)

    null_rate = null_count / row_count if row_count else 0.0

    distinct = set(str(v) for v in non_null)
    unique_rate = len(distinct) / len(non_null) if non_null else 0.0

    inferred_type = infer_column_type(non_null)

    cardinality: int | None = None
    unique_values: list = []
    if len(distinct) <= 50:
        cardinality = len(distinct)
    if len(distinct) <= 20:
        unique_values = sorted(distinct)[:20]

    sample_values = []
    for v in non_null[:5]:
        sample_values.append(str(v))

    canonical_name = to_canonical_name(col_name)
    roles = detect_role_candidates(col_name, inferred_type, null_rate, unique_rate, cardinality, row_count)
    semantic = guess_semantic_type(col_name, inferred_type)

    return {
        "source_name": col_name,
        "canonical_name": canonical_name,
        "inferred_type": inferred_type,
        "null_rate": round(null_rate, 4),
        "unique_rate": round(unique_rate, 4),
        "cardinality": cardinality,
        "unique_values": unique_values,
        "sample_values": sample_values,
        "role_candidates": roles,
        "possible_semantic_type": semantic,
    }
