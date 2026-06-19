---
purpose: Current working checklist for finishing DataRoot.
prerequisites: CONTEXT.md, docs/build-plan.md, docs/architecture.md
read-when: Picking the next implementation task or checking demo readiness.
---

# Working Task List

This file is the active execution checklist distilled from the plan files in
`docs/`. It reflects the current repo state after the first Tier 1 foundation
passes.

## Current Baseline

Completed and verified locally:

- Python package scaffold with `pyproject.toml`, CLI entrypoint, README, env example, and `.gitignore`.
- KBStore adapter boundary:
  - `GitKBStore` shells out to the real `git kb` CLI.
  - `LocalMarkdownStore` is retained only for narrow unit tests, not application fallback.
  - Persistence-facing code uses `read/search/write/update/commit` style methods.
- Generic profiler:
  - CSV, JSON, FASTA, Markdown/text, unknown-file fallback.
  - XLSX support if `openpyxl` is installed.
  - Emits `workspace`, `source_file`, `table`, `column`, `row_group`, `measurement`, and `candidate_entity` records.
- Generic linker:
  - Structural file/table/column/row links.
  - Repeated-ID relationship docs.
  - Candidate FK links from column overlap/name matches.
  - ID extraction fixed for values like `A-FLD-BLOCK-3`.
- Domain spec fallback:
  - `dataroot infer-domain-spec`
  - `dataroot apply-domain-spec`
  - generated and accepted specs are stored as `domain_spec` KB docs.
- Query fallback:
  - `kb_search`, `kb_show`, `kb_list`, `kb_graph`, `query_table`, `find_candidate_paths`, `log_inquiry` dispatcher.
  - Threshold questions work for water quality.
  - ID-centered questions prioritize row-level evidence.
  - `dataroot ask` persists `inquiry` and `provenance_trace` docs.
- Example data:
  - CompanyA and CompanyB demo packs.
  - Water-quality smoke dataset.
- Tests:
  - KB store search/graph.
  - Profile/link repeated IDs.
  - CompanyA demo spine invariant.
  - Water-quality nitrate exceedance invariant.
  - Query tool threshold behavior.
  - Full water-quality CLI e2e smoke path.
  - CompanyA readiness synthesis.
  - CompanyB fermentation scale-up synthesis.

Verification commands that currently pass:

