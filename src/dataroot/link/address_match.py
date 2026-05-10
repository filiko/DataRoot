"""Heuristic address normalization for cross-dataset joins.

Austin open-data slices express the same address in slightly different forms
(`1623 S LAMAR BOULEVARD`, `1623 S Lamar Blvd`, `1623 S. LAMAR BLVD UNIT 2`).
The KB linker keys identity off `_id` columns; addresses need a separate
canonicalizer before they can act as a join key.

Two functions:

- ``normalize_address(s)`` returns a canonical text form — uppercase, no
  punctuation, USPS-style suffixes (BOULEVARD → BLVD), directions collapsed
  (NORTH → N). Useful for filtering / display.
- ``address_key(s)`` returns the canonical form with any unit/suite/apt
  trailer stripped. This is the cross-dataset join key — two records share an
  address regardless of whether one carries a unit suffix.
"""

from __future__ import annotations

import re

_SUFFIXES: dict[str, str] = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "DRIVE": "DR",
    "LANE": "LN",
    "ROAD": "RD",
    "COURT": "CT",
    "CIRCLE": "CIR",
    "PARKWAY": "PKWY",
    "HIGHWAY": "HWY",
    "TERRACE": "TER",
    "PLACE": "PL",
    "TRAIL": "TRL",
    "SQUARE": "SQ",
    "ALLEY": "ALY",
    "CROSSING": "XING",
    "EXPRESSWAY": "EXPY",
    "FREEWAY": "FWY",
    "JUNCTION": "JCT",
    "PASS": "PASS",
}

_DIRECTIONS: dict[str, str] = {
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
    "NORTHEAST": "NE",
    "NORTHWEST": "NW",
    "SOUTHEAST": "SE",
    "SOUTHWEST": "SW",
}

_UNIT_TOKENS = frozenset({"UNIT", "STE", "SUITE", "APT", "APARTMENT", "BLDG", "BUILDING", "#"})

_PUNCT_RE = re.compile(r"[.,;]+")
_NON_TOKEN_RE = re.compile(r"[^A-Z0-9# ]")
_WS_RE = re.compile(r"\s+")


def normalize_address(value: str | None) -> str:
    """Return a canonical uppercase form of ``value`` with stable abbreviations."""
    if not value:
        return ""
    text = str(value).upper()
    text = _PUNCT_RE.sub(" ", text)
    text = _NON_TOKEN_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""
    tokens = [_canonical_token(token) for token in text.split(" ")]
    return " ".join(token for token in tokens if token)


def address_key(value: str | None) -> str:
    """Return the ``normalize_address`` form with unit/suite trailers removed."""
    canonical = normalize_address(value)
    if not canonical:
        return ""
    tokens = canonical.split(" ")
    cut = _unit_split_index(tokens)
    if cut is not None:
        tokens = tokens[:cut]
    return " ".join(tokens).strip()


def _canonical_token(token: str) -> str:
    if token in _DIRECTIONS:
        return _DIRECTIONS[token]
    if token in _SUFFIXES:
        return _SUFFIXES[token]
    return token


def _unit_split_index(tokens: list[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token in _UNIT_TOKENS:
            return index
        if token.startswith("#"):
            return index
    return None
