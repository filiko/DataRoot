---
purpose: Full architectural reference for DataRoot.
prerequisites: CONTEXT.md
read-when: Building core system, understanding data flow, making architectural decisions.
---

# Architecture — docs/architecture.md

Full architectural reference for DataRoot. For the compressed
master context, see [CONTEXT.md](../CONTEXT.md).

## §1 Full problem statement

Research organizations — biotech, pharma, agriculture R&D, materials labs — have data scattered across:

- Spreadsheets (cultivar registries, harvest logs, assay results)
- Sequence files (FASTA, GenBank)
- Compound databases (internal CSVs, external refs to PubChem/ChEMBL)
- Protocol PDFs and markdown lab notebooks
- Instrument exports (HPLC traces, mass spec runs)
- Field/cultivation logs
- Customer inquiry records

When someone asks "do we have anything that can do X," answering it correctly means traversing all of these and stitching together a coherent picture. Today this requires asking three different teams and waiting two weeks. The work isn't hard — it's mechanical, lookup-heavy, and exactly the kind of thing an agent should excel at.

### Why agents specifically

This isn't a RAG problem. It's a planning problem. The agent has to:

- Decompose a domain question into typed retrieval steps (compound lookup ≠ sequence search ≠ inventory check).
- Pick the right tool for each step.
- Recover when an upstream artifact is missing ("we don't have this cultivar's titer data, but we have its parent line's — substitute with confidence note").
- Produce a structured output (the lineage graph) not just text.
- Project forward when relevant ("seeds in inventory, ~9 months to first harvest").

### Why the lab/research demo

The lab/research demo is the polished story because it is intuitive, high-value, and agentic: a customer asks a product/spec question, and the answer requires traversing genetics, experiments, QC, inventory, and product documents.

But CompanyA/CompanyB are not the core architecture. They are demo domain packs produced from, or compatible with, the Domain Spec Generator.

The core DataRoot system works on any folder by first profiling the files and generating a domain spec.

## §2 Full scope and tier breakdown

### Tier 1 — Demo-able (must work)

- Generic workspace profiler for CSV, XLSX, JSON, Markdown/text, and FASTA if present.
- Generic KB document-record generation for:
  - workspace, source_file, table, column, row_group
  - candidate_entity, measurement, relationship
  - domain_spec, inquiry, provenance_trace
- KBStore adapter backed by the real GitKB CLI. Missing GitKB is a hard failure.
- Generic linker for: file→table, table→column, likely PK/FK, repeated IDs, date/time, geo, measurement, text mentions.
- Domain Spec Generator that proposes `.dataroot/domain_spec.yaml` (reviewed before proceeding).
- `apply-domain` that enriches KB docs using the accepted spec.
- Generic traversal tools: kb_search, kb_show, kb_graph, profile_workspace, infer_domain_spec, apply_domain_spec, find_candidate_paths, query_table, log_inquiry.
- CLI demo with cited answers and provenance JSON.
- Lab/research demo pack.

### Tier 2 — Differentiated

- Miro REST renderer using `MIRO_ACCESS_TOKEN`.
- Cytoscape/HTML fallback.
- Web UI.
- Better confidence scoring.

### Tier 3 — Polish

- Streaming agent output in the UI.
- "Next experiments" suggestion frame on the Miro board.
- Inquiry log auto-update.
- Multi-hop confidence scoring.

### Out of scope

- Perfect arbitrary dataset understanding.
- Production OAuth / multi-user auth.
- Live external datastore integrations.
- Mirage integration.
- Full Miro MCP integration.
- Production-grade ontology extraction.

### Demo spine invariant

The following ID chain must hold for CompanyA_AgriTrait:

```
A-CUL-TOM-014 appears in cultivar registry
A-CUL-TOM-014 has trait A-TRT-DRT (drought tolerance)
A-CUL-TOM-014 has marker A-GEN-PMR3 (powdery mildew resistance)
A-CUL-TOM-014 appears in greenhouse trials
A-CUL-TOM-014 appears in field trials
A-CUL-TOM-014 appears in seed inventory
A-CUL-TOM-014 appears in field readiness
A-CUL-TOM-022 appears and has a failure reason
```

