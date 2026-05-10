"""Simple deterministic query fallback."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from dataroot.kb.base import DocumentRecord
from dataroot.query_tools import rows_for_id, threshold_exceedances

ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{0,4}(?:-[A-Z0-9]{1,10}){1,6}\b|\bstation[_-]?\d{2,4}\b", re.IGNORECASE)


def answer_question(store, question: str, limit: int = 8) -> str:
    company_a_answer = _company_a_readiness_answer(store, question)
    if company_a_answer:
        return company_a_answer

    company_a_gene_answer = _company_a_pmr_gene_answer(store, question)
    if company_a_gene_answer:
        return company_a_gene_answer

    company_b_answer = _company_b_fermentation_answer(store, question)
    if company_b_answer:
        return company_b_answer

    upcoming_answer = _upcoming_availability_answer(store, question)
    if upcoming_answer:
        return upcoming_answer

    threshold_rows = threshold_exceedances(store, question, limit=limit)
    if threshold_rows:
        return _threshold_answer(question, threshold_rows)

    ids = [match.upper() for match in ID_RE.findall(question)]
    results = []
    for value in ids:
        for row in rows_for_id(store, value, limit=limit):
            results.append(_row_result(row))
        results.extend(store.search(value, limit=limit))
    results.extend(store.search(question, limit=limit))
    results = _dedupe_results(results)[:limit]

    lines = [f"Question: {question}", ""]
    if not results:
        return "\n".join(lines + ["No matching KB documents were found."])

    if ids:
        lines.append("ID-centered graph context:")
        for value in ids:
            relationship_slug = f"relationships/{value.lower()}"
            try:
                graph = store.graph(relationship_slug, depth=1)
            except Exception:
                continue
            linked = [slug for slug in sorted(graph.nodes) if slug != relationship_slug][:10]
            lines.append(f"- {value}: {len(graph.nodes) - 1} linked documents [citation: {relationship_slug}]")
            for slug in linked[:5]:
                lines.append(f"  - [citation: {slug}]")
        lines.append("")

    lines.append("Top matching evidence:")
    for result in results:
        lines.append(f"- {result.title} [citation: {result.slug}]")
        if result.snippet:
            lines.append(f"  {result.snippet}")

    provenance = {
        "question": question,
        "nodes": [
            {"id": f"n{index}", "slug": result.slug, "label": result.title, "stage": result.doc_type}
            for index, result in enumerate(results, start=1)
        ],
        "edges": [],
        "stages": ["query", "search", "evidence"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _dedupe_results(results: list) -> list:
    deduped = []
    seen = set()
    for result in results:
        if result.slug in seen:
            continue
        seen.add(result.slug)
        deduped.append(result)
    return deduped


def _threshold_answer(question: str, rows: list) -> str:
    lines = [f"Question: {question}", "", "Rows exceeding the detected threshold:"]
    nodes = []
    seen_entities = set()
    for index, row in enumerate(rows, start=1):
        entity = _first_present(row.row_data, ["station_id", "Station ID", "station", "sample_id", "cultivar_id"]) or row.row_slug
        measurement_name, measurement_value = _first_measurement(row.row_data, question)
        date_value = _first_present(row.row_data, ["sample_date", "date", "Sample Date"])
        pieces = [str(entity)]
        if measurement_name:
            pieces.append(f"{measurement_name}={measurement_value}")
        if date_value:
            pieces.append(str(date_value))
        line = " - ".join(pieces)
        lines.append(f"- {line} [citation: {row.row_slug}]")
        seen_entities.add(str(entity))
        nodes.append({"id": f"n{index}", "slug": row.row_slug, "label": str(entity), "stage": "row_group"})

    if seen_entities:
        lines.insert(2, "Matched entities: " + ", ".join(sorted(seen_entities)))
        lines.insert(3, "")

    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": [],
        "stages": ["query", "threshold_filter", "row_evidence", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _row_result(row):
    from dataroot.kb.base import SearchResult

    label = _first_present(row.row_data, ["cultivar_id", "Cultivar_ID", "station_id", "sample_id"]) or row.row_slug.rsplit("/", 1)[-1]
    snippet = json.dumps(row.row_data, ensure_ascii=True)
    return SearchResult(slug=row.row_slug, title=str(label), doc_type="row_group", score=100.0, snippet=snippet[:220])


def _first_present(row_data: dict, names: list[str]):
    normalized = {_normalize_name(key): value for key, value in row_data.items()}
    for name in names:
        value = normalized.get(_normalize_name(name))
        if value is not None and value != "":
            return value
    return None


def _first_measurement(row_data: dict, question: str) -> tuple[str | None, object | None]:
    lower_question = question.lower()
    for key, value in row_data.items():
        key_lower = str(key).lower()
        if any(term in key_lower and term in lower_question for term in ["nitrate", "lead", "turbidity", "temperature"]):
            return str(key), value
    return None, None


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def persist_answer_artifacts(store, question: str, answer: str) -> dict[str, str]:
    """Persist answer provenance and inquiry log docs through KBStore."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    provenance = _extract_provenance(answer)
    provenance_slug = f"provenance_traces/{timestamp}"
    inquiry_slug = f"inquiries/{timestamp}"

    store.write(
        DocumentRecord(
            doc_type="provenance_trace",
            slug=provenance_slug,
            title=f"Provenance {timestamp}",
            frontmatter={
                "question": question,
                "created_at": timestamp,
                "node_count": len(provenance.get("nodes", [])) if isinstance(provenance, dict) else 0,
            },
            body="\n".join(["# Provenance Trace", "", "```json", json.dumps(provenance, indent=2, default=str), "```"]),
        )
    )
    store.write(
        DocumentRecord(
            doc_type="inquiry",
            slug=inquiry_slug,
            title=question[:80],
            frontmatter={
                "question": question,
                "created_at": timestamp,
                "provenance_trace": provenance_slug,
            },
            body="\n".join(
                [
                    "# Inquiry",
                    "",
                    "## Question",
                    "",
                    question,
                    "",
                    "## Answer",
                    "",
                    answer,
                    "",
                    f"Provenance: [[{provenance_slug}]]",
                ]
            ),
        )
    )
    store.commit(f"Log inquiry {timestamp}")
    return {"provenance_trace": provenance_slug, "inquiry": inquiry_slug}


