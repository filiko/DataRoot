"""Project the repo's detected behavioral signals into PenFile business rules
and connectors, so the Business Rules / Connectors tabs are populated with real,
evidence-linked content for any analyzed repo (not just hand-authored fixtures).

Reuses the AST detectors in `systemmap_provider` and maps their EvidenceRecords
onto the `models.pen` BusinessRule / Connector shapes the UI reads from
`pen.dfd.business_rules` / `pen.dfd.connectors`.
"""
from __future__ import annotations

import re
from pathlib import Path

from models.pen import BusinessRule, Connector

from .models import EvidenceRecord, RepositoryInventory
from .systemmap_provider import (
    collect_business_rules,
    collect_middleware_connectors,
    collect_outbound_connectors,
)


def _enforced_at(record: EvidenceRecord) -> list[str]:
    if record.path and record.line_start:
        end = record.line_end or record.line_start
        return [f"{record.path}:{record.line_start}-{end}"]
    return []


def _rule_id(record: EvidenceRecord) -> str:
    # record.id is a stable "ev_<hash>"; reuse the hash so rules are stable across runs.
    suffix = record.id.split("_", 1)[-1] if "_" in record.id else record.id
    return f"rule_{suffix}"


def _conn_id(record: EvidenceRecord) -> str:
    suffix = record.id.split("_", 1)[-1] if "_" in record.id else record.id
    return f"conn_{suffix}"


# A real state transition is named with an explicit transition verb, e.g.
# `transition_open_to_closed`, `set_status_to_active`. This excludes the
# detector's noisy matches — any function whose name merely contains "_to_"
# (`source_col_to_attribute`, `propagate_erd_to_dfd`) or that references a
# state-ish identifier (to_state="next_state" fallback).
_TRANSITION_NAME = re.compile(r"^(transition|change|set|update|move|advance|promote|mark)_.+?_(?:to|2)_.+", re.IGNORECASE)


def _is_high_signal_rule(record: EvidenceRecord) -> bool:
    """Keep only high-precision detections so the tab is useful, not noise.

    Pydantic validators are decorator-matched → reliable. State transitions are
    kept only when the function name uses an explicit transition verb."""
    attrs = record.attributes
    if attrs.get("category") == "validation":
        return True
    handler = str(attrs.get("handler") or "")
    to_state = attrs.get("to_state")
    return to_state != "next_state" and bool(_TRANSITION_NAME.match(handler))


def _business_rule_from(record: EvidenceRecord) -> BusinessRule:
    attrs = record.attributes
    handler = str(attrs.get("handler") or "rule")
    category = "state_machine" if attrs.get("category") == "state_machine" else "validation"

    if category == "validation":
        field = attrs.get("field_name")
        title = f"Validates {field}" if field and field != "unknown" else f"Validator: {handler}"
        statement = record.excerpt or (
            f"`{handler}` enforces a {attrs.get('validator_kind', 'field')} validation"
            + (f" on `{field}`." if field and field != "unknown" else ".")
        )
    else:
        from_state, to_state = attrs.get("from_state"), attrs.get("to_state")
        title = f"State transition: {from_state} → {to_state}"
        statement = record.excerpt or f"`{handler}` transitions {from_state} → {to_state}."

    return BusinessRule(
        id=_rule_id(record),
        title=title,
        statement=statement,
        category=category,
        condition=record.excerpt,
        enforced_at=_enforced_at(record),
        severity="constraint",
        status="enforced",
        review_status="accepted",
    )


def _guard_connector_from(record: EvidenceRecord) -> Connector:
    """Map a middleware/auth-guard EvidenceRecord 1:1 (these are few and specific)."""
    attrs = record.attributes
    handler = str(attrs.get("handler") or "")
    kind = "auth" if attrs.get("kind") == "auth" else "middleware"
    name = (f"Auth guard: {handler}" if kind == "auth" else f"Middleware: {handler}").strip()
    return Connector(
        id=_conn_id(record),
        name=name or kind,
        kind=kind,
        trigger=record.excerpt,
        effect="Requires authentication" if kind == "auth" else "Runs on matching requests",
        enforced_at=_enforced_at(record),
        status="wired",
        review_status="accepted",
    )


def _grouped_outbound_connectors(records: list[EvidenceRecord]) -> list[Connector]:
    """Group outbound HTTP calls by (client, method, target) so a repo with
    hundreds of identical calls yields a handful of meaningful connectors, each
    listing its call sites — instead of one row per call (noise)."""
    groups: dict[tuple[str, str, str], list[EvidenceRecord]] = {}
    for rec in records:
        attrs = rec.attributes
        key = (str(attrs.get("client", "http")), str(attrs.get("method", "")), str(attrs.get("target_system") or "external service"))
        groups.setdefault(key, []).append(rec)

    connectors: list[Connector] = []
    for (client, method, target), recs in sorted(groups.items()):
        sites = [s for r in recs for s in _enforced_at(r)][:12]
        urls = sorted({str(r.attributes.get("url")) for r in recs if r.attributes.get("url")})
        connectors.append(Connector(
            id=f"conn_out_{client}_{method}_{target}".lower().replace(" ", "_").replace("/", "_")[:80],
            name=f"{client} {method} → {target}".strip(),
            kind="seam",
            trigger=f"{len(recs)} call site(s)" if len(recs) > 1 else (recs[0].excerpt if recs else None),
            effect=f"Calls {urls[0]}" if urls else f"Outbound {method} to {target}",
            to_contexts=[target] if target != "external service" else [],
            contract=f"{method} {urls[0]}" if urls else (method or None),
            enforced_at=sites,
            status="wired",
            review_status="accepted",
        ))
    return connectors


def _dedupe(items: list, key) -> list:
    seen: set = set()
    out: list = []
    for item in items:
        k = key(item)
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


_MAX_RULES = 80
_MAX_CONNECTORS = 80


def synthesize_behavioral_layer(
    repo_root: Path,
    inventory: RepositoryInventory,
) -> tuple[list[BusinessRule], list[Connector]]:
    """Detect rules + connectors in the repo and map them to PenFile shapes.

    High-precision only: validators + genuine named state transitions for rules;
    middleware/auth guards plus grouped-by-target outbound calls for connectors.
    Capped so a large repo can't flood the tabs with low-signal rows.
    """
    rule_records = [r for r in collect_business_rules(repo_root, inventory) if _is_high_signal_rule(r)]
    rules = _dedupe([_business_rule_from(r) for r in rule_records], lambda r: r.id)[:_MAX_RULES]

    guards = collect_middleware_connectors(repo_root, inventory)
    outbound = collect_outbound_connectors(repo_root, inventory)
    connectors = _dedupe(
        [_guard_connector_from(r) for r in guards] + _grouped_outbound_connectors(outbound),
        lambda c: c.id,
    )[:_MAX_CONNECTORS]
    return rules, connectors
