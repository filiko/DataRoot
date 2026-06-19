---
purpose: Hour-by-hour build plan.
prerequisites: CONTEXT.md, docs/architecture.md §9
read-when: Starting the hackathon build, tracking progress.
---

# Build plan — docs/build-plan.md

Hour-by-hour plan for the hackathon weekend. Assumes ~30 hours
of focused build (Friday eve through Sunday demo).

← Back to [CONTEXT.md](../CONTEXT.md)

## Hour 0–2: Foundation

- Scaffold dataroot/ Python project with uv.
- Create FastAPI skeleton, healthcheck endpoint.
- Implement KBStore adapter interface (`read/search/write/update/commit`) with GitKBStore first and LocalMarkdownStore as fallback.
- Commit CONTEXT.md (this doc) into the repo.

## Hour 2–4: Generic workspace profiler

- CSV parser (pandas.read_csv).
- XLSX parser (openpyxl or pandas.read_excel).
- JSON parser (json.load, handle both array-of-objects and nested).
- Markdown/text parser.
- FASTA parser if present.
- Test: run `dataroot profile ExampleData/water_quality/`, verify generic records persisted through KBStore.

## Hour 4–8: Generic KB record generation

- Profile → document emitter for all generic types (source_file, table, column, row_group, candidate_entity, measurement, relationship).
- Test: run `dataroot profile` on water_quality dataset, verify records have correct types/frontmatter and are searchable through GitKBStore.

## Hour 8–11: Generic linker

- Implement: file→table, table→column, likely PK/FK detection, repeated IDs, date/time columns, geo/location columns, measurement/unit columns, text mentions.
- Confidence scoring for wikilinks.
- Test: run `dataroot link` on profiled workspace, verify wikilinks created, run `kb_graph` to see the graph.

## Hour 11–14: Domain Spec Generator

- Add `dataroot infer-domain-spec`.
- Role A prompt reads generic KB docs, writes `.dataroot/domain_spec.yaml`.
- Spec includes: domain name, entities, relationships, aliases, units, important columns, traversal hints, confidence, review warnings.
- Test: run `dataroot infer-domain-spec` on water_quality, verify plausible spec created.
- **Human reviews and accepts spec before proceeding.**

## Hour 14–18: Apply Domain Spec

- Add `dataroot apply-domain-spec`.
- Role B enriches KB docs using domain spec: tags, aliases, labels, wikilinks.
- Test: run `dataroot apply-domain-spec`, verify docs enriched without raw-file edits.

## Hour 18–22: Generic query agent

- Implement tools: kb_search, kb_show, kb_graph, find_candidate_paths, query_table, log_inquiry.
- Role C system prompt reads domain spec first.
- CLI: `dataroot ask "..."` runs the full loop, prints streaming answer + provenance.
- Test: `dataroot ask "Which stations exceeded nitrate limits in 2024?"` — verify stations, citations, provenance JSON.

## Hour 22–26: Demo data

- Polish the lab/research demo pack (CompanyA_AgriTrait, CompanyB_Fermentation).
- Add water_quality OpenData smoke-test dataset.
- Run demo spine invariant check (A-CUL-TOM-014 chain).
- Test both demos through the full pipeline.

## Hour 26–28: Tier 2 (only after Tier 1 passes)

- Web UI with chat, answer pane, and provenance display.
- Demo-site DFD/ERD editor polish.
- Export/import polish for local diagram fixtures.

## Hour 28–30: Buffer

- Record backup video.
- Practice demo script.
- Test on actual demo laptop.
- Pre-load the Nexus demo fixtures and known-good question set.

## Cut order if behind

At any checkpoint, if more than 2 hours behind: cut from the bottom
of Tier 3, then Tier 2. Demo polish and buffer are non-negotiable —
a polished Tier 1 demo wins more often than a janky Tier 3.

**Cut order:** export polish → Tier 3 polish → Tier 2 features.
Always protect: profiler, linker, Domain Spec Generator, query agent.

← Back to [CONTEXT.md](../CONTEXT.md)