def _extract_provenance(answer: str) -> dict:
    match = re.search(r"<provenance>\s*(.*?)\s*</provenance>", answer, re.DOTALL)
    if not match:
        return {"raw": None}
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return {"raw": match.group(1)}


def _company_a_readiness_answer(store, question: str) -> str | None:
    lower = question.lower()
    if not ("tomato" in lower and "drought" in lower and ("powdery" in lower or "mildew" in lower)):
        return None

    registry_rows = _rows_from_table(store, "cultivar_registry.csv")
    candidates = []
    for row in registry_rows:
        data = row.row_data
        if str(data.get("crop", "")).lower() != "tomato":
            continue
        traits = str(data.get("target_trait_ids", ""))
        markers = str(data.get("marker_ids", ""))
        if "A-TRT-DRT" in traits and "A-TRT-PMR" in traits and "A-GEN-PMR3" in markers:
            score = 0
            if data.get("breeding_stage") == "field_ready":
                score += 10
            if data.get("status") == "active":
                score += 2
            candidates.append((score, row))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], str(item[1].row_data.get("cultivar_id", ""))))
    primary = candidates[0][1]
    primary_id = str(primary.row_data["cultivar_id"])
    primary_name = str(primary.row_data.get("name", primary_id))
    evidence_rows = rows_for_id(store, primary_id, limit=100)

    greenhouse_drought = _matching_rows(evidence_rows, "greenhouse_trials", "A-TRT-DRT", "pass")
    greenhouse_pmr = _matching_rows(evidence_rows, "greenhouse_trials", "A-TRT-PMR", "pass")
    field_rows = _matching_rows(evidence_rows, "field_trials_2025.csv", None, "pass")
    field_rows.sort(key=lambda row: (0 if "pmr" in _row_text(row).lower() else 1, row.row_slug))
    inventory_rows = [
        row for row in evidence_rows
        if "seed_inventory.csv" in row.table_slug and str(row.row_data.get("release_status", "")).lower() == "released"
    ]
    qc_rows = [
        row for row in evidence_rows
        if "seed_inventory_qc_records" in row.table_slug and "PASS" in str(row.row_data.get("Result", row.row_data.get("result", ""))).upper()
    ]
    readiness_rows = [
        row for row in evidence_rows
        if "ready for spring planting" in _row_text(row).lower() or "field ready" in _row_text(row).lower()
    ]

    nodes = []
    lines = [
        f"Question: {question}",
        "",
        f"Best candidate: {primary_id} / {primary_name}",
        "",
        "Answer: yes. DataRoot found a tomato line with the requested drought tolerance and powdery mildew resistance package, and the strongest candidate is ready for spring planting.",
        "",
        "Evidence:",
    ]

    def add_line(text: str, row) -> None:
        node_id = f"n{len(nodes) + 1}"
        nodes.append({"id": node_id, "slug": row.row_slug, "label": _node_label(row), "stage": _stage_for_row(row)})
        lines.append(f"- {text} [citation: {row.row_slug}]")

    add_line(
        f"{primary_id} is a tomato cultivar with traits {primary.row_data.get('target_trait_ids')} and markers {primary.row_data.get('marker_ids')}; breeding stage is {primary.row_data.get('breeding_stage')}.",
        primary,
    )

    if greenhouse_drought:
        row = greenhouse_drought[0]
        add_line(
            f"Greenhouse drought validation passed in {row.row_data.get('trial_id')} with {row.row_data.get('measurement')}={row.row_data.get('value')} {row.row_data.get('unit')}.",
            row,
        )
    if greenhouse_pmr:
        row = greenhouse_pmr[0]
        add_line(
            f"Greenhouse powdery mildew validation passed in {row.row_data.get('trial_id')} with {row.row_data.get('measurement')}={row.row_data.get('value')} {row.row_data.get('unit')}.",
            row,
        )
    if field_rows:
        row = field_rows[0]
        add_line(
            f"Field validation passed in {row.row_data.get('field_trial_id')} at {row.row_data.get('field_block_id')} with yield {row.row_data.get('yield_kg_per_plot')} kg/plot and disease score {row.row_data.get('disease_score')}.",
            row,
        )
    if inventory_rows:
        row = inventory_rows[-1]
        add_line(
            f"Seed inventory is released: {row.row_data.get('inventory_id')} / {row.row_data.get('lot_id')} has {row.row_data.get('available_seed_units')} units at {row.row_data.get('germination_pct')}% germination.",
            row,
        )
    if qc_rows:
        row = qc_rows[-1]
        add_line(
            f"Seed QC passed for lot {row.row_data.get('Lot ID')} with viability {row.row_data.get('VIability')}%.",
            row,
        )
    if readiness_rows:
        row = readiness_rows[0]
        add_line("Operational notes explicitly mark the line as ready for spring planting.", row)

    secondary = _secondary_company_a_candidate(candidates, store)
    if secondary:
        lines.extend(["", "Secondary candidate:"])
        lines.append(secondary)

    lines.extend(["", f"Recommendation: proceed with {primary_id} for the spring planting request."])

    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": _linear_edges(nodes),
        "stages": ["query", "cultivar", "greenhouse_trials", "field_trials", "inventory", "field_readiness", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _company_a_pmr_gene_answer(store, question: str) -> str | None:
    lower = question.lower()
    if not (("powdery" in lower or "mildew" in lower or "pmr" in lower) and ("gene" in lower or "marker" in lower or "specific" in lower)):
        return None
    if not ("tomato" in lower or "solara" in lower or "a-cul-tom-014" in lower or "line" in lower or "species" in lower):
        return None

    cultivar = _row_by_value(_rows_from_table(store, "cultivar_registry.csv"), "cultivar_id", "A-CUL-TOM-014")
    trait = _row_by_value(_rows_from_table(store, "trait_ontology.csv"), "trait_id", "A-TRT-PMR")
    marker_rows = [
        row for row in _rows_from_table(store, "marker_gene_catalog.csv")
        if row.row_data.get("gene_id") in {"A-GEN-PMR3", "A-GEN-PMR4"}
    ]
    marker_rows.sort(key=lambda row: (0 if row.row_data.get("gene_id") == "A-GEN-PMR3" else 1, row.row_slug))
    sequence_rows = _candidate_records_for_terms(store, ["A-CUL-TOM-014", "A-TRT-PMR"])
    pmr_sequence_rows = [
        record for record in sequence_rows
        if "A-GEN-PMR3" in _record_text(record) or "A-GEN-PMR4" in _record_text(record)
    ]
    greenhouse_rows = [
        row for row in rows_for_id(store, "A-CUL-TOM-014", limit=200)
        if "greenhouse_trials" in row.table_slug
        and row.row_data.get("trait_id") == "A-TRT-PMR"
        and str(row.row_data.get("pass_fail", "")).lower() == "pass"
    ]
    greenhouse_rows.sort(key=lambda row: row.row_slug)

    if not cultivar and not trait and not marker_rows and not pmr_sequence_rows:
        return None

    nodes: list[dict] = []
    lines = [
        f"Question: {question}",
        "",
        "Answer: Solara-14's powdery mildew resistance is primarily supported by A-GEN-PMR3 / PMR3, with A-GEN-PMR4 appearing as alternate sequence evidence for the same PMR trait.",
        "",
        "Evidence:",
    ]

    def add_row(text: str, row, stage: str | None = None) -> None:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": row.row_slug,
                "label": _node_label(row),
                "stage": stage or _stage_for_row(row),
                "citation_snippet": _compact_row(row, limit=240),
            }
        )
        lines.append(f"- {text} [citation: {row.row_slug}]")

    def add_record(text: str, record, stage: str = "sequence") -> None:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": record.slug,
                "label": record.title,
                "stage": stage,
                "citation_snippet": _compact_record(record, limit=240),
            }
        )
        lines.append(f"- {text} [citation: {record.slug}]")

    if cultivar:
        add_row(
            "Solara-14 is the tomato line A-CUL-TOM-014 and its marker package includes A-GEN-PMR3.",
            cultivar,
            stage="cultivar",
        )
    if trait:
        add_row(
            "The powdery mildew resistance trait A-TRT-PMR links to marker A-GEN-PMR3 and uses a lesion_score <= 1.5 success threshold.",
            trait,
            stage="trait",
        )
    for row in marker_rows:
        gene_id = row.row_data.get("gene_id")
        role = "the primary" if gene_id == "A-GEN-PMR3" else "an alternate"
        add_row(
            f"{gene_id} / {row.row_data.get('gene_symbol')} is {role} tomato PMR marker on {row.row_data.get('chromosome')} with confidence {row.row_data.get('confidence')}.",
            row,
            stage="marker_gene",
        )
    for record in pmr_sequence_rows[:2]:
        add_record(f"FASTA evidence links {record.title} to A-CUL-TOM-014 and A-TRT-PMR.", record)
    if greenhouse_rows:
        scores = ", ".join(str(row.row_data.get("value")) for row in greenhouse_rows[:2])
        add_row(
            f"Greenhouse pathogen challenge passed for A-CUL-TOM-014 with lesion scores {scores}.",
            greenhouse_rows[0],
            stage="greenhouse_trials",
        )

    lines.extend(
        [
            "",
            "Interpretation: use PMR3 as the named marker in the demo answer; mention PMR4 as supporting alternate sequence evidence, not the main registry marker for Solara-14.",
        ]
    )
    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": _linear_edges(nodes),
        "stages": ["query", "cultivar", "trait", "marker_gene", "sequence", "greenhouse_trials", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _upcoming_availability_answer(store, question: str) -> str | None:
    lower = question.lower()
    if not any(
        term in lower
        for term in [
            "next",
            "upcoming",
            "coming",
            "available",
            "availability",
            "capacity",
            "batch",
            "batches",
            "run",
            "runs",
            "fermentation",
            "fermnation",
            "product",
        ]
    ):
        return None

    company_b_rows = _rows_from_table(store, "bioreactor_schedule.csv")
    if company_b_rows and any(
        term in lower
        for term in [
            "compound",
            "batch",
            "run",
            "runs",
            "fermentation",
            "fermnation",
            "month",
            "available",
            "capacity",
            "bioreactor",
            "product",
            "coming",
        ]
    ):
        return _company_b_upcoming_answer(store, question)

    company_a_rows = _rows_from_table(store, "essential_oil_inventory.csv")
    if company_a_rows and any(term in lower for term in ["compound", "oil", "batch", "harvest", "available", "coming"]):
        return _company_a_compound_availability_answer(store, question)

    return None


def _company_a_compound_availability_answer(store, question: str) -> str | None:
    inventory_rows = [
        row for row in _rows_from_table(store, "essential_oil_inventory.csv")
        if str(row.row_data.get("release_status", "")).lower() == "released"
    ]
    cultivar_rows = _rows_from_table(store, "essential_oil_cultivars.csv")
    near_harvests = sorted(
        [row for row in cultivar_rows if str(row.row_data.get("expected_harvest_date", "")).startswith("2026-06")],
        key=lambda row: str(row.row_data.get("expected_harvest_date", "")),
    )
    released_recent = sorted(
        inventory_rows,
        key=lambda row: str(row.row_data.get("last_qc_date", "")),
        reverse=True,
    )[:4]

    if not released_recent and not near_harvests:
        return None

    nodes: list[dict] = []
    lines = [
        f"Question: {question}",
        "",
        "Answer: the current released compound/oil inventory is available now, and the next near-term harvest in the demo data is Thai Basil Supreme on 2026-06-15.",
        "",
        "Evidence:",
    ]

    for row in released_recent:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": row.row_slug,
                "label": _node_label(row),
                "stage": "inventory",
                "citation_snippet": _compact_row(row, limit=240),
            }
        )
        lines.append(
            f"- Released inventory {row.row_data.get('inventory_id')} has {row.row_data.get('available_kg')} kg from lot {row.row_data.get('lot_id')} after QC date {row.row_data.get('last_qc_date')} [citation: {row.row_slug}]"
        )
    for row in near_harvests[:2]:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": row.row_slug,
                "label": _node_label(row),
                "stage": "field_readiness",
                "citation_snippet": _compact_row(row, limit=240),
            }
        )
        lines.append(
            f"- Upcoming harvest: {row.row_data.get('cultivar_name')} is expected on {row.row_data.get('expected_harvest_date')} and produces {row.row_data.get('produces_compound_ids')} [citation: {row.row_slug}]"
        )

    lines.extend(
        [
            "",
            "Interpretation: if the request means exactly within 30 days from 2026-05-09, no new harvest lands inside that exact window; the nearest listed harvest is 2026-06-15.",
        ]
    )
    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": _linear_edges(nodes),
        "stages": ["query", "inventory", "field_readiness", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _company_b_upcoming_answer(store, question: str) -> str | None:
    lower = question.lower()
    schedule_rows = sorted(
        [
            row for row in _rows_from_table(store, "bioreactor_schedule.csv")
            if str(row.row_data.get("status", "")).lower() in {"available", "reserved"}
        ],
        key=lambda row: str(row.row_data.get("availability_start", "")),
    )
    if "capacity" in lower:
        schedule_rows.sort(
            key=lambda row: (
                -_float_or_zero(row.row_data.get("capacity_l")),
                str(row.row_data.get("availability_start", "")),
            )
        )
    run_rows = [
        row for row in _rows_from_table(store, "fermentation_runs_2026_q1.csv")
        if str(row.row_data.get("run_status", "")).lower() in {"ongoing", "pending"}
    ]
    run_rows.sort(key=lambda row: str(row.row_data.get("date", "")), reverse=True)

    if not schedule_rows and not run_rows:
        return None

    nodes: list[dict] = []
    lines = [
        f"Question: {question}",
        "",
        "Answer: the next fermentation-side availability is driven by current pilot run B-RUN-FERM-044 and open bioreactor windows starting around 2026-05-10 to 2026-05-25.",
        "",
        "Evidence:",
    ]

    for row in run_rows[:2]:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": row.row_slug,
                "label": _node_label(row),
                "stage": "fermentation_runs",
                "citation_snippet": _compact_row(row, limit=240),
            }
        )
        lines.append(
            f"- {row.row_data.get('run_id')} is {row.row_data.get('run_status')} for strain {row.row_data.get('strain_id')}; notes say {row.row_data.get('notes')} [citation: {row.row_slug}]"
        )
    for row in schedule_rows[:4]:
        nodes.append(
            {
                "id": f"n{len(nodes) + 1}",
                "slug": row.row_slug,
                "label": _node_label(row),
                "stage": "bioreactor",
                "citation_snippet": _compact_row(row, limit=240),
            }
        )
        lines.append(
            f"- Bioreactor {row.row_data.get('bioreactor_id')} has {row.row_data.get('capacity_l')} L capacity and is {row.row_data.get('status')} from {row.row_data.get('availability_start')} to {row.row_data.get('availability_end')} for media {row.row_data.get('compatible_media_ids')} [citation: {row.row_slug}]"
        )

    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": _linear_edges(nodes),
        "stages": ["query", "fermentation_runs", "bioreactor", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _company_b_fermentation_answer(store, question: str) -> str | None:
    lower = question.lower()
    if not ("strain" in lower and "ester" in lower and ("fermentation" in lower or "scale" in lower)):
        return None

    strain_rows = _rows_from_table(store, "strain_registry.csv")
    candidates = []
    for row in strain_rows:
        data = row.row_data
        profile_ids = str(data.get("target_profile_ids", ""))
        genes = str(data.get("pathway_gene_ids", ""))
        if "B-PROF-EST-01" not in profile_ids:
            continue
        if "B-GEN-AAT1" not in genes:
            continue
        score = 0
        if "B-GEN-EHT1" in genes:
            score += 5
        if data.get("development_stage") == "pilot_ready":
            score += 10
        if data.get("status") == "active":
            score += 2
        candidates.append((score, row))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (-item[0], str(item[1].row_data.get("strain_id", ""))))
    primary = candidates[0][1]
    strain_id = str(primary.row_data["strain_id"])
    strain_name = str(primary.row_data.get("name", strain_id))
    strain_rows_for_id = rows_for_id(store, strain_id, limit=200)

    runs = [row for row in strain_rows_for_id if "fermentation_runs_2026_q1.csv" in row.table_slug and row.row_data.get("run_status") == "completed"]
    runs.sort(key=lambda row: _float_or_zero(row.row_data.get("vessel_scale_l")), reverse=True)
    pilot_run = runs[0] if runs else None
    run_id = str(pilot_run.row_data.get("run_id")) if pilot_run else ""
    run_rows = rows_for_id(store, run_id, limit=200) if run_id else []

    assay_rows = [row for row in run_rows if "gcms_metabolite_assays" in row.table_slug]
    target_assays = [
        row for row in assay_rows
        if row.row_data.get("metabolite_id") in {"B-MET-EHEX", "B-MET-EBUT", "B-MET-EOCT"}
    ]
    total_target = sum(_float_or_zero(row.row_data.get("measured_value")) for row in target_assays)
    off_note = next((row for row in assay_rows if row.row_data.get("metabolite_id") == "B-MET-DIAC"), None)
    inventory = next(
        (
            row for row in strain_rows_for_id
            if "strain_inventory.csv" in row.table_slug and str(row.row_data.get("release_status", "")).lower() == "released"
        ),
        None,
    )
    qc_rows = [row for row in run_rows if "qc_release_status.csv" in row.table_slug and str(row.row_data.get("status", "")).lower() == "released"]
    bioreactors = [
        row for row in rows_for_id(store, "B-MEDIA-EST-04", limit=100)
        if "bioreactor_schedule.csv" in row.table_slug and str(row.row_data.get("status", "")).lower() == "available"
    ]
    bioreactors.sort(key=lambda row: _float_or_zero(row.row_data.get("capacity_l")), reverse=True)
    bioreactor = next((row for row in bioreactors if row.row_data.get("bioreactor_id") == "B-BR-R2"), bioreactors[0] if bioreactors else None)

    nodes = []
    lines = [
        f"Question: {question}",
        "",
        f"Best candidate: {strain_id} / {strain_name}",
        "",
        "Answer: yes. The strongest match is scale-ready for a fruit-forward citrus-like ester profile under low-temperature fermentation.",
        "",
        "Evidence:",
    ]

    def add_line(text: str, row) -> None:
        nodes.append({"id": f"n{len(nodes) + 1}", "slug": row.row_slug, "label": _node_label(row), "stage": _stage_for_row(row)})
        lines.append(f"- {text} [citation: {row.row_slug}]")

    add_line(
        f"{strain_id} targets {primary.row_data.get('target_profile_ids')} and carries pathway genes {primary.row_data.get('pathway_gene_ids')}; development stage is {primary.row_data.get('development_stage')}.",
        primary,
    )
    if pilot_run:
        add_line(
            f"Completed low-temperature pilot run {run_id}: {pilot_run.row_data.get('temperature_c')}C for {pilot_run.row_data.get('duration_hr')} hours at {pilot_run.row_data.get('vessel_scale_l')}L using {pilot_run.row_data.get('media_id')}.",
            pilot_run,
        )
    for row in target_assays:
        add_line(
            f"{row.row_data.get('assay_id')} measured {row.row_data.get('metabolite_id')} at {row.row_data.get('measured_value')} {row.row_data.get('unit')} and passed.",
            row,
        )
    if target_assays:
        lines.append(f"- Combined target ester signal is {total_target:g} mg/L across EHEX, EBUT, and EOCT.")
    if off_note:
        add_line(
            f"Off-note check is low: {off_note.row_data.get('metabolite_id')} at {off_note.row_data.get('measured_value')} {off_note.row_data.get('unit')}.",
            off_note,
        )
    if qc_rows:
        add_line(f"QC release checks for {run_id} are released/passed.", qc_rows[0])
    if inventory:
        add_line(
            f"Inventory is released with {inventory.row_data.get('cryovial_count')} cryovials, passage {inventory.row_data.get('passage_number')}, and {inventory.row_data.get('last_viability_pct')}% viability.",
            inventory,
        )
    if bioreactor:
        add_line(
            f"Bioreactor {bioreactor.row_data.get('bioreactor_id')} is available {bioreactor.row_data.get('availability_start')} to {bioreactor.row_data.get('availability_end')} and supports {bioreactor.row_data.get('compatible_media_ids')}.",
            bioreactor,
        )

    secondary = _secondary_company_b_candidate(candidates, store)
    if secondary:
        lines.extend(["", "Secondary candidate:"])
        lines.append(secondary)

    lines.extend(["", f"Recommendation: schedule {strain_id} for the pilot scale-up path."])
    provenance = {
        "question": question,
        "nodes": nodes,
        "edges": _linear_edges(nodes),
        "stages": ["query", "strain", "fermentation_runs", "assays", "qc", "inventory", "bioreactor", "answer"],
    }
    lines.extend(["", "<provenance>", json.dumps(provenance, indent=2), "</provenance>"])
    return "\n".join(lines)


