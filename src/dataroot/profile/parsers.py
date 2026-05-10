"""File parsers for the workspace profiler."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dataroot.kb.base import DocumentRecord
from dataroot.kb.markdown import extract_wikilinks, split_frontmatter

from .slug import candidate_slug, column_slug, measurement_slug, relative_slug, row_group_slug, source_slug, table_slug

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{0,4}(?:-[A-Z0-9]{1,10}){1,6}\b|\bstation[_-]?\d{2,4}\b", re.IGNORECASE)
UNIT_HINTS = {
    "mg_l": "mg/L",
    "mg/l": "mg/L",
    "ppm": "ppm",
    "ppb": "ppb",
    "pct": "percent",
    "percent": "percent",
    "kg": "kg",
    "days": "days",
    "celsius": "C",
    "temperature": "C",
}
MAX_ROW_DOCS_PER_TABLE = 500
ROW_CHUNK_SIZE = 500


@dataclass
class ParsedFile:
    records: list[DocumentRecord]


def parse_file(root: Path, path: Path) -> ParsedFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return parse_csv(root, path)
    if suffix == ".json":
        return parse_json(root, path)
    if suffix in {".fasta", ".fa", ".fna"}:
        return parse_fasta(root, path)
    if suffix in {".md", ".txt"}:
        return parse_text(root, path)
    if suffix == ".xlsx":
        return parse_xlsx(root, path)
    return parse_unknown(root, path)


def parse_csv(root: Path, path: Path) -> ParsedFile:
    rel = relative_slug(root, path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    table_records = _table_records(root, path, rel, rows)
    return ParsedFile([_source_record(root, path, rel, "csv", rows)] + table_records)


def parse_json(root: Path, path: Path) -> ParsedFile:
    rel = relative_slug(root, path)
    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    if isinstance(data, list) and all(isinstance(item, dict) for item in data):
        rows = [_flatten_json(dict(item)) for item in data]
    elif isinstance(data, dict):
        rows = [_flatten_json(data)]
    else:
        rows = [{"value": data}]
    records = [_source_record(root, path, rel, "json", rows)] + _table_records(root, path, rel, rows)
    records.extend(_json_candidate_records(rel, rows))
    return ParsedFile(records)


def parse_fasta(root: Path, path: Path) -> ParsedFile:
    rel = relative_slug(root, path)
    text = path.read_text(encoding="utf-8")
    records = [_source_record(root, path, rel, "fasta", [])]
    for index, entry in enumerate(_fasta_entries(text), start=1):
        header, sequence = entry
        parsed = _parse_fasta_header(header)
        title = parsed.get("id") or header.split("|", 1)[0] or f"entry_{index}"
        slug = candidate_slug(rel, str(title))
        body = "\n".join(
            [
                f"# {title}",
                "",
                f"Source: [[{source_slug(rel)}]]",
                "",
                "Header:",
                f"`{header}`",
                "",
                "Sequence sample:",
                f"`{sequence[:240]}`",
            ]
        )
        records.append(
            DocumentRecord(
                doc_type="candidate_entity",
                slug=slug,
                title=str(title),
                frontmatter={
                    "detected_from": "fasta_header",
                    "source_file": source_slug(rel),
                    "source_path": rel,
                    "raw_value": header,
                    "fields": parsed,
                    "sequence_length": len(sequence),
                },
                body=body,
            )
        )
    return ParsedFile(records)


def parse_text(root: Path, path: Path) -> ParsedFile:
    rel = relative_slug(root, path)
    text = path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    source = _source_record(root, path, rel, path.suffix.lower().lstrip(".") or "text", [])
    if frontmatter:
        source.frontmatter["parsed_frontmatter"] = frontmatter
    source.frontmatter["wikilinks"] = extract_wikilinks(body)
    records = [source]
    for table_index, rows in enumerate(_markdown_tables(body), start=1):
        records.extend(_table_records(root, path, f"{rel}/table_{table_index}", rows))
    for value in sorted(set(ID_RE.findall(body))):
        records.append(
            DocumentRecord(
                doc_type="candidate_entity",
                slug=candidate_slug(rel, value),
                title=value,
                frontmatter={
                    "detected_from": "text_mention",
                    "source_file": source_slug(rel),
                    "source_path": rel,
                    "raw_value": value,
                },
                body=f"# {value}\n\nDetected in [[{source_slug(rel)}]].",
            )
        )
    for wikilink in extract_wikilinks(body):
        records.append(
            DocumentRecord(
                doc_type="candidate_entity",
                slug=candidate_slug(rel, f"wikilink/{wikilink}"),
                title=wikilink,
                frontmatter={
                    "detected_from": "wikilink",
                    "source_file": source_slug(rel),
                    "source_path": rel,
                    "target_slug": wikilink,
                },
                body=f"# {wikilink}\n\nWikilink target detected in [[{source_slug(rel)}]].\n\nTarget: [[{wikilink}]]",
            )
        )
    return ParsedFile(records)


def parse_xlsx(root: Path, path: Path) -> ParsedFile:
    try:
        import openpyxl
    except ImportError:
        return parse_unknown(root, path)

    rel = relative_slug(root, path)
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    records = [_source_record(root, path, rel, "xlsx", [])]
    for sheet in workbook.worksheets:
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            headers = [str(value or "") for value in next(rows_iter)]
        except StopIteration:
            continue
        rows = []
        for values in rows_iter:
            rows.append({headers[index]: values[index] for index in range(len(headers)) if headers[index]})
        sheet_rel = f"{rel}/{sheet.title}"
        records.extend(_table_records(root, path, sheet_rel, rows))
    return ParsedFile(records)


def parse_unknown(root: Path, path: Path) -> ParsedFile:
    rel = relative_slug(root, path)
    return ParsedFile([_source_record(root, path, rel, path.suffix.lower().lstrip(".") or "unknown", [])])


def _source_record(root: Path, path: Path, rel: str, file_type: str, rows: list[dict]) -> DocumentRecord:
    body_lines = [
        f"# {path.name}",
        "",
        f"Path: `{rel}`",
        f"File type: `{file_type}`",
    ]
    if rows:
        body_lines.append(f"Rows parsed: {len(rows)}")
        body_lines.append("")
        body_lines.append(f"Table: [[{table_slug(rel)}]]")
    return DocumentRecord(
        doc_type="source_file",
        slug=source_slug(rel),
        title=path.name,
        frontmatter={
            "path": rel,
            "size_bytes": path.stat().st_size,
            "file_type": file_type,
            "row_count": len(rows),
        },
        body="\n".join(body_lines),
    )


def _table_records(root: Path, path: Path, rel: str, rows: list[dict]) -> list[DocumentRecord]:
    headers = _headers(rows)
    table = table_slug(rel)
    source = source_slug(relative_slug(root, path))
    column_docs = [column_slug(rel, name) for name in headers]
    records = [
        DocumentRecord(
            doc_type="table",
            slug=table,
            title=Path(rel).name,
            frontmatter={
                "source_file": source,
                "path": rel,
                "row_count": len(rows),
                "column_count": len(headers),
                "header_row": headers,
                "sample_rows": rows[:5],
            },
            body=_table_body(table, source, column_docs, rows[:5]),
        )
    ]

    stats = _column_stats(rows, headers)
    for name in headers:
        info = stats[name]
        col_slug = column_slug(rel, name)
        records.append(
            DocumentRecord(
                doc_type="column",
                slug=col_slug,
                title=name,
                frontmatter={
                    "table": table,
                    "source_file": source,
                    "name": name,
                    "inferred_type": info["inferred_type"],
                    "null_pct": info["null_pct"],
                    "unique_count": info["unique_count"],
                    "is_likely_pk": info["is_likely_pk"],
                    "is_likely_fk": info["is_likely_fk"],
                    "is_likely_measurement": info["is_likely_measurement"],
                    "unit": info["unit"],
                    "sample_values": info["sample_values"],
                },
                body=_column_body(name, table, info),
            )
        )
        if info["is_likely_measurement"]:
            records.append(_measurement_record(rel, name, table, col_slug, source, info))

    id_column = _best_identifier_column(headers, stats)
    if id_column:
        records.extend(_row_group_records(rel, table, source, id_column, rows))

    return records


def _row_group_records(rel: str, table: str, source: str, id_column: str, rows: list[dict]) -> list[DocumentRecord]:
    records = []
    for index, row in enumerate(rows[:MAX_ROW_DOCS_PER_TABLE], start=1):
        value = str(row.get(id_column, "")).strip()
        if not value:
            continue
        records.append(
            DocumentRecord(
                doc_type="row_group",
                slug=row_group_slug(rel, value),
                title=value,
                frontmatter={
                    "table": table,
                    "source_file": source,
                    "row_index": index,
                    "key_column": id_column,
                    "key_value": value,
                    "row_data": row,
                    "row_grouping": "single_row",
                },
                body=_row_body(value, table, row),
            )
        )

    if len(rows) <= MAX_ROW_DOCS_PER_TABLE:
        return records

    for chunk_start in range(MAX_ROW_DOCS_PER_TABLE, len(rows), ROW_CHUNK_SIZE):
        chunk_rows = rows[chunk_start : chunk_start + ROW_CHUNK_SIZE]
        start_row = chunk_start + 1
        end_row = chunk_start + len(chunk_rows)
        title = f"rows_{start_row}_{end_row}"
        records.append(
            DocumentRecord(
                doc_type="row_group",
                slug=row_group_slug(rel, title),
                title=title,
                frontmatter={
                    "table": table,
                    "source_file": source,
                    "row_start": start_row,
                    "row_end": end_row,
                    "row_count": len(chunk_rows),
                    "key_column": id_column,
                    "row_grouping": "chunk",
                    "rows": chunk_rows,
                },
                body=_row_chunk_body(title, table, chunk_rows),
            )
        )
    return records


def _table_body(table: str, source: str, column_docs: list[str], sample_rows: list[dict]) -> str:
    lines = [f"# {table}", "", f"Source: [[{source}]]", "", "Columns:"]
    lines.extend(f"- [[{slug}]]" for slug in column_docs)
    if sample_rows:
        lines.extend(["", "Sample rows:", "```json", json.dumps(sample_rows, indent=2, default=str), "```"])
    return "\n".join(lines)


def _column_body(name: str, table: str, info: dict) -> str:
    lines = [
        f"# {name}",
        "",
        f"Table: [[{table}]]",
        f"Inferred type: `{info['inferred_type']}`",
        f"Unique values: `{info['unique_count']}`",
    ]
    if info["unit"]:
        lines.append(f"Unit: `{info['unit']}`")
    if info["sample_values"]:
        lines.extend(["", "Sample values:", ", ".join(f"`{value}`" for value in info["sample_values"][:10])])
    return "\n".join(lines)


def _measurement_record(rel: str, name: str, table: str, col_slug: str, source: str, info: dict) -> DocumentRecord:
    numeric_values = [_to_float(value) for value in info["values"]]
    numeric_values = [value for value in numeric_values if value is not None]
    frontmatter = {
        "table": table,
        "column": col_slug,
        "source_file": source,
        "unit": info["unit"],
        "inferred_type": info["inferred_type"],
        "detected_from": "column_profile",
        "sample_values": info["sample_values"],
        "count": len(numeric_values),
    }
    if numeric_values:
        frontmatter.update(
            {
                "min_value": min(numeric_values),
                "max_value": max(numeric_values),
                "mean_value": round(sum(numeric_values) / len(numeric_values), 4),
            }
        )

    body_lines = [
        f"# {name}",
        "",
        f"Table: [[{table}]]",
        f"Column: [[{col_slug}]]",
    ]
    if info["unit"]:
        body_lines.append(f"Unit: `{info['unit']}`")
    if numeric_values:
        body_lines.extend(
            [
                f"Minimum: `{frontmatter['min_value']}`",
                f"Maximum: `{frontmatter['max_value']}`",
                f"Mean: `{frontmatter['mean_value']}`",
            ]
        )

    return DocumentRecord(
        doc_type="measurement",
        slug=measurement_slug(rel, name),
        title=name,
        frontmatter=frontmatter,
        body="\n".join(body_lines),
    )


def _row_body(value: str, table: str, row: dict) -> str:
    mentions = sorted(set(ID_RE.findall(json.dumps(row, default=str))))
    links = [f"- ID mention: `{mention}`" for mention in mentions if mention != value]
    return "\n".join(
        [
            f"# {value}",
            "",
            f"Table: [[{table}]]",
            "",
            "Row data:",
            "```json",
            json.dumps(row, indent=2, default=str),
            "```",
            "",
            "Detected IDs:",
            *(links or ["- none"]),
        ]
    )


def _row_chunk_body(title: str, table: str, rows: list[dict]) -> str:
    mentions = sorted(set(ID_RE.findall(json.dumps(rows[:20], default=str))))
    id_lines = [f"- `{mention}`" for mention in mentions[:25]] if mentions else ["- none"]
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Table: [[{table}]]",
            f"Rows in chunk: `{len(rows)}`",
            "",
            "Sample rows:",
            "```json",
            json.dumps(rows[:10], indent=2, default=str),
            "```",
            "",
            "Detected IDs in sample:",
            *id_lines,
        ]
    )


def _column_stats(rows: list[dict], headers: list[str]) -> dict[str, dict]:
    total = len(rows)
    stats = {}
    for name in headers:
        values = [row.get(name) for row in rows]
        nonempty = [str(value).strip() for value in values if str(value or "").strip()]
        unique_values = sorted(set(nonempty))
        inferred_type = _infer_type(nonempty)
        lower = name.lower()
        unit = _detect_unit(lower, nonempty)
        is_likely_measurement = inferred_type in {"int", "float"} or unit is not None
        is_id_name = lower == "id" or lower.endswith("_id") or lower.endswith(" id") or "identifier" in lower
        is_likely_pk = total > 0 and len(unique_values) == total and is_id_name
        is_likely_fk = is_id_name and not is_likely_pk
        stats[name] = {
            "inferred_type": inferred_type,
            "null_pct": 0 if total == 0 else round((total - len(nonempty)) / total, 3),
            "unique_count": len(unique_values),
            "is_likely_pk": is_likely_pk,
            "is_likely_fk": is_likely_fk,
            "is_likely_measurement": is_likely_measurement,
            "unit": unit,
            "sample_values": unique_values[:10],
            "values": nonempty,
        }
    return stats


def _infer_type(values: Iterable[str]) -> str:
    values = list(values)[:100]
    if not values:
        return "string"
    if all(_is_int(value) for value in values):
        return "int"
    if all(_is_float(value) for value in values):
        return "float"
    if all(_looks_date(value) for value in values):
        return "date"
    if all(value.lower() in {"true", "false", "yes", "no"} for value in values):
        return "bool"
    return "string"


def _detect_unit(column_name: str, values: list[str]) -> str | None:
    normalized = column_name.replace("/", "_").replace("-", "_")
    for hint, unit in UNIT_HINTS.items():
        if hint in normalized:
            return unit
    for value in values[:20]:
        lower = value.lower()
        for hint, unit in UNIT_HINTS.items():
            if hint in lower:
                return unit
    return None


def _best_identifier_column(headers: list[str], stats: dict[str, dict]) -> str | None:
    likely = [name for name in headers if stats[name]["is_likely_pk"]]
    if likely:
        return likely[0]
    id_like = [name for name in headers if name.lower().endswith("_id") or name.lower() == "id"]
    return id_like[0] if id_like else (headers[0] if headers else None)


def _headers(rows: list[dict]) -> list[str]:
    seen = []
    for row in rows:
        for key in row:
            if key not in seen:
                seen.append(str(key))
    return seen


def _flatten_json(data: dict, prefix: str = "") -> dict:
    flattened = {}
    for key, value in data.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_json(value, name))
        else:
            flattened[name] = value
    return flattened


def _json_candidate_records(rel: str, rows: list[dict]) -> list[DocumentRecord]:
    records = []
    seen = set()
    for row_index, row in enumerate(rows, start=1):
        for key, value in row.items():
            for match in ID_RE.findall(str(value)):
                normalized = match.upper()
                dedupe_key = (normalized, key)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                records.append(
                    DocumentRecord(
                        doc_type="candidate_entity",
                        slug=candidate_slug(rel, f"{key}/{normalized}"),
                        title=normalized,
                        frontmatter={
                            "detected_from": "json_value",
                            "source_file": source_slug(rel),
                            "source_path": rel,
                            "json_path": key,
                            "row_index": row_index,
                            "raw_value": value,
                        },
                        body=f"# {normalized}\n\nDetected at `{key}` in [[{source_slug(rel)}]].",
                    )
                )
    return records


def _markdown_tables(text: str) -> list[list[dict]]:
    tables: list[list[dict]] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines) - 1:
        header = lines[index].strip()
        separator = lines[index + 1].strip()
        if not (_is_markdown_table_row(header) and _is_markdown_separator(separator)):
            index += 1
            continue
        headers = _split_markdown_row(header)
        rows = []
        index += 2
        while index < len(lines) and _is_markdown_table_row(lines[index].strip()):
            values = _split_markdown_row(lines[index].strip())
            row = {headers[pos]: values[pos] if pos < len(values) else "" for pos in range(len(headers))}
            rows.append(row)
            index += 1
        if rows:
            tables.append(rows)
    return tables


def _is_markdown_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _is_markdown_separator(line: str) -> bool:
    if not _is_markdown_table_row(line):
        return False
    cells = _split_markdown_row(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _fasta_entries(text: str) -> list[tuple[str, str]]:
    entries = []
    header = None
    chunks = []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                entries.append((header, "".join(chunks)))
            header = line[1:].strip()
            chunks = []
        else:
            chunks.append(line.strip())
    if header is not None:
        entries.append((header, "".join(chunks)))
    return entries


def _parse_fasta_header(header: str) -> dict:
    parts = [part.strip() for part in header.split("|") if part.strip()]
    fields = {}
    names = ["id", "entity_id", "variant", "related_id"]
    for index, part in enumerate(parts):
        fields[names[index] if index < len(names) else f"field_{index + 1}"] = part
    return fields


def _is_int(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def _is_float(value: str) -> bool:
    try:
        float(value)
        return True
    except ValueError:
        return False


def _to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _looks_date(value: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{1,2}-\d{1,2}", value))
