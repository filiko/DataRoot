"""Thin re-export wrapper so callers can import from generators.dbml."""
from generators.sql import export_dbml

__all__ = ["export_dbml"]