```powershell
$env:PYTHONPATH='src'; python -m compileall src
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

## Immediate Next Tasks

These are the highest-priority tasks before adding polish.

- [x] Install and validate real GitKB locally under WSL.
  - Run `git kb --help`.
  - Run `dataroot init`.
  - Confirm DataRoot uses `GitKBStore` and fails if GitKB is unavailable.
  - Re-run profile/link/search against water_quality and CompanyA.

- [x] Verify `GitKBStore` command shapes against the installed GitKB CLI.
  - `git kb init`
  - `git kb create ...`
  - `git kb update ...`
  - `git kb show ...`
  - `git kb list ...`
  - `git kb search ...`
  - `git kb graph ...`
  - `git kb commit ...`
  - Patch adapter names/flags to match the real CLI.

- [x] Add an end-to-end CLI smoke test.
  - Fresh temp workspace.
  - `init`
  - `profile ExampleData/water_quality/raw`
  - `link`
  - `infer-domain-spec`
  - `apply-domain-spec`
  - `ask "Which stations exceeded nitrate limits in 2024?"`
  - Assert `STATION_001`, `STATION_002`, citations, and `<provenance>`.

- [x] Improve `ask` output for CompanyA.
  - Target question:
    `Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?`
  - Expected answer should cite:
    - cultivar registry
    - trait/marker evidence
    - greenhouse trials
    - field trials
    - seed inventory/QC
    - field readiness / planting window
  - Current fallback finds evidence but does not yet synthesize the full narrative.

- [x] Improve `ask` output for CompanyB.
  - Target question:
    `Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?`
  - Expected answer should cite:
    - strain registry
    - pathway genes
    - metabolite catalog
    - GC-MS assays
    - fermentation run
    - QC release status
    - strain inventory
    - bioreactor schedule

## Tier 1 Remaining

### Ingestion

- [x] Add true `measurement` docs, not only measurement metadata on columns.
- [x] Add `provenance_trace` docs when answers are produced.
- [x] Add richer Markdown parsing:
  - frontmatter preservation
  - markdown tables
  - wikilink extraction as first-class records
- [x] Improve JSON nested-object handling:
  - candidate entities from nested IDs
  - measurement docs from numeric leaves
- [x] Add row grouping strategy for large files.
  - Current implementation creates one row doc per detected key row.
  - Need a cap/chunking strategy for bigger datasets.

### Linking

- [ ] Add explicit confidence metadata to inferred links.
- [ ] Separate relationship types:
  - `contains_table`
  - `has_column`
  - `has_row`
  - `repeated_id`
  - `candidate_fk`
  - `temporal_cooccurrence`
  - `geo_match`
  - `measurement_of`
- [ ] Improve FK inference beyond sample values.
  - Compare full row-group values where practical.
  - Normalize case, whitespace, punctuation.
- [ ] Add temporal/date relationship docs.
- [ ] Add geo/location relationship docs.
- [ ] Add tests for FK confidence thresholds.

### Domain Spec

- [ ] Decide final Role A path:
  - model-driven by default with deterministic fallback, or
  - deterministic first with model review.
- [ ] Wire `dataroot infer-domain-spec` to the actual `Runner` when `OPENAI_API_KEY` is present.
- [ ] Validate Role A output schema before writing `.dataroot/domain_spec.yaml`.
- [ ] Add human-review guardrail:
  - do not run `apply-domain-spec` unless spec exists and is accepted.
- [x] Store accepted domain spec in KB as a `domain_spec` doc.

### Apply Domain Spec

- [ ] Wire Role B to `Runner` for fuzzy matches.
- [ ] Preserve deterministic enrichments for low-risk mappings.
- [ ] Add domain-specific aliases to row/table docs, not just columns.
- [ ] Add domain labels/tags consistently across tables, columns, row groups, and relationships.
- [ ] Add tests that raw source files are never modified.

### Query Agent

- [ ] Wire `dataroot ask` to Role C/Runner when API key is present.
- [ ] Keep deterministic fallback for offline/demo safety.
- [x] Add basic provenance edges for synthesized answers.
- [x] Add `log_inquiry`-style persistence for each CLI answer.
- [x] Add `provenance_trace` doc creation.
- [ ] Implement domain-specific helper tools from `agent-runtime.md`:
  - `resolve_compound`
  - `find_cultivars_producing`
  - `check_inventory`
  - `project_timeline`
- [ ] Add missing-data behavior:
  - explicitly report gaps
  - cite substitute evidence
  - avoid unsupported claims

### Tests

- [ ] Add `tests/test_demo_e2e.py`.
- [x] Add full water-quality e2e test.
- [x] Add CompanyA answer synthesis regression test.
- [x] Add CompanyB answer synthesis regression test.
- [ ] Add GitKB adapter integration test gated on `git kb` availability.
- [ ] Add regression test for generated provenance shape.

## Tier 2 Remaining

Only start these after Tier 1 e2e is stable.

### Diagram App

- [ ] Keep the Nexus DFD/ERD fixture suite loadable from the demo site.
- [ ] Preserve DFD business rules and connectors during import, save, and rules-gate updates.
- [ ] Keep JSON export/import round-tripping the Nexus metadata.

### Server / UI

- [ ] Add FastAPI skeleton and healthcheck.
- [ ] Add endpoint for:
  - profile
  - link
  - ask
  - provenance retrieval
  - render
- [ ] Decide whether a web UI is worth the remaining time.
- [ ] If yes, keep it minimal:
  - one workspace selector
  - one question input
  - answer pane
  - provenance JSON/render link

## Demo Prep

- [ ] Re-run full pipeline on water_quality from a clean `.dataroot`.
- [ ] Re-run full pipeline on CompanyA from a clean `.dataroot`.
- [ ] Re-run full pipeline on CompanyB from a clean `.dataroot`.
- [ ] Save known-good command transcript.
- [ ] Save known-good answers for:
  - water-quality nitrate exceedance
  - CompanyA spring planting readiness
  - CompanyB fermentation scale-up
- [ ] Record backup video.
- [ ] Test on demo laptop and demo network.
- [ ] Pre-load the Nexus demo fixtures and known-good question set.

## Known Local Caveats

- Native Windows GitKB artifacts are not published in the current release;
  real validation on this machine runs through WSL.
- `.dataroot/kb_docs/` is legacy generated output from the old local fallback.
- `.dataroot/domain_spec.yaml` may be generated during smoke runs; review before
  committing it.
- Current `ask` fallback has deterministic synthesis for water_quality,
  CompanyA, and CompanyB, but model-driven Role C is still pending.

## Cut Order

If time gets tight, cut in this order:

1. Export polish
2. Diagram visual polish
3. Model-driven fuzzy Role B
4. Advanced confidence scoring

Do not cut:

- Generic profiler
- KBStore adapter boundary
- Linker
- Query tools
- Water-quality smoke test
- CompanyA/CompanyB demo spine tests
- Cited answer + provenance JSON
