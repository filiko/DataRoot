"""
CSV parser — DuckDB sniff_csv for type inference, pandas for profiling.
"""
from __future__ import annotations

import os

import duckdb
import pandas as pd

from models.source import SourceColumn, SourceTableModel
from parsers.profiler import profile_column, to_canonical_name


def parse_csv(file_path: str, original_filename: str | None = None) -> SourceTableModel:
    """Parse a single CSV file into a SourceTableModel."""
    file_name = os.path.basename(file_path)
    if original_filename:
        file_name = original_filename
    table_name = to_canonical_name(os.path.splitext(file_name)[0])
    source_id = file_name

    # Use DuckDB to sniff types and read the CSV
    con = duckdb.connect()
    try:
        # sniff_csv gives us inferred column types and delimiter
        sniff = con.execute(f"SELECT * FROM sniff_csv('{file_path}')").fetchone()
        # Actually read into a DataFrame via DuckDB (handles encoding, delimiters, quoting)
        df = con.execute(f"SELECT * FROM read_csv_auto('{file_path}', header=true)").df()
    except Exception as e:
        # Fallback to pandas if DuckDB can't handle the file
        try:
            df = pd.read_csv(file_path, encoding="utf-8", low_memory=False)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding="latin-1", low_memory=False)

    row_count = len(df)
    warnings: list[str] = []

    if row_count == 0:
        warnings.append("CSV appears to be empty or header-only.")

    columns: list[SourceColumn] = []
    for col_name in df.columns:
        raw_values = df[col_name].tolist()
        # Replace pandas NA/NaT/NaN with None for consistent profiling
        clean_values = [
            None if (pd.isna(v) if not isinstance(v, (list, dict)) else False) else v
            for v in raw_values
        ]
        profile = profile_column(str(col_name), clean_values)
        columns.append(SourceColumn(**profile))

    return SourceTableModel(
        source_id=source_id,
        file_name=file_name,
        sheet_name=None,
        detected_table_name=table_name,
        header_row=1,
        data_start_row=2,
        row_count=row_count,
        columns=columns,
        warnings=warnings,
    )
