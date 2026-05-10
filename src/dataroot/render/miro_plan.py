"""Build viewer-friendly Miro board plans from provenance traces."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from dataroot.render.interpretation import (
    DataTidbitInterpretation,
    ProofRow,
    interpret_data_tidbits,
)


@dataclass
class BoardCard:
    id: str
    title: str
    detail: str
    stage: str
    citation: str = ""
    source: str = ""
    kind: str = "evidence"
    emphasis: str = "normal"


@dataclass
class BoardConnection:
    source: str
    target: str
    label: str = "supports"
    evidence: str = ""


@dataclass
class BoardPlan:
    title: str
    context_label: str
    question: str
    answer: str
    recommendation: str
    confidence: str
    retrieval_summary: str
    evidence_cards: list[BoardCard] = field(default_factory=list)
    alternatives: list[BoardCard] = field(default_factory=list)
    connections: list[BoardConnection] = field(default_factory=list)
    audit_notes: list[str] = field(default_factory=list)
    proof_rows: list[ProofRow] = field(default_factory=list)
    interpreter_source: str = "deterministic_fallback"
    planner_source: str = "deterministic_fallback"


def plan_miro_board(
    trace: dict,
    *,
    store=None,
    inquiry_slug: str | None = None,
    answer_text: str | None = None,
    context_label: str | None = None,
    interpretation: DataTidbitInterpretation | None = None,
) -> BoardPlan:
    """Return a story-first board plan with deterministic fallback."""

    interpretation = interpretation or interpret_data_tidbits(
        trace,
        store=store,
        inquiry_slug=inquiry_slug,
        answer_text=answer_text,
    )
    fallback = _deterministic_plan(
        trace,
        store=store,
        inquiry_slug=inquiry_slug,
        answer_text=answer_text,
        context_label=context_label,
        interpretation=interpretation,
    )
    if os.environ.get("DATAROOT_USE_MIRO_PLANNER") == "0" or not os.environ.get("OPENAI_API_KEY"):
        return fallback

    try:
        return _model_plan(trace, fallback)
    except Exception:
        return fallback


def _deterministic_plan(
    trace: dict,
    *,
    store=None,
    inquiry_slug: str | None,
    answer_text: str | None,
    context_label: str | None,
    interpretation: DataTidbitInterpretation,
) -> BoardPlan:
    question = _clean(str(trace.get("question") or "DataRoot inquiry"))
    plan_context = _clean(context_label or _infer_context_label(trace))
    summary = trace.get("provenance_summary") if isinstance(trace.get("provenance_summary"), dict) else {}
    answer = interpretation.takeaway or _answer_from_inputs(
        trace,
        store=store,
        inquiry_slug=inquiry_slug,
        answer_text=answer_text,
    )
    recommendation = _clean(str(summary.get("primary_candidate") or _first_sentence(answer) or "Review the evidence chain"))
    confidence = _clean(interpretation.confidence or str(summary.get("confidence") or "supported"))

    contexts = [_node_context(node, store=store) for node in trace.get("nodes") or [] if isinstance(node, dict)]
    proof_by_ref = {row.evidence_ref: row for row in interpretation.proof_rows if row.evidence_ref}
    evidence_cards = _cards_from_interpretation(interpretation, proof_by_ref)

    if not evidence_cards:
        seen = set()
        for node_context in contexts:
            if node_context["stage"] in {"query", "answer"}:
                continue
            if node_context["id"] in seen:
                continue
            seen.add(node_context["id"])
            evidence_cards.append(
                BoardCard(
                    id=node_context["id"],
                    title=node_context["label"],
                    detail=node_context["detail"],
                    stage=node_context["stage"],
                    citation=node_context["slug"],
                    source=node_context["source"],
                    emphasis=_emphasis_for(node_context["label"], summary),
                )
            )

    if not evidence_cards:
        for node_context in contexts:
            if node_context["stage"] == "answer":
                continue
            evidence_cards.append(
                BoardCard(
                    id=node_context["id"],
                    title=node_context["label"],
                    detail=node_context["detail"],
                    stage=node_context["stage"],
                    citation=node_context["slug"],
                    source=node_context["source"],
                    emphasis="normal",
                )
            )

    alternatives = _alternative_cards_from_caveats(interpretation.caveats) or _alternative_cards(summary)
    sources = sorted({card.source for card in evidence_cards if card.source})
    stages = sorted({card.stage for card in evidence_cards if card.stage})
    retrieval_summary = interpretation.retrieval_explanation or (
        f"GitKB retrieved {len(evidence_cards)} cited records across "
        f"{len(sources) or len(stages) or 1} data sources: {', '.join(sources[:4] or stages[:4])}."
    )

    connections = []
    card_ids = {card.id for card in evidence_cards}
    for edge in trace.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("from") or edge.get("source") or "")
        target = str(edge.get("to") or edge.get("target") or "")
        if source in card_ids or target in card_ids:
            connections.append(
                BoardConnection(
                    source=source,
                    target=target,
                    label=_clean(str(edge.get("label") or "supports")),
                    evidence=_clean(str(edge.get("evidence") or edge.get("description") or "")),
                )
            )

    if not connections:
        ordered = [card.id for card in evidence_cards]
        connections = [
            BoardConnection(source=ordered[index], target=ordered[index + 1], label="supports")
            for index in range(max(0, len(ordered) - 1))
        ]

    audit_notes = [
        f"Interpreter: {interpretation.source}",
        "Miro planner: deterministic_fallback",
        f"Trace nodes: {len(trace.get('nodes') or [])}",
        f"Trace edges: {len(trace.get('edges') or [])}",
    ]
    if inquiry_slug:
        audit_notes.append(f"Inquiry: {inquiry_slug}")

    return BoardPlan(
        title=f"{plan_context} evidence path",
        context_label=plan_context,
        question=question,
        answer=answer,
        recommendation=recommendation,
        confidence=confidence,
        retrieval_summary=retrieval_summary,
        evidence_cards=evidence_cards,
        alternatives=alternatives,
        connections=connections,
        audit_notes=audit_notes,
        proof_rows=interpretation.proof_rows,
        interpreter_source=interpretation.source,
        planner_source="deterministic_fallback",
    )


def _cards_from_interpretation(
    interpretation: DataTidbitInterpretation,
    proof_by_ref: dict[str, ProofRow],
) -> list[BoardCard]:
    cards = []
    for index, claim in enumerate(interpretation.claims, start=1):
        citation = next((ref for ref in claim.evidence_refs if ref in proof_by_ref), "")
        if proof_by_ref and not citation:
            continue
        proof = proof_by_ref.get(citation)
        source = claim.source_label or (proof.source_label if proof else "")
        stage = _normalize_stage(proof.stage if proof else source or "evidence_path")
        cards.append(
            BoardCard(
                id=f"claim_{index}",
                title=_clean(claim.claim),
                detail=_clean(claim.why_it_matters),
                stage=stage,
                citation=citation,
                source=source,
                emphasis=_normalize_emphasis(claim.importance),
            )
        )
    return cards


def _alternative_cards_from_caveats(caveats: list[str]) -> list[BoardCard]:
    cards = []
    for index, caveat in enumerate(caveats[:4], start=1):
        text = _clean(caveat)
        if not text:
            continue
        cards.append(
            BoardCard(
                id=f"caveat_{index}",
                title="Caveat",
                detail=text,
                stage="alternatives",
                kind="alternative",
                emphasis="gap",
            )
        )
    return cards


def _model_plan(trace: dict, fallback: BoardPlan) -> BoardPlan:
    from dataroot.agent.codex_client import CodexClient

    payload = {
        "question": fallback.question,
        "answer": fallback.answer,
        "recommendation": fallback.recommendation,
        "confidence": fallback.confidence,
        "context_label": fallback.context_label,
        "retrieval_summary": fallback.retrieval_summary,
        "evidence_cards": [card.__dict__ for card in fallback.evidence_cards],
        "alternatives": [card.__dict__ for card in fallback.alternatives],
        "connections": [connection.__dict__ for connection in fallback.connections],
        "proof_rows": [row.__dict__ for row in fallback.proof_rows],
        "interpreter_source": fallback.interpreter_source,
        "trace_summary": trace.get("provenance_summary"),
    }
    allowed_citations = (
        {card.citation for card in fallback.evidence_cards if card.citation}
        | {row.evidence_ref for row in fallback.proof_rows if row.evidence_ref}
    )
    system_prompt = (
        "You turn interpreted DataRoot claims into a concise Miro board plan for a demo viewer. "
        "Return only JSON with title, context_label, question, answer, recommendation, confidence, "
        "retrieval_summary, evidence_cards, alternatives, connections, and audit_notes. "
        "Keep the fixed board story Question -> GitKB retrieval -> Evidence path -> Final answer. "
        "Do not invent citations; reuse only citations already present in proof_rows or evidence_cards. "
        "Do not add new scientific facts beyond the interpreted claims."
    )
    result = CodexClient().run(
        system_prompt,
        [{"role": "user", "content": json.dumps(payload, ensure_ascii=True)}],
        tools=[],
        temperature=0.2,
        max_retries=1,
    )
    if not result.final_output:
        raise ValueError("model planner returned no output")
    raw = result.final_output.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    data = json.loads(raw)
    plan = _plan_from_payload(data, fallback=fallback, allowed_citations=allowed_citations)
    if not plan.evidence_cards:
        raise ValueError("model planner returned no evidence cards")
    return plan


def _plan_from_payload(data: dict, *, fallback: BoardPlan, allowed_citations: set[str]) -> BoardPlan:
    def cards(values: Any, kind: str) -> list[BoardCard]:
        output = []
        if not isinstance(values, list):
            return output
        fallback_by_id = {card.id: card for card in fallback.evidence_cards + fallback.alternatives}
        for index, item in enumerate(values, start=1):
            if not isinstance(item, dict):
                continue
            card_id = _clean(str(item.get("id") or f"{kind}_{index}"))
            base = fallback_by_id.get(card_id)
            citation = _clean(str(item.get("citation") or (base.citation if base else "")))
            if citation and citation not in allowed_citations and kind == "evidence":
                citation = base.citation if base else ""
            if kind == "evidence" and allowed_citations and not citation:
                continue
            output.append(
                BoardCard(
                    id=card_id,
                    title=_clean(str(item.get("title") or (base.title if base else kind.title()))),
                    detail=_clean(str(item.get("detail") or (base.detail if base else ""))),
                    stage=_normalize_stage(str(item.get("stage") or (base.stage if base else kind))),
                    citation=citation,
                    source=_clean(str(item.get("source") or (base.source if base else ""))),
                    kind=_clean(str(item.get("kind") or kind)),
                    emphasis=_clean(str(item.get("emphasis") or (base.emphasis if base else "normal"))),
                )
            )
        return output

    connections = []
    for item in data.get("connections") or []:
        if not isinstance(item, dict):
            continue
        source = _clean(str(item.get("source") or ""))
        target = _clean(str(item.get("target") or ""))
        if source and target:
            connections.append(
                BoardConnection(
                    source=source,
                    target=target,
                    label=_clean(str(item.get("label") or "supports")),
                    evidence=_clean(str(item.get("evidence") or "")),
                )
            )

    audit_notes = [_clean(str(item)) for item in data.get("audit_notes") or fallback.audit_notes]
    if not any(note.lower().startswith("miro planner:") for note in audit_notes):
        audit_notes.insert(0, "Miro planner: agent")
    else:
        audit_notes = ["Miro planner: agent" if note.lower().startswith("miro planner:") else note for note in audit_notes]

    return BoardPlan(
        title=_clean(str(data.get("title") or fallback.title)),
        context_label=_clean(str(data.get("context_label") or fallback.context_label)),
        question=_clean(str(data.get("question") or fallback.question)),
        answer=_clean(str(data.get("answer") or fallback.answer)),
        recommendation=_clean(str(data.get("recommendation") or fallback.recommendation)),
        confidence=_clean(str(data.get("confidence") or fallback.confidence)),
        retrieval_summary=_clean(str(data.get("retrieval_summary") or fallback.retrieval_summary)),
        evidence_cards=cards(data.get("evidence_cards"), "evidence"),
        alternatives=cards(data.get("alternatives"), "alternative"),
        connections=connections or fallback.connections,
        audit_notes=audit_notes,
        proof_rows=fallback.proof_rows,
        interpreter_source=fallback.interpreter_source,
        planner_source="agent",
    )


def _answer_from_inputs(trace: dict, *, store=None, inquiry_slug: str | None, answer_text: str | None) -> str:
    if answer_text:
        return _clean(_strip_provenance(answer_text))
    if store and inquiry_slug:
        try:
            record = store.read(inquiry_slug)
            answer = _extract_answer_summary(record.body)
            if answer:
                return answer
        except Exception:
            pass
    summary = trace.get("provenance_summary")
    if isinstance(summary, dict):
        reasoning = summary.get("reasoning") or summary.get("summary")
        if reasoning:
            return _clean(str(reasoning))
    if isinstance(summary, str):
        return _clean(summary)
    return "DataRoot found a cited evidence path for this question."


def _infer_context_label(trace: dict) -> str:
    text = json.dumps(trace, ensure_ascii=True).lower()
    if any(term in text for term in ["a-cul", "tomato", "agritrait", "solara", "powdery"]):
        return "CropProtectorAI"
    if any(term in text for term in ["b-run", "fermentation", "strain", "bioreactor"]):
        return "BioReactorAI"
    return "DataRoot demo"


def _node_context(node: dict, *, store=None) -> dict[str, str]:
    slug = _clean(str(node.get("slug") or ""))
    label = _clean(str(node.get("label") or node.get("id") or slug or "Evidence"))
    stage = _normalize_stage(str(node.get("stage") or "evidence"))
    detail = _clean(str(node.get("citation_snippet") or node.get("description") or node.get("detail") or ""))
    source = _source_from_slug(slug)
    if store and slug and not node.get("visual_only"):
        try:
            record = store.read(slug)
            source = _source_from_record(record) or source
            if not detail:
                detail = _record_summary(record)
        except Exception:
            pass
    if not detail:
        detail = f"Retrieved from {source or slug or stage}."
    return {
        "id": _clean(str(node.get("id") or slug or label)),
        "slug": slug,
        "label": label,
        "stage": stage,
        "detail": detail,
        "source": source,
    }


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


def _record_summary(record, limit: int = 240) -> str:
    row_data = record.frontmatter.get("row_data")
    if isinstance(row_data, dict) and row_data:
        pieces = [f"{key}: {value}" for key, value in row_data.items() if value is not None and value != ""]
        return _truncate("; ".join(pieces[:6]), limit)
    fields = record.frontmatter.get("fields")
    if isinstance(fields, dict) and fields:
        pieces = [f"{key}: {value}" for key, value in fields.items() if value is not None and value != ""]
        return _truncate("; ".join(pieces[:6]), limit)
    body = " ".join(record.body.split())
    return _truncate(body or record.title, limit)


def _alternative_cards(summary: dict) -> list[BoardCard]:
    cards = []
    for key, emphasis, title in [
        ("secondary_candidates", "secondary", "Secondary option"),
        ("insufficient_candidates", "rejected", "Rejected option"),
        ("insufficient_context", "gap", "Open gap"),
    ]:
        values = summary.get(key) if isinstance(summary, dict) else None
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for index, value in enumerate(values, start=1):
            text = _clean(str(value))
            if not text:
                continue
            cards.append(
                BoardCard(
                    id=f"{key}_{index}",
                    title=title,
                    detail=text,
                    stage="alternatives",
                    kind="alternative",
                    emphasis=emphasis,
                )
            )
    return cards


def _emphasis_for(label: str, summary: dict) -> str:
    if not isinstance(summary, dict):
        return "normal"
    text = json.dumps(summary, ensure_ascii=True).lower()
    lower = label.lower()
    if lower and lower in str(summary.get("primary_candidate", "")).lower():
        return "primary"
    secondary = json.dumps(summary.get("secondary_candidates", []), ensure_ascii=True).lower()
    rejected = json.dumps(summary.get("insufficient_candidates", []), ensure_ascii=True).lower()
    if lower and lower in secondary:
        return "secondary"
    if lower and lower in rejected:
        return "rejected"
    if lower and lower in text and any(term in lower for term in ["pass", "ready", "released"]):
        return "primary"
    return "normal"


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


def _first_sentence(value: str) -> str:
    match = re.search(r"(.+?[.!?])(?:\s|$)", value)
    return match.group(1) if match else value[:160]


def _normalize_stage(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "evidence"


def _normalize_emphasis(value: str) -> str:
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
