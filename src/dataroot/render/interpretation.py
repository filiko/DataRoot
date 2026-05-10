"""Interpret raw DataRoot provenance tidbits into human-readable claims."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InterpretedClaim:
    claim: str
    why_it_matters: str
    evidence_refs: list[str] = field(default_factory=list)
    source_label: str = ""
    importance: str = "normal"


@dataclass
class ProofRow:
    evidence_ref: str
    title: str
    stage: str
    source_label: str = ""
    detail: str = ""
    raw_detail: str = ""


@dataclass
class DataTidbitInterpretation:
    takeaway: str
    confidence: str
    retrieval_explanation: str
    claims: list[InterpretedClaim] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    proof_rows: list[ProofRow] = field(default_factory=list)
    source: str = "deterministic_fallback"


def interpret_data_tidbits(
    trace: dict,
    *,
    store=None,
    inquiry_slug: str | None = None,
    answer_text: str | None = None,
) -> DataTidbitInterpretation:
    """Return human-readable claim blocks grounded in existing provenance refs."""

    fallback = _deterministic_interpretation(
        trace,
        store=store,
        inquiry_slug=inquiry_slug,
        answer_text=answer_text,
    )
    if os.environ.get("DATAROOT_USE_TIDBIT_INTERPRETER") == "0" or not (os.environ.get("OPENAI_API_KEY") or os.environ.get("MINIMAX_API_KEY")):
        return fallback

    try:
        return _agent_interpretation(trace, fallback)
    except Exception:
        return fallback


def _deterministic_interpretation(
    trace: dict,
    *,
    store=None,
    inquiry_slug: str | None,
    answer_text: str | None,
) -> DataTidbitInterpretation:
    summary = trace.get("provenance_summary") if isinstance(trace.get("provenance_summary"), dict) else {}
    takeaway = _answer_from_inputs(trace, store=store, inquiry_slug=inquiry_slug, answer_text=answer_text)
    confidence = _clean(str(summary.get("confidence") or "supported"))
    contexts = [_node_context(node, store=store) for node in trace.get("nodes") or [] if isinstance(node, dict)]
    evidence_contexts = [context for context in contexts if context["stage"] not in {"query", "answer"}]

    proof_rows = [
        ProofRow(
            evidence_ref=context["slug"] or context["id"],
            title=context["label"],
            stage=context["stage"],
            source_label=context["source"],
            detail=context["detail"],
            raw_detail=context["raw_detail"] or context["detail"],
        )
        for context in evidence_contexts
        if context["slug"] or context["id"]
    ]

    claims = []
    for context in evidence_contexts:
        ref = context["slug"] or context["id"]
        if not ref:
            continue
        claims.append(
            InterpretedClaim(
                claim=_claim_from_context(context),
                why_it_matters=_why_it_matters(context, summary),
                evidence_refs=[ref],
                source_label=context["source"] or _humanize(context["stage"]),
                importance=_importance_for(context, summary),
            )
        )

    sources = sorted({row.source_label for row in proof_rows if row.source_label})
    source_text = ", ".join(sources[:4]) if sources else ", ".join(sorted({row.stage for row in proof_rows})[:4])
    if not source_text:
        source_text = "the linked knowledge base"
    retrieved = len(proof_rows)
    retrieval_explanation = (
        f"DataRoot found {retrieved} cited evidence record{'s' if retrieved != 1 else ''} from {source_text} "
        "and kept the citation refs attached for proof mode."
    )

    return DataTidbitInterpretation(
        takeaway=takeaway,
        confidence=confidence,
        retrieval_explanation=retrieval_explanation,
        claims=claims,
        caveats=_caveats_from_summary(summary),
        proof_rows=proof_rows,
        source="deterministic_fallback",
    )


def _agent_interpretation(trace: dict, fallback: DataTidbitInterpretation) -> DataTidbitInterpretation:
    from dataroot.agent.codex_client import CodexClient

    allowed_refs = sorted({row.evidence_ref for row in fallback.proof_rows if row.evidence_ref})
    payload = {
        "question": _clean(str(trace.get("question") or "")),
        "takeaway": fallback.takeaway,
        "confidence": fallback.confidence,
        "retrieval_explanation": fallback.retrieval_explanation,
        "allowed_evidence_refs": allowed_refs,
        "fallback_claims": [claim.__dict__ for claim in fallback.claims],
        "proof_rows": [row.__dict__ for row in fallback.proof_rows],
        "trace_summary": trace.get("provenance_summary"),
    }
    system_prompt = (
        "You are DataRoot's data tidbit interpreter. Rewrite the supplied mini data records into concise, "
        "natural-language claims for a business/research demo viewer. Return only JSON with keys: "
        "takeaway, confidence, retrieval_explanation, claims, caveats. Each claim must contain claim, "
        "why_it_matters, evidence_refs, source_label, and importance. Use only evidence_refs from "
        "allowed_evidence_refs. Do not add facts, citations, measurements, genes, strains, dates, or outcomes "
        "that are not already present in the input proof rows."
    )
    result = CodexClient().run(
        system_prompt,
        [{"role": "user", "content": json.dumps(payload, ensure_ascii=True)}],
        tools=[],
        temperature=0.2,
        max_retries=1,
    )
    if not result.final_output:
        raise ValueError("interpreter returned no output")
    data = _json_object_from_model_text(result.final_output)
    interpreted = _interpretation_from_payload(data, fallback=fallback, allowed_refs=set(allowed_refs))
    if fallback.proof_rows and not interpreted.claims:
        raise ValueError("interpreter returned no citation-grounded claims")
    return interpreted


def _interpretation_from_payload(
    data: dict,
    *,
    fallback: DataTidbitInterpretation,
    allowed_refs: set[str],
) -> DataTidbitInterpretation:
    claims = []
    for item in data.get("claims") or []:
        if not isinstance(item, dict):
            continue
        refs = _list_of_strings(item.get("evidence_refs"))
        refs = [ref for ref in refs if ref in allowed_refs]
        if allowed_refs and not refs:
            continue
        claim = _clean(str(item.get("claim") or ""))
        why = _clean(str(item.get("why_it_matters") or ""))
        if not claim:
            continue
        claims.append(
            InterpretedClaim(
                claim=claim,
                why_it_matters=why or "This cited record supports the answer.",
                evidence_refs=refs,
                source_label=_clean(str(item.get("source_label") or "")),
                importance=_normalize_importance(str(item.get("importance") or "normal")),
            )
        )

    return DataTidbitInterpretation(
        takeaway=_sanitize_final_answer_text(str(data.get("takeaway") or fallback.takeaway)),
        confidence=_clean(str(data.get("confidence") or fallback.confidence)),
        retrieval_explanation=_clean(str(data.get("retrieval_explanation") or fallback.retrieval_explanation)),
        claims=claims or fallback.claims,
        caveats=[item for item in _list_of_strings(data.get("caveats")) if item] or fallback.caveats,
        proof_rows=fallback.proof_rows,
        source="agent",
    )


def _json_object_from_model_text(value: str) -> dict:
    raw = value.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("model output must be a JSON object")
    return data


def _answer_from_inputs(trace: dict, *, store=None, inquiry_slug: str | None, answer_text: str | None) -> str:
    if answer_text:
        return _sanitize_final_answer_text(answer_text)
    if store and inquiry_slug:
        try:
            record = store.read(inquiry_slug)
            answer = _extract_answer_summary(record.body)
            if answer:
                return _sanitize_final_answer_text(answer)
        except Exception:
            pass
    summary = trace.get("provenance_summary")
    if isinstance(summary, dict):
        reasoning = summary.get("reasoning") or summary.get("summary")
        if reasoning:
            return _sanitize_final_answer_text(str(reasoning))
    if isinstance(summary, str):
        return _sanitize_final_answer_text(summary)
    return "DataRoot found a cited evidence path for this question."


def _node_context(node: dict, *, store=None) -> dict[str, str]:
    slug = _clean(str(node.get("slug") or ""))
    label = _clean(str(node.get("label") or node.get("id") or slug or "Evidence"))
    stage = _normalize_stage(str(node.get("stage") or "evidence"))
    if stage in _GENERIC_NODE_STAGES:
        stage = _stage_from_slug(slug) or stage
    detail = _clean(str(node.get("citation_snippet") or node.get("description") or node.get("detail") or ""))
    source = _source_from_slug(slug)
    raw_detail = detail
    if store and slug and not node.get("visual_only"):
        try:
            record = store.read(slug)
            source = _source_from_record(record) or source
            raw_detail = _record_summary(record, limit=700)
            if not detail:
                detail = _record_summary(record)
        except Exception:
            pass
    if not detail:
        detail = f"Retrieved from {source or slug or stage}."
    if not raw_detail:
        raw_detail = detail
    return {
        "id": _clean(str(node.get("id") or slug or label)),
        "slug": slug,
        "label": label,
        "stage": stage,
        "detail": detail,
        "raw_detail": raw_detail,
        "source": source,
    }


def _claim_from_context(context: dict[str, str]) -> str:
    title = context["label"]
    detail = _humanize_raw_detail(context["detail"])
    if detail and detail.lower().startswith(title.lower()):
        return _truncate(detail, 180)
    if detail:
        return _truncate(f"{title}: {detail}", 180)
    return _truncate(f"{title} is part of the cited evidence path.", 180)


def _why_it_matters(context: dict[str, str], summary: dict) -> str:
    reasoning = _clean(str(summary.get("reasoning") or summary.get("summary") or ""))
    label = context["label"].lower()
    if reasoning and label and label in reasoning.lower():
        return _truncate(reasoning, 220)
    return "This cited record is one of the proof points DataRoot used to support the answer."


def _importance_for(context: dict[str, str], summary: dict) -> str:
    text = json.dumps(summary, ensure_ascii=True).lower() if isinstance(summary, dict) else ""
    haystack = f"{context['label']} {context['detail']}".lower()
    if any(term in haystack for term in ["primary", "best", "ready", "passed", "released"]):
        return "primary"
    if haystack and any(token for token in _meaningful_tokens(haystack) if token in text):
        return "primary"
    return "normal"


def _caveats_from_summary(summary: dict) -> list[str]:
    caveats = []
    for key in ("insufficient_context", "insufficient_candidates", "secondary_candidates"):
        values = summary.get(key) if isinstance(summary, dict) else None
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for value in values:
            text = _clean(str(value))
            if text:
                caveats.append(text)
    return caveats


def _source_from_record(record) -> str:
    row_data = record.frontmatter.get("row_data")
    table = record.frontmatter.get("table")
    source_file = record.frontmatter.get("source_file")
    path = record.frontmatter.get("path")
    if table:
        return _short_source(str(table))
    if source_file:
        return _short_source(str(source_file))
    if path:
        return _short_source(str(path))
    if isinstance(row_data, dict):
        return _short_source(record.slug)
    return _short_source(record.slug)


def _source_from_slug(slug: str) -> str:
    if not slug:
        return ""
    parts = slug.split("/")
    if len(parts) >= 2:
        return _short_source("/".join(parts[:2]))
    return _short_source(slug)


def _short_source(value: str) -> str:
    cleaned = value.replace("\\", "/").strip("/")
    if not cleaned:
        return ""
    tail = cleaned.rsplit("/", 1)[-1]
    parent = cleaned.rsplit("/", 2)[-2] if "/" in cleaned else ""
    return f"{parent}/{tail}" if parent and tail not in parent else tail


def _record_summary(record, limit: int = 320) -> str:
    row_data = record.frontmatter.get("row_data")
    if isinstance(row_data, dict) and row_data:
        pieces = [f"{key}: {value}" for key, value in row_data.items() if value is not None and value != ""]
        return _truncate("; ".join(pieces), limit)
    fields = record.frontmatter.get("fields")
    if isinstance(fields, dict) and fields:
        pieces = [f"{key}: {value}" for key, value in fields.items() if value is not None and value != ""]
        return _truncate("; ".join(pieces), limit)
    body = " ".join(record.body.split())
    return _truncate(body or record.title, limit)


def _extract_answer_summary(body: str) -> str:
    lines = body.splitlines()
    in_answer = False
    collected = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "## answer":
            in_answer = True
            continue
        if not in_answer:
            continue
        if stripped.startswith("## ") or stripped.startswith("<provenance>") or stripped.startswith("Provenance:"):
            break
        if stripped.startswith("Question:") or stripped in {"Evidence:", "Top matching evidence:", "ID-centered graph context:"}:
            continue
        if stripped:
            collected.append(stripped)
        if len(collected) >= 3:
            break
    return _truncate(" ".join(collected), 520)


def _strip_provenance(answer: str) -> str:
    return re.sub(r"\n?<provenance>\s*.*?\s*</provenance>\s*", "", answer, flags=re.DOTALL).strip()


_FINAL_ANSWER_HEADING_RE = re.compile(r"^#{1,6}\s")
_FINAL_ANSWER_HRULE_RE = re.compile(r"^(?:-{3,}|={3,}|\*{3,})$")
_FINAL_ANSWER_QUESTION_LINE_RE = re.compile(r"^\*{0,2}question\s*:?\*{0,2}", re.IGNORECASE)
_FINAL_ANSWER_PREFIX_RE = re.compile(r"^\*{0,2}answer\s*:\s*\*{0,2}", re.IGNORECASE)
_FINAL_ANSWER_CITATION_RE = re.compile(r"\s*\[citation:[^\]]*\]")


def _sanitize_final_answer_text(text: str) -> str:
    """Strip headers, repeated questions, "Answer:" prefix, and [citation: …] markers."""
    if not text:
        return ""
    cleaned = _strip_provenance(str(text))
    kept_lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _FINAL_ANSWER_HEADING_RE.match(stripped):
            continue
        if _FINAL_ANSWER_HRULE_RE.match(stripped):
            continue
        if _FINAL_ANSWER_QUESTION_LINE_RE.match(stripped):
            continue
        kept_lines.append(stripped)
    collapsed = _clean(" ".join(kept_lines))
    collapsed = _FINAL_ANSWER_PREFIX_RE.sub("", collapsed, count=1).strip()
    collapsed = _FINAL_ANSWER_CITATION_RE.sub("", collapsed)
    return _clean(collapsed)


_GENERIC_NODE_STAGES = {"", "evidence", "evidence_path", "row_group", "row_groups", "search", "result"}
_SLUG_STAGE_PREFIXES = ("row_groups/", "tables/", "columns/", "measurements/", "candidates/", "source_files/")


def _stage_from_slug(slug: str) -> str:
    """Derive a per-dataset stage from a KB slug (e.g. row_groups/permits/... → permits)."""
    if not slug:
        return ""
    cleaned = slug.replace("\\", "/").strip("/").lower()
    for prefix in _SLUG_STAGE_PREFIXES:
        if cleaned.startswith(prefix):
            remainder = cleaned[len(prefix):]
            head, _, rest = remainder.partition("/")
            if not head or "." in head or not rest:
                return ""
            return _normalize_stage(head)
    return ""


def _list_of_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [_clean(value)]
    if isinstance(value, list):
        return [_clean(str(item)) for item in value if _clean(str(item))]
    return []


def _meaningful_tokens(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9-]{3,}", value.lower())
    return [token for token in tokens if token not in {"with", "from", "this", "that", "evidence"}]


def _humanize_raw_detail(value: str) -> str:
    return re.sub(
        r"\b([a-z][a-z0-9_]+):",
        lambda match: match.group(1).replace("_", " ") + ":",
        _clean(value),
    )


def _humanize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _normalize_stage(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "evidence"


def _normalize_importance(value: str) -> str:
    normalized = _normalize_stage(value)
    if normalized in {"primary", "secondary", "rejected", "gap", "normal"}:
        return normalized
    return "normal"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split())


def _truncate(value: str, limit: int) -> str:
    compact = _clean(value)
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


__all__ = [
    "DataTidbitInterpretation",
    "InterpretedClaim",
    "ProofRow",
    "interpret_data_tidbits",
    "_sanitize_final_answer_text",
    "_stage_from_slug",
]
