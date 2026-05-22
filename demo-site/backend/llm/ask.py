"""Free-form 'Ask' over the bundled demo CSV data (Austin permits + fermentation).

All CSVs under demo_data/ are loaded recursively and labelled by subfolder/name
so the LLM can cite them correctly. Files are tiny and cached after first load.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .minimax import ask_about_data

_DATA_DIR = Path(__file__).resolve().parent.parent / "demo_data"


@lru_cache(maxsize=1)
def _csv_context() -> str:
    """Recursively load all CSVs under demo_data/, labelled by relative path."""
    blocks: list[str] = []
    for path in sorted(_DATA_DIR.rglob("*.csv")):
        label = path.relative_to(_DATA_DIR).as_posix()
        text = path.read_text(encoding="utf-8").strip()
        blocks.append(f"=== {label} ===\n{text}")
    return "\n\n".join(blocks)


def answer_question(question: str) -> dict[str, Any]:
    """Answer a free-form question; result is shaped like a frontend DemoQuestion."""
    return ask_about_data(question, _csv_context())
