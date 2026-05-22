"""
Source Table Model — what the spreadsheet/CSV literally contained.
Deterministic output from parsers. No LLM involved.
"""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class SourceColumn(BaseModel):
    source_name: str
    canonical_name: str
    inferred_type: str  # "string" | "integer" | "float" | "date" | "datetime" | "boolean" | "email" | "uuid"
    null_rate: float = 0.0          # 0.0 – 1.0
    unique_rate: float = 0.0        # 0.0 – 1.0
    cardinality: int | None = None  # number of distinct values (for low-card columns)
    unique_values: list[Any] = Field(default_factory=list)   # populated when cardinality ≤ 20
    sample_values: list[Any] = Field(default_factory=list)   # up to 5 representative values
    role_candidates: list[str] = Field(default_factory=list)
    # e.g. ["primary_key", "foreign_key", "enum", "entity_identifier", "business_identifier", "audit"]
    possible_semantic_type: str | None = None
    # e.g. "email", "phone", "person_name", "identifier", "amount", "date", "status", "address"


class SourceTableModel(BaseModel):
    source_id: str          # e.g. "orders.xlsx:Sheet1" or "orders.csv"
    file_name: str
    sheet_name: str | None  # None for CSVs
    detected_table_name: str
    header_row: int = 1
    data_start_row: int = 2
    row_count: int
    columns: list[SourceColumn]
    warnings: list[str] = Field(default_factory=list)
