"""MiniMax LLM client.

MiniMax exposes an Anthropic-Messages-compatible endpoint, so we drive it with
the already-bundled `anthropic` SDK pointed at a custom base_url. Methodology
mirrors the AgenticFlow project (provider "minimax", model "MiniMax-M2.7",
api "anthropic-messages", baseUrl "https://api.minimax.io/anthropic").

Env vars:
  MINIMAX_API_KEY   required — the MiniMax API key
  MINIMAX_BASE_URL  optional — defaults to https://api.minimax.io/anthropic
  MINIMAX_MODEL     optional — defaults to MiniMax-M2.7
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "").strip()
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic").strip()
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()


def is_configured() -> bool:
    """True when an API key is present — used for graceful degradation."""
    return bool(MINIMAX_API_KEY)


def _complete(system: str, user: str, *, max_tokens: int = 1024,
              temperature: float | None = None) -> str:
    """Single-turn completion against MiniMax. Returns concatenated text content.

    `temperature` is passed through only when set — eval/deterministic callers
    pass 0; the chat/ask paths leave it unset to use the provider default."""
    from anthropic import Anthropic

    client = Anthropic(api_key=MINIMAX_API_KEY, base_url=MINIMAX_BASE_URL)
    extra: dict[str, Any] = {}
    if temperature is not None:
        extra["temperature"] = temperature
    resp = client.messages.create(
        model=MINIMAX_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        **extra,
    )
    parts = [b.text for b in resp.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts).strip()


# ── Diagram chat (DFD/ERD assistant) ──────────────────────────────────────────

_CHAT_SYSTEM = (
    "You are the DataRoot assistant inside a DFD/ERD schema-design tool. "
    "Answer the user's question about their data model clearly and concisely. "
    "Base your answer only on the diagram summary provided; if the summary does "
    "not contain the answer, say so plainly rather than guessing. "
    "Keep replies under 130 words."
)


def chat_about_diagram(message: str, diagram_summary: str) -> str:
    """Answer a question about the current ERD/DFD. Never raises — returns a
    friendly string on any failure so the chat UI degrades gracefully."""
    if not is_configured():
        return "The AI assistant isn't configured yet (missing MINIMAX_API_KEY)."
    user = f"Diagram summary:\n{diagram_summary}\n\nQuestion: {message}"
    try:
        return _complete(_CHAT_SYSTEM, user, max_tokens=512) or "(no response)"
    except Exception as e:  # noqa: BLE001 - surface as chat text, not a 500
        return f"The AI assistant hit an error reaching MiniMax: {e}"


# ── Free-form data Ask (cited answers) ────────────────────────────────────────

_ASK_SYSTEM = """You are DataRoot's data analyst. You answer questions strictly \
from the City of Austin permit CSV data provided to you.

Rules:
- Use ONLY facts present in the provided CSV data. Never invent records, IDs, \
names, addresses, dates, or values.
- Cite the specific rows you actually used. Provide between 0 and 3 sources — \
only as many as you genuinely relied on. Do NOT pad to a fixed count.
- If the data does not support an answer, say so honestly and return an empty \
"sources" list. Do not hallucinate.
- Respond with ONLY a JSON object — no markdown, no prose outside the JSON — in \
exactly this shape:
{
  "headline": "<one-sentence direct answer>",
  "answer": "<2-4 sentence explanation grounded in the cited rows>",
  "confidence": "<short pill text, e.g. '2 linked sources' or 'no direct match'>",
  "sources": [
    {"file": "<csv file name>", "role": "<starting record|linked context|final proof>", "detail": "<the exact record/fact used>"}
  ]
}"""


def ask_about_data(question: str, csv_context: str) -> dict[str, Any]:
    """Answer a free-form question about the bundled CSV data. Returns a dict
    shaped like the frontend DemoQuestion. Never raises."""
    if not is_configured():
        return {
            "headline": "The Ask service isn't configured yet.",
            "answer": "Set MINIMAX_API_KEY on the backend to enable free-form questions.",
            "confidence": "unavailable",
            "sources": [],
        }
    user = f"CSV DATA:\n{csv_context}\n\nQUESTION: {question}"
    try:
        raw = _complete(_ASK_SYSTEM, user, max_tokens=1500)
    except Exception as e:  # noqa: BLE001
        return {
            "headline": "The Ask service hit an error.",
            "answer": f"Could not reach MiniMax: {e}",
            "confidence": "error",
            "sources": [],
        }
    return _parse_ask_json(raw)


def _parse_ask_json(raw: str) -> dict[str, Any]:
    """Defensively parse the model's JSON answer; fall back to plain text."""
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                data = None

    if not isinstance(data, dict):
        return {
            "headline": (raw[:140].strip() or "No answer"),
            "answer": raw.strip() or "The assistant did not return an answer.",
            "confidence": "unverified",
            "sources": [],
        }

    sources: list[dict[str, str]] = []
    for s in (data.get("sources") or [])[:3]:  # hard cap: max 3 citations
        if not isinstance(s, dict):
            continue
        sources.append({
            "file": str(s.get("file", "")).strip(),
            "role": (str(s.get("role", "")).strip() or "source"),
            "detail": str(s.get("detail", "")).strip(),
        })

    return {
        "headline": str(data.get("headline", "")).strip() or "Answer",
        "answer": str(data.get("answer", "")).strip() or "No answer provided.",
        "confidence": (str(data.get("confidence", "")).strip()
                       or f"{len(sources)} linked sources"),
        "sources": sources,
    }