If this chain breaks, the demo fails. Test this with a pytest invariant check before the hackathon.

## §3 Architecture details

### 3.1 Full architecture diagram

Raw Folder / ExampleData / OpenData
        ↓
DataRoot Workspace Profiler
        ↓
Generic KB Document Records
  - source_file
  - table
  - column
  - row_group
  - candidate_entity
  - measurement
  - relationship
        ↓
GitKB / KBStore
        ↓
Domain Spec Generator Agent (Role A)
        ↓
Reviewable .dataroot/domain_spec.yaml
        ↓
Apply Domain Spec (Role B)
        ↓
Enriched KB Graph
        ↓
Query Agent (Role C)
        ↓
Cited Answer + Provenance JSON + Inquiry Log
        ↓
Optional Miro Board (Tier 2)

### 3.2 Why GitKB as the substrate

GitKB gives us:

- Document model: Markdown + YAML frontmatter, typed (task, spec, incident, note, context, plus custom types like cultivar, gene, compound, harvest, protocol, inquiry).
- Wikilinks: [[cultivars/tbf-lime-04]] becomes a real graph edge GitKB tracks.
- FTS5 search via kb_search.
- Semantic search via kb_semantic (alpha, optional).
- Graph traversal via kb_graph with directional and depth controls.
- MCP server/tools — DataRoot calls them through GitKBStore rather than re-implementing document search/write/traversal.
- Workspace checkout/commit semantics.
- Backup/export as KB invariants.

What GitKB does NOT do (DataRoot must add):

- Native parsing of .xlsx, .fasta, .csv into structured facts. DataRoot still extracts normalized document records from raw scientific files before handing them to GitKB.
- Domain-specific edge inference (e.g., "this column in harvests.csv is a foreign key into cultivars.xlsx").
- Miro rendering.
- Domain ontology.

Implication: every time you'd reach for a generic indexing/search/graph primitive, ask "does GitKB already do this?" first. Almost always yes.

### 3.2.1 KBStore backend

**GitKBStore** implements `read/search/write/update/commit` by calling the
real `git kb` CLI. There is no application fallback to a local mock store:
if GitKB is missing, DataRoot exits with an installation error. This is
intentional because the product must validate against GitKB's document,
search, commit, and graph behavior.

`LocalMarkdownStore` is retained only as a narrow unit-test helper for parser
and deterministic-query tests.

### 3.3 Full data model

Two layers:

**Layer 1 — Source artifacts** (raw files in /ExampleData/, never modified by the agent):