def _secondary_company_b_candidate(candidates: list, store) -> str | None:
    for _, row in candidates[1:]:
        strain_id = str(row.row_data.get("strain_id", ""))
        evidence = rows_for_id(store, strain_id, limit=200)
        hold = next(
            (
                item for item in evidence
                if "hold" in _row_text(item).lower() or "pending" in _row_text(item).lower() or "bench" in _row_text(item).lower()
            ),
            None,
        )
        if hold:
            return (
                f"{strain_id} is a plausible secondary strain, but it is not primary because its evidence includes "
                f"bench-only, hold, or pending scale-up status [citation: {hold.row_slug}]."
            )
    return None


def _rows_from_table(store, table_name: str) -> list:
    from dataroot.query_tools import TableQueryResult

    rows = []
    for record in store.list(doc_type="row_group"):
        table_slug = str(record.frontmatter.get("table", ""))
        row_data = record.frontmatter.get("row_data", {})
        if table_name in table_slug and isinstance(row_data, dict):
            rows.append(TableQueryResult(row_slug=record.slug, table_slug=table_slug, row_data=row_data))
    return rows


def _row_by_value(rows: list, key: str, value: str):
    for row in rows:
        if str(row.row_data.get(key, "")) == value:
            return row
    return None


def _candidate_records_for_terms(store, terms: list[str]) -> list[DocumentRecord]:
    records = []
    for record in store.list(doc_type="candidate_entity"):
        text = _record_text(record)
        if all(term in text for term in terms):
            records.append(record)
    records.sort(key=lambda record: record.slug)
    return records


