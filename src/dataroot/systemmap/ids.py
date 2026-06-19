"""Stable identifier helpers for System Map records."""

from __future__ import annotations

import hashlib
import re

_UNSAFE_CHARS = re.compile(r"[^a-z0-9._-]+")
_REPEATED_SEPARATORS = re.compile(r"[_-]{2,}")


def slug_part(value: object, *, max_length: int = 64) -> str:
    """Return a stable, readable ID segment."""

    text = str(value or "").strip().lower()
    text = _UNSAFE_CHARS.sub("_", text)
    text = _REPEATED_SEPARATORS.sub("_", text).strip("._-")
    return text[:max_length].strip("._-") or "item"


def stable_id(prefix: str, *parts: object, max_length: int = 96) -> str:
    """Build a deterministic ID with a readable stem and collision-resistant suffix."""

    clean_prefix = slug_part(prefix, max_length=32)
    readable = "_".join(slug_part(part, max_length=32) for part in parts if str(part or "").strip())
    digest_input = "|".join(str(part) for part in (prefix, *parts))
    digest = hashlib.sha1(digest_input.encode("utf-8")).hexdigest()[:12]
    if readable:
        candidate = f"{clean_prefix}_{readable}_{digest}"
    else:
        candidate = f"{clean_prefix}_{digest}"
    return candidate[:max_length].strip("._-")