- cultivars.xlsx — plant lines with IDs, lineage, traits
- compounds.csv — compound definitions, properties, flavor descriptors
- terpene_synthases.fasta — gene sequences with structured headers
- field_plantings_2025.csv — what's planted where, when
- harvest_logs/*.csv — historical yields and titers
- protocols/*.md — experimental protocols with referenced cultivar/gene IDs
- inquiries/*.json — customer inquiries (input)

**Layer 2 — KB documents** (in .kb/, created by profiling + linking + agent):

Generic types: workspace, source_file, table, column, row_group, candidate_entity, measurement, relationship, domain_spec, inquiry, provenance_trace.

Domain-specific types (after apply-domain): cultivar, gene, compound, harvest, planting, protocol, strain, ferm_run, assay.

The key insight: we use GitKB's document model as our domain knowledge graph. Source files stay as files; KB documents are the structured, linked, searchable layer the agent operates on.

### 3.4 Full dataroot CLI

```
dataroot init                          # scaffold .dataroot/, init KBStore
dataroot profile <path>                # profile workspace, persist generic records via KBStore
dataroot infer-domain-spec             # run Role A, write .dataroot/domain_spec.yaml
dataroot apply-domain-spec            # run Role B, enrich KB docs using spec
dataroot link                          # generic linker: FK, PK, ID, date, geo, measurement
dataroot ask "<question>"              # run Role C, stream answer + provenance
dataroot serve                         # start FastAPI + Next.js UI (Tier 2)
dataroot miro <provenance_slug>         # render provenance to Miro board (Tier 2)
```

For the hackathon, miro is Tier 2, not Tier 1.

### 3.5 Full project layout

```
dataroot/
├── CONTEXT.md                  # compressed master (this file's parent)
├── docs/                       # topic-specific depth files
│   ├── architecture.md         # this file
│   ├── agent-runtime.md         # roles, runner, tool_sets, prompts
│   ├── ingestion.md             # parsers, document emission
│   ├── linking.md               # FK inference, wikilink rules
│   ├── miro-renderer.md         # Miro REST, layout, fallback
│   ├── synthetic-dataset.md     # demo data specs
│   ├── build-plan.md           # hour-by-hour plan
│   └── glossary.md             # key terms
├── README.md
├── pyproject.toml              # uv-managed
├── .env.example
│   # Required for AI calls
│   OPENAI_API_KEY=your_openai_api_key_here
│   # Optional Tier 2 Miro rendering
│   MIRO_ACCESS_TOKEN=your_miro_oauth_access_token_here
│   MIRO_BOARD_ID=optional_existing_board_id
│   # KB backend
│   DATAROOT_KB_BACKEND=gitkb
│   # no local backend fallback; GitKB is required
│   # Model
│   DATAROOT_MODEL=gpt-4o
├── .kb/                        # created by GitKB, not committed
├── .dataroot/
│   └── config.toml
├── src/dataroot/
│   ├── __init__.py
│   ├── cli.py                  # typer entrypoint
│   ├── kb/
│   │   ├── base.py             # KBStore abstract base
│   │   ├── gitkb_store.py      # GitKBStore implementation
│   │   └── local_store.py     # LocalMarkdownStore implementation
│   ├── profile/
│   │   ├── walker.py           # directory traversal
│   │   ├── parsers/
│   │   │   ├── csv.py
│   │   │   ├── xlsx.py
│   │   │   ├── json.py
│   │   │   ├── fasta.py
│   │   │   └── markdown.py
│   │   └── doc_emitter.py      # converts profile output into KBStore.write calls
│   ├── link/
│   │   ├── fk_inference.py    # column-name FK detection
│   │   ├── id_extraction.py   # regex-based ID refs in text
│   │   └── linker.py          # adds [[wikilinks]] to KB docs
│   ├── agent/
│   │   ├── codex_client.py    # single Codex API wrapper
│   │   ├── runner.py          # single tool-calling loop
│   │   ├── tool_sets.py       # role → list of tool schemas
│   │   └── prompts/
│   │       ├── domain_spec_generator.md   # Role A
│   │       ├── domain_spec_applier.md     # Role B
│   │       └── query_agent.md             # Role C
│   ├── render/
│   │   ├── miro.py            # Miro REST renderer
│   │   └── cytoscape.py       # HTML fallback
│   └── server/
│       ├── app.py             # FastAPI
│       └── routes.py
├── ExampleData/
│   ├── water_quality/         # smoke-test dataset
│   ├── CompanyA_AgriTrait/
│   │   ├── cultivars.xlsx
│   │   ├── compounds.csv
│   │   ├── terpene_synthases.fasta
│   │   ├── field_plantings_2025.csv
│   │   ├── harvest_logs/
│   │   ├── protocols/
│   │   └── inquiries/
│   └── CompanyB_Fermentation/
│       ├── ...
└── tests/
    ├── test_parsers.py
    ├── test_linker.py
    ├── test_demo_spine.py     # invariant check for ID chain
    └── test_demo_e2e.py
```

← Back to [CONTEXT.md](../CONTEXT.md)
