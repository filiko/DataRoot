"""Stub — real LLM wiring is future work."""
from __future__ import annotations


def mock_chat(prompt: str) -> str:
    return f"[mock] {prompt[:80]}"