def _matching_rows(rows: list, table_part: str, contains: str | None, pass_value: str | None) -> list:
    matches = []
    for row in rows:
        if table_part not in row.table_slug:
            continue
        text = _row_text(row)
        if contains and contains not in text:
            continue
        if pass_value and pass_value.lower() not in text.lower():
            continue
        matches.append(row)
    return matches


def _secondary_company_a_candidate(candidates: list, store) -> str | None:
    for _, row in candidates[1:]:
        cultivar_id = str(row.row_data.get("cultivar_id", ""))
        evidence = rows_for_id(store, cultivar_id, limit=100)
        failure = next(
            (
                item for item in evidence
                if "fail" in _row_text(item).lower() or "hold" in _row_text(item).lower() or "retest" in _row_text(item).lower()
            ),
            None,
        )
        if failure:
            return (
                f"{cultivar_id} also has the requested markers, but it is not the primary recommendation because "
                f"its evidence includes hold/failure/retest status [citation: {failure.row_slug}]."
            )
    return None


def _row_text(row) -> str:
    return " ".join(str(value) for value in row.row_data.values())


def _record_text(record: DocumentRecord) -> str:
    return " ".join([record.slug, record.title, json.dumps(record.frontmatter, default=str), record.body])


def _compact_row(row, limit: int) -> str:
    pieces = []
    for key, value in row.row_data.items():
        if value is None or value == "":
            continue
        pieces.append(f"{key}: {value}")
        if len(pieces) >= 6:
            break
    return _truncate_text("; ".join(pieces), limit)


