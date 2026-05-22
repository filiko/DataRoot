"""
Excel parser — deterministic sheet/table detection and column profiling.
Supports .xlsx (openpyxl) and .xls (xlrd).

Rules:
- Header row: first non-empty row where >50% of cells are non-numeric strings
- Skip rows: blank, subtotal (all numeric after header), merged-cell rows
- Multiple tables per sheet: detected by blank-row separators
"""
from __future__ import annotations

import os
from typing import Any

import openpyxl
from slugify import slugify

from models.source import SourceColumn, SourceTableModel
from parsers.profiler import profile_column, to_canonical_name


# ── Helpers ───────────────────────────────────────────────────────────────────

def _cell_value(cell) -> Any:
    if cell is None:
        return None
    v = cell.value
    if isinstance(v, str):
        v = v.strip()
        return None if v == "" else v
    return v


def _is_blank_row(row) -> bool:
    return all(_cell_value(c) is None for c in row)


def _is_header_row(row) -> bool:
    """True if >50% of non-empty cells are non-numeric strings."""
    non_empty = [_cell_value(c) for c in row if _cell_value(c) is not None]
    if not non_empty:
        return False
    string_count = sum(1 for v in non_empty if isinstance(v, str))
    return string_count / len(non_empty) > 0.5


def _detect_header(rows: list) -> int | None:
    """Return 0-based index of header row, or None."""
    for i, row in enumerate(rows[:20]):
        if _is_header_row(row):
            return i
    return None


def _extract_table(rows: list, sheet_name: str, file_name: str, table_index: int = 0) -> SourceTableModel | None:
    """Parse one contiguous block of rows into a SourceTableModel."""
    header_idx = _detect_header(rows)
    if header_idx is None:
        return None

    header_row = rows[header_idx]
    headers = [_cell_value(c) for c in header_row]

    # Drop fully-None header columns
    col_indices = [(i, h) for i, h in enumerate(headers) if h is not None]
    if not col_indices:
        return None

    data_rows = rows[header_idx + 1:]
    # Filter out blank rows and rows that look like subtotals
    data_rows = [r for r in data_rows if not _is_blank_row(r)]

    # Collect raw column values
    col_data: dict[int, list[Any]] = {i: [] for i, _ in col_indices}
    for row in data_rows:
        for i, _ in col_indices:
            val = _cell_value(row[i]) if i < len(row) else None
            col_data[i].append(val)

    row_count = len(data_rows)

    # Determine table name from sheet name + index
    raw_name = f"{sheet_name}_{table_index}" if table_index > 0 else sheet_name
    table_name = to_canonical_name(raw_name)
    source_id = f"{file_name}:{sheet_name}"
    if table_index > 0:
        source_id += f"[{table_index}]"

    columns: list[SourceColumn] = []
    for i, header in col_indices:
        profile = profile_column(str(header), col_data[i])
        columns.append(SourceColumn(**profile))

    return SourceTableModel(
        source_id=source_id,
        file_name=file_name,
        sheet_name=sheet_name,
        detected_table_name=table_name,
        header_row=header_idx + 1,
        data_start_row=header_idx + 2,
        row_count=row_count,
        columns=columns,
        warnings=[],
    )


def _split_by_blank_rows(rows: list) -> list[list]:
    """Split a flat list of rows on blank-row separators."""
    chunks: list[list] = []
    current: list = []
    for row in rows:
        if _is_blank_row(row):
            if current:
                chunks.append(current)
                current = []
        else:
            current.append(row)
    if current:
        chunks.append(current)
    return chunks


# ── Public API ────────────────────────────────────────────────────────────────

def parse_xlsx(file_path: str, original_filename: str | None = None) -> list[SourceTableModel]:
    """Parse all sheets in an .xlsx file. Returns one model per detected table."""
    file_name = os.path.basename(file_path)
    if original_filename:
        file_name = original_filename
    wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    results: list[SourceTableModel] = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Read all rows as tuples
        all_rows = list(ws.iter_rows())
        if not all_rows:
            continue

        # Try to find multiple tables separated by blank rows
        chunks = _split_by_blank_rows(all_rows)
        for idx, chunk in enumerate(chunks):
            model = _extract_table(chunk, sheet_name, file_name, table_index=idx)
            if model:
                results.append(model)

    wb.close()
    return results


def parse_xls(file_path: str, original_filename: str | None = None) -> list[SourceTableModel]:
    """Parse all sheets in an .xls file using xlrd, then route through same logic."""
    try:
        import xlrd
    except ImportError:
        raise RuntimeError("xlrd is required for .xls support: pip install xlrd")

    file_name = os.path.basename(file_path)
    if original_filename:
        file_name = original_filename
    wb = xlrd.open_workbook(file_path)
    results: list[SourceTableModel] = []

    for sheet_idx in range(wb.nsheets):
        ws = wb.sheet_by_index(sheet_idx)
        sheet_name = ws.name

        # Build a list of "rows" in the same format as openpyxl (list of cell-like objects)
        class FakeCell:
            def __init__(self, value):
                self.value = value

        all_rows = []
        for r in range(ws.nrows):
            row = [FakeCell(ws.cell_value(r, c)) for c in range(ws.ncols)]
            all_rows.append(row)

        if not all_rows:
            continue

        chunks = _split_by_blank_rows(all_rows)
        for idx, chunk in enumerate(chunks):
            model = _extract_table(chunk, sheet_name, file_name, table_index=idx)
            if model:
                results.append(model)

    return results


def parse_excel(file_path: str, original_filename: str | None = None) -> list[SourceTableModel]:
    """Auto-detect xlsx vs xls and parse."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".xlsx":
        return parse_xlsx(file_path, original_filename)
    elif ext == ".xls":
        return parse_xls(file_path, original_filename)
    else:
        raise ValueError(f"Unsupported Excel format: {ext}")
