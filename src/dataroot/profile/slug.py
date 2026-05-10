"""Slug helpers."""

from __future__ import annotations

import re
from pathlib import Path


def slugify(value: str) -> str:
    value = value.replace("\\", "/").strip().strip("/").lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9._/\-]+", "_", value)
    value = re.sub(r"/+", "/", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_") or "unnamed"


def relative_slug(root: Path, path: Path) -> str:
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path.name
    return slugify(rel.as_posix() if isinstance(rel, Path) else str(rel))


def column_slug(table_path: str, column_name: str) -> str:
    return f"columns/{slugify(table_path)}/{slugify(column_name)}"


def table_slug(table_path: str) -> str:
    return f"tables/{slugify(table_path)}"


def source_slug(file_path: str) -> str:
    return f"source_files/{slugify(file_path)}"


def row_group_slug(table_path: str, row_key: str) -> str:
    return f"row_groups/{slugify(table_path)}/{slugify(row_key)}"


def candidate_slug(source_path: str, value: str) -> str:
    return f"candidates/{slugify(source_path)}/{slugify(value)}"


def measurement_slug(table_path: str, column_name: str) -> str:
    return f"measurements/{slugify(table_path)}/{slugify(column_name)}"