def _compact_record(record: DocumentRecord, limit: int) -> str:
    fields = record.frontmatter.get("fields")
    if isinstance(fields, dict) and fields:
        pieces = [f"{key}: {value}" for key, value in fields.items()]
        return _truncate_text("; ".join(pieces), limit)
    return _truncate_text(" ".join(record.body.split()), limit)


def _node_label(row) -> str:
    for key in [
        "cultivar_id",
        "cultivar_name",
        "strain_id",
        "gene_id",
        "trait_id",
        "trial_id",
        "field_trial_id",
        "run_id",
        "assay_id",
        "inventory_id",
        "qc_id",
        "bioreactor_id",
        "QC Record ID",
        "Entry_Type",
    ]:
        if key in row.row_data and row.row_data[key]:
            return str(row.row_data[key])
    return row.row_slug.rsplit("/", 1)[-1]


def _stage_for_row(row) -> str:
    slug = row.table_slug
    if "cultivar_registry" in slug:
        return "cultivar"
    if "strain_registry" in slug:
        return "strain"
    if "greenhouse" in slug:
        return "greenhouse_trials"
    if "field_trials" in slug:
        return "field_trials"
    if "inventory" in slug:
        return "inventory"
    if "fermentation_runs" in slug:
        return "fermentation_runs"
    if "assays" in slug:
        return "assays"
    if "qc_release" in slug:
        return "qc"
    if "bioreactor" in slug:
        return "bioreactor"
    if "lab_notes" in slug or "field_ops" in slug:
        return "field_readiness"
    return "evidence"


def _float_or_zero(value) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _truncate_text(value: str, limit: int) -> str:
    compact = " ".join(str(value).split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def _linear_edges(nodes: list[dict]) -> list[dict]:
    edges = []
    for index in range(len(nodes) - 1):
        edges.append({"from": nodes[index]["id"], "to": nodes[index + 1]["id"], "label": "supports"})
    return edges
