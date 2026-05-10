"""Deterministic KB linker."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass

from dataroot.kb.base import DocumentRecord
from dataroot.kb.markdown import append_links, record_to_markdown
from dataroot.link.address_match import address_key

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{0,4}(?:-[A-Z0-9]{1,10}){1,6}\b|\bstation[_-]?\d{2,4}\b", re.IGNORECASE)
ADDRESS_COLUMN_RE = re.compile(r"(?:^|_)(?:address|street_address|site_address|property_address|location_address)$", re.IGNORECASE)


@dataclass
class LinkSummary:
    relationship_docs: int
    documents_updated: int
    links_added: int


def link_workspace(store) -> LinkSummary:
    records = store.list()
    records_by_slug = {record.slug: record for record in records}
    links_by_slug: dict[str, list[tuple[str, str]]] = defaultdict(list)

    _add_structural_links(records, links_by_slug)
    id_map = _collect_id_mentions(records)
    relationship_docs = _write_relationship_docs(store, id_map)
    _add_relationship_links(id_map, links_by_slug)
    _add_column_overlap_links(records, links_by_slug)

    if _address_join_enabled():
        address_map = _collect_address_mentions(records)
        relationship_docs += _write_address_relationship_docs(store, address_map)
        _add_address_relationship_links(address_map, links_by_slug)

    updates = 0
    added = 0
    for slug, links in sorted(links_by_slug.items()):
        record = records_by_slug.get(slug)
        if not record:
            continue
        content = record_to_markdown(record)
        updated = append_links(content, links)
        if updated != content:
            store.update(slug, updated)
            updates += 1
            added += len(links)

    store.commit("Link DataRoot workspace")
    return LinkSummary(relationship_docs=relationship_docs, documents_updated=updates, links_added=added)


def _add_structural_links(records: list[DocumentRecord], links_by_slug: dict[str, list[tuple[str, str]]]) -> None:
    tables_by_source: dict[str, list[DocumentRecord]] = defaultdict(list)
    columns_by_table: dict[str, list[DocumentRecord]] = defaultdict(list)
    rows_by_table: dict[str, list[DocumentRecord]] = defaultdict(list)
    measurements_by_column: dict[str, list[DocumentRecord]] = defaultdict(list)
    measurements_by_table: dict[str, list[DocumentRecord]] = defaultdict(list)

    for record in records:
        if record.doc_type == "table":
            source = str(record.frontmatter.get("source_file", ""))
            if source:
                tables_by_source[source].append(record)
        elif record.doc_type == "column":
            table = str(record.frontmatter.get("table", ""))
            if table:
                columns_by_table[table].append(record)
        elif record.doc_type == "row_group":
            table = str(record.frontmatter.get("table", ""))
            if table:
                rows_by_table[table].append(record)
        elif record.doc_type == "measurement":
            column = str(record.frontmatter.get("column", ""))
            table = str(record.frontmatter.get("table", ""))
            if column:
                measurements_by_column[column].append(record)
            if table:
                measurements_by_table[table].append(record)

    for source, tables in tables_by_source.items():
        for table in tables:
            links_by_slug[source].append((table.slug, "contains table"))
            links_by_slug[table.slug].append((source, "source file"))

    for table, columns in columns_by_table.items():
        for column in columns:
            links_by_slug[table].append((column.slug, "has column"))
            links_by_slug[column.slug].append((table, "belongs to table"))

    for table, rows in rows_by_table.items():
        for row in rows:
            links_by_slug[table].append((row.slug, "has row"))
            links_by_slug[row.slug].append((table, "row from table"))

    for column, measurements in measurements_by_column.items():
        for measurement in measurements:
            links_by_slug[column].append((measurement.slug, "measures"))
            links_by_slug[measurement.slug].append((column, "measurement column"))

    for table, measurements in measurements_by_table.items():
        for measurement in measurements:
            links_by_slug[table].append((measurement.slug, "has measurement"))
            links_by_slug[measurement.slug].append((table, "measurement table"))


def _collect_id_mentions(records: list[DocumentRecord]) -> dict[str, list[str]]:
    id_map: dict[str, list[str]] = defaultdict(list)
    for record in records:
        haystack = " ".join([record.slug, record.title, json.dumps(record.frontmatter, default=str), record.body])
        for value in sorted(set(ID_RE.findall(haystack))):
            normalized = value.upper()
            if record.slug not in id_map[normalized]:
                id_map[normalized].append(record.slug)
    return {key: slugs for key, slugs in id_map.items() if len(slugs) > 1}


def _write_relationship_docs(store, id_map: dict[str, list[str]]) -> int:
    count = 0
    existing = {record.slug for record in store.list(doc_type="relationship")}
    for value, slugs in sorted(id_map.items()):
        slug = f"relationships/{_slug_id(value)}"
        body = "\n".join(
            [
                f"# {value}",
                "",
                "Documents mentioning this ID:",
                *[f"- [[{doc_slug}]]" for doc_slug in sorted(slugs)],
            ]
        )
        record = DocumentRecord(
            doc_type="relationship",
            slug=slug,
            title=value,
            frontmatter={
                "relationship_type": "repeated_id",
                "id_value": value,
                "document_count": len(slugs),
                "documents": sorted(slugs),
                "confidence": 0.7,
            },
            body=body,
        )
        if slug not in existing:
            store.write(record)
            count += 1
    return count


def _add_relationship_links(id_map: dict[str, list[str]], links_by_slug: dict[str, list[tuple[str, str]]]) -> None:
    for value, slugs in id_map.items():
        relationship_slug = f"relationships/{_slug_id(value)}"
        for doc_slug in slugs:
            links_by_slug[doc_slug].append((relationship_slug, f"mentions {value}"))


def _add_column_overlap_links(records: list[DocumentRecord], links_by_slug: dict[str, list[tuple[str, str]]]) -> None:
    columns = [record for record in records if record.doc_type == "column"]
    for source in columns:
        source_values = set(str(value) for value in source.frontmatter.get("sample_values", []) if value)
        if not source_values:
            continue
        for target in columns:
            if source.slug == target.slug:
                continue
            target_values = set(str(value) for value in target.frontmatter.get("sample_values", []) if value)
            if not target_values:
                continue
            name_match = source.frontmatter.get("name") == target.frontmatter.get("name")
            overlap = source_values & target_values
            if not name_match and not overlap:
                continue
            if name_match or len(overlap) >= 2:
                links_by_slug[source.slug].append((target.slug, "candidate FK"))


def _slug_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._/-]+", "_", value.strip().lower()).strip("_")


def _address_join_enabled() -> bool:
    return os.environ.get("DATAROOT_LINK_ADDRESS_JOIN", "0") == "1"


def _collect_address_mentions(records: list[DocumentRecord]) -> dict[str, list[tuple[str, str]]]:
    """Map ``address_key`` -> list of (row_group_slug, source_table)."""
    address_map: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for record in records:
        if record.doc_type != "row_group":
            continue
        if record.frontmatter.get("row_grouping") != "single_row":
            continue
        row = record.frontmatter.get("row_data") or {}
        if not isinstance(row, dict):
            continue
        table = str(record.frontmatter.get("table", ""))
        for column_name, value in row.items():
            if not isinstance(column_name, str):
                continue
            if not ADDRESS_COLUMN_RE.search(column_name):
                continue
            key = address_key(value)
            if not key:
                continue
            entry = (record.slug, table)
            if entry not in address_map[key]:
                address_map[key].append(entry)
            break
    return {key: entries for key, entries in address_map.items() if len({table for _, table in entries}) > 1}


def _write_address_relationship_docs(store, address_map: dict[str, list[tuple[str, str]]]) -> int:
    count = 0
    existing = {record.slug for record in store.list(doc_type="relationship")}
    for key, entries in sorted(address_map.items()):
        slug = f"relationships/address__{_slug_id(key)}"
        slugs = sorted({entry[0] for entry in entries})
        tables = sorted({entry[1] for entry in entries if entry[1]})
        body = "\n".join(
            [
                f"# {key}",
                "",
                "Documents whose normalized address matches this key:",
                *[f"- [[{doc_slug}]]" for doc_slug in slugs],
            ]
        )
        record = DocumentRecord(
            doc_type="relationship",
            slug=slug,
            title=key,
            frontmatter={
                "relationship_type": "shared_address",
                "address_key": key,
                "document_count": len(slugs),
                "documents": slugs,
                "source_tables": tables,
                "confidence": 0.6,
            },
            body=body,
        )
        if slug not in existing:
            store.write(record)
            count += 1
    return count


def _add_address_relationship_links(
    address_map: dict[str, list[tuple[str, str]]],
    links_by_slug: dict[str, list[tuple[str, str]]],
) -> None:
    for key, entries in address_map.items():
        relationship_slug = f"relationships/address__{_slug_id(key)}"
        for doc_slug, _table in entries:
            links_by_slug[doc_slug].append((relationship_slug, f"shares address {key}"))
