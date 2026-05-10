"""Deterministic retrieval tools shared by CLI and agent runtime."""

from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass
from typing import Any

from dataroot.kb.base import DocumentRecord


@dataclass
class TableQueryResult:
    row_slug: str
    table_slug: str
    row_data: dict[str, Any]


def query_table(store, table_slug: str, filters: list[dict] | None = None, limit: int = 50) -> list[TableQueryResult]:
    """Query row_group docs belonging to a table."""

    filters = filters or []
    rows = []
    for record in store.list(doc_type="row_group"):
        if record.frontmatter.get("table") != table_slug:
            continue
        row_data = record.frontmatter.get("row_data", {})
        if not isinstance(row_data, dict):
            continue
        if all(_row_matches(row_data, item) for item in filters):
            rows.append(TableQueryResult(row_slug=record.slug, table_slug=table_slug, row_data=row_data))
        if len(rows) >= limit:
            break
    return rows


def find_candidate_paths(
    store,
    start_terms: list[str],
    target_terms: list[str],
    depth: int = 3,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Find short graph paths between search result slugs."""

    starts = _search_slugs(store, start_terms, limit=limit)
    targets = set(_search_slugs(store, target_terms, limit=limit))
    if not starts or not targets:
        return []

    paths = []
    for start in starts:
        path = _bfs_path(store, start, targets, depth)
        if path:
            paths.append({"start": start, "target": path[-1], "path": path, "hops": len(path) - 1})
        if len(paths) >= limit:
            break
    return paths


def rows_for_id(store, identifier: str, limit: int = 25) -> list[TableQueryResult]:
    """Return row_group docs whose row data contains an identifier."""

    identifier_upper = identifier.upper()
    matches = []
    for record in store.list(doc_type="row_group"):
        row_data = record.frontmatter.get("row_data", {})
        if not isinstance(row_data, dict):
            continue
        haystack = " ".join(str(value) for value in row_data.values()).upper()
        if identifier_upper in haystack:
            matches.append(
                TableQueryResult(
                    row_slug=record.slug,
                    table_slug=str(record.frontmatter.get("table", "")),
                    row_data=row_data,
                )
            )
        if len(matches) >= limit:
            break
    return matches


def threshold_exceedances(store, question: str, limit: int = 25) -> list[TableQueryResult]:
    """Find rows where a measurement term in the question exceeds its standard."""

    parameter = _detect_parameter(question)
    if not parameter:
        return []

    threshold = _find_threshold(store, parameter)
    if threshold is None:
        threshold = _number_after_words(question, ["above", "over", "exceed", "exceeded", "greater"])
    if threshold is None:
        return []

    year = _detect_year(question)
    candidate_tables = _tables_with_measurement(store, parameter)
    results: list[TableQueryResult] = []
    for table_slug, column_name in candidate_tables:
        filters = [{"field": column_name, "op": ">", "value": threshold}]
        if year:
            filters.append({"field": "date", "op": "contains", "value": year})
        results.extend(query_table(store, table_slug, filters=filters, limit=limit - len(results)))
        if len(results) >= limit:
            break
    return results


def _row_matches(row_data: dict[str, Any], filter_spec: dict) -> bool:
    field = str(filter_spec.get("field") or filter_spec.get("column") or "")
    op = str(filter_spec.get("op") or filter_spec.get("operator") or "==").lower()
    expected = filter_spec.get("value")
    actual = _field_value(row_data, field)
    if actual is None:
        return False

    if op in {"=", "==", "eq"}:
        return str(actual).lower() == str(expected).lower()
    if op in {"!=", "ne"}:
        return str(actual).lower() != str(expected).lower()
    if op in {"contains", "includes"}:
        return str(expected).lower() in str(actual).lower()
    if op in {">", "gt", ">=", "gte", "<", "lt", "<=", "lte"}:
        actual_num = _as_float(actual)
        expected_num = _as_float(expected)
        if actual_num is None or expected_num is None:
            return False
        if op in {">", "gt"}:
            return actual_num > expected_num
        if op in {">=", "gte"}:
            return actual_num >= expected_num
        if op in {"<", "lt"}:
            return actual_num < expected_num
        return actual_num <= expected_num
    return False


def _field_value(row_data: dict[str, Any], requested: str) -> Any | None:
    requested_norm = _normalize_name(requested)
    for key, value in row_data.items():
        key_norm = _normalize_name(str(key))
        if key_norm == requested_norm:
            return value
    for key, value in row_data.items():
        key_norm = _normalize_name(str(key))
        if requested_norm and requested_norm in key_norm:
            return value
    return None


def _detect_parameter(question: str) -> str | None:
    lower = question.lower()
    for parameter in ["nitrate", "lead", "turbidity", "temperature"]:
        if parameter in lower:
            return parameter
    return None


def _find_threshold(store, parameter: str) -> float | None:
    for table in store.list(doc_type="table"):
        if "standard" not in table.slug.lower():
            continue
        rows = query_table(store, table.slug, filters=[{"field": "parameter", "op": "contains", "value": parameter}])
        for row in rows:
            for key in ["limit_value", "limit", "threshold", "value"]:
                value = _field_value(row.row_data, key)
                number = _as_float(value)
                if number is not None:
                    return number
    return None


def _tables_with_measurement(store, parameter: str) -> list[tuple[str, str]]:
    tables = []
    for column in store.list(doc_type="column"):
        name = str(column.frontmatter.get("name", column.title))
        if parameter not in name.lower():
            continue
        if not column.frontmatter.get("is_likely_measurement"):
            continue
        table = str(column.frontmatter.get("table", ""))
        if table:
            tables.append((table, name))
    return tables


def _detect_year(question: str) -> str | None:
    match = re.search(r"\b(20\d{2}|19\d{2})\b", question)
    return match.group(1) if match else None


def _number_after_words(question: str, words: list[str]) -> float | None:
    for word in words:
        match = re.search(rf"\b{re.escape(word)}\w*\b[^\d]*(\d+(?:\.\d+)?)", question, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _search_slugs(store, terms: list[str], limit: int) -> list[str]:
    slugs = []
    for term in terms:
        for result in store.search(term, limit=limit):
            if result.slug not in slugs:
                slugs.append(result.slug)
    return slugs[:limit]


def _bfs_path(store, start: str, targets: set[str], depth: int) -> list[str] | None:
    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    seen = {start}
    while queue:
        slug, path = queue.popleft()
        if slug in targets:
            return path
        if len(path) - 1 >= depth:
            continue
        graph = store.graph(slug, depth=1)
        neighbors = set()
        for edge in graph.edges:
            if edge.source == slug:
                neighbors.add(edge.target)
            if edge.target == slug:
                neighbors.add(edge.source)
        for neighbor in sorted(neighbors):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            queue.append((neighbor, path + [neighbor]))
    return None


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None
