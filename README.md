# DataRoot

> Turn a folder of heterogeneous files into a searchable provenance graph,
> then ask any question and get the answer rendered as a Miro board.

DataRoot ingests CSV / JSON / FASTA / Markdown into a GitKB-backed knowledge
graph, links it by repeated IDs and (optionally) by normalized addresses,
and exposes the result through a Live Ask agent that produces cited
answers and Miro provenance boards.

This repository is a single hackathon submission targeting **two tracks** at
once:

- **[Agents Track](#track-2-agents-track)** — DataRoot's Live Ask is an
  autonomous, tool-using agent (LLM + nine tools + three scoped roles +
  deterministic fallback) that takes a question, plans a multi-hop graph
  traversal, and writes its answer + provenance into Miro.
- **[Brainforge / Vicinity Texas Open Data Track](#track-1-texas-open-data)** —
  the same pipeline runs against four public City of Austin datasets, with
  a stdio MCP server (`src/dataroot/mcp/server.py`) and a Claude Code
  skill (`skills/dataroot-texas/SKILL.md`) that satisfy both technical
  artifact options the track asks for.

For a one-page judge pitch, read [`SUBMISSION.md`](SUBMISSION.md).

## 30-second demo paths

Pick whichever track you're judging. Both require `git-kb` on `PATH`
(install via WSL on Windows; see [GitKB releases](https://github.com/gitkb/gitkb-releases)).

**Texas Open Data — Austin Permits Live Ask.**

```bash
git kb --version
python scripts/fetch_austin.py
export DATAROOT_LINK_ADDRESS_JOIN=1
dataroot profile ExampleData/AustinPermits/raw
dataroot link
uvicorn dataroot.server.app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/miro/, pick "Austin Permits Explorer", ask anything
```

**Agents Track — biotech Live Ask.**

```bash
git kb --version
dataroot profile ExampleData/CompanyA_AgriTrait/raw
dataroot link
dataroot ask "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"
# the agent runs the loop end-to-end and emits a cited answer + provenance
```

## Architecture

```
folder of files                               LLM-driven Query Agent
       ↓                                            ↓
profile_workspace            ToolExecutor (kb_search, kb_graph, query_table,
       ↓                       find_candidate_paths, kb_show, kb_list, ...)
KB records (GitKB)                                  ↓
       ↓                                     answer_question
link_workspace                                      ↓
   ↓     ↓                              provenance trace (nodes, edges)
   ID   address_key                              ↓                    ↓
   joins   joins                       interpret_data_tidbits   miro_plan
                                                ↓                    ↓
                                          claim cards  →  render_provenance_to_miro
                                                                     ↓
                                                              Miro board URL
```

The same pipeline is reachable two ways:

- **HTTP** — `POST /api/ask-render` (FastAPI app in `src/dataroot/server/app.py`)
- **MCP** — `ask_and_render` tool (stdio server in `src/dataroot/mcp/server.py`)

---

## Track 1 — Texas Open Data

### Datasets

Four bounded Socrata slices from `data.austintexas.gov`, all City of
Austin / Austin Development Services public data, used under the
[City of Austin Open Data Terms](https://data.austintexas.gov/stories/s/ranj-cccq).
Per-dataset URLs, fetch parameters, attribution, and SoQL filters are in
[`ExampleData/AustinPermits/SOURCES.md`](ExampleData/AustinPermits/SOURCES.md).

| Slug          | Title                         |
|---------------|-------------------------------|
| `3syk-w9eu`   | Issued Construction Permits   |
| `n8ck-xkda`   | Plan Review Cases             |
| `6wtj-zbtb`   | Austin Code Complaint Cases   |
| `ttd7-isgm`   | Austin Code Task List         |

`scripts/fetch_austin.py` pulls bounded slices via the Socrata API and
applies the column renames the linker expects (`permit_number` →
`permit_id`, `foldernumber` → `case_task_id`).

### MCP server

The track's MCP requirement is satisfied by `src/dataroot/mcp/server.py`,
a stdio MCP server that wraps the existing `ToolExecutor` with eight
bounded tools (`list_datasets`, `summarize_workspace`, `kb_search`,
`kb_list`, `kb_show`, `query_table`, `kb_graph`, `ask_and_render`).
Hard caps: 50 hits / 100 records / 200 rows / depth 3.

```bash
dataroot mcp                       # via the CLI
python -m dataroot.mcp             # equivalent
bash scripts/start-mcp.sh          # WSL launcher (used by Codex / Claude Code)
```

The server fails loudly if `git-kb` is not on `PATH`; there is no
LocalMarkdownStore fallback. The bundled `scripts/start-mcp.sh` activates
the WSL virtualenv, sources `.env`, exports `DATAROOT_LINK_ADDRESS_JOIN=1`,
and execs `python -m dataroot.mcp` — keep stdout silent so the JSON-RPC
handshake isn't corrupted. Full per-tool API reference, schemas, and
examples are in [`docs/mcp-server.md`](docs/mcp-server.md).

A bundled verifier lets you confirm the server is healthy without wiring
up a stdio client:

```bash
PYTHONPATH=src python scripts/verify_mcp.py
```

The script runs eight in-process JSON-RPC checks (tool descriptors,
`list_datasets`, error path, `summarize_workspace`, cap clamping, git-kb
gate) and prints a pass/fail matrix. Works on Windows without WSL.

### Claude Code skill

The matching agent skill lives at
[`skills/dataroot-texas/SKILL.md`](skills/dataroot-texas/SKILL.md). Copy
that directory under `~/.claude/skills/` to make Claude Code aware of it.
It documents safe-use rules (bounded queries, no PII, attribution
required) and the question shapes the workspace handles well — without
hardcoding canned answers.

### Run the Austin Live Ask

See the [30-second demo paths](#30-second-demo-paths) above, plus the
deeper walkthrough in
[`ExampleData/AustinPermits/README.md`](ExampleData/AustinPermits/README.md).

---

## Track 2 — Agents Track

### Agent loop

DataRoot's autonomous behavior lives in `src/dataroot/agent/`:

- `runner.py` — the single tool-calling loop, harness-agnostic.
- `tools.py` — `ToolExecutor` that dispatches every tool call.
- `tool_sets.py` — per-role tool allowlists (Role A / B / C have
  different scopes).
- `prompts/*.md` — hand-authored system prompts, one file per role.

Three roles share the runner:

| Role                       | When                                  | What it does                                                 |
|----------------------------|---------------------------------------|--------------------------------------------------------------|
| **A — Domain Spec Generator** | Once per workspace, after profile     | Reads the generic KB and proposes `.dataroot/domain_spec.yaml` |
| **B — Domain Spec Applier**   | Once, after the human accepts the spec | Walks KB docs and enriches them with tags / wikilinks         |
| **C — Query Agent**           | Every Live Ask                         | Plans a multi-hop traversal, cites evidence, emits provenance  |

Full reference (loop semantics, tool inventory, prompts, failure modes):
[`docs/agent-runtime.md`](docs/agent-runtime.md).

### Why this is more than a chatbot

- **Plans across multi-hop graphs.** Tool order is decided by the model,
  not hardcoded.
- **Two real-world effects.** Every turn writes `inquiries/<timestamp>`
  and a provenance trace into GitKB, then calls the Miro REST API to
  render the trace as a board.
- **Recovers from missing data.** Prompts force an explicit "lineage gap"
  admission rather than fabrication; the deterministic fallback in
  `src/dataroot/query.py` takes over so the user always gets a cited
  answer.
- **Scoped autonomy.** Tool allowlists in `tool_sets.py` enforce role
  boundaries — Role A and B can write to specific KB paths; Role C is
  read-only and append-only.
- **Graceful degradation.** Every LLM-driven layer (interpreter, planner,
  query) has a deterministic fallback that runs without `OPENAI_API_KEY`.

### Biotech demo workspaces (`company_a` / `company_b`)

The Agents Track demos use two synthetic research workspaces that
exercise the same pipeline as the Austin slice:

- **CropProtectorAI** (`ExampleData/CompanyA_AgriTrait/`) — tomato
  cultivars × markers × greenhouse trials × seed inventory.
- **BioReactorAI** (`ExampleData/CompanyB_Fermentation/`) — yeast
  strains × pathway genes × fermentation runs × GC-MS assays.

Each one ships an `expected_answers/` and `provenance_targets/` folder
so the agent's output can be diffed against ground truth during
development.

```bash
dataroot profile ExampleData/CompanyB_Fermentation/raw
dataroot link
dataroot ask "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation?"
```

---

## Project layout

```
src/dataroot/
├── agent/        # the autonomous loop, three roles, prompts, tool schemas
├── kb/           # KBStore protocol + GitKB and LocalMarkdownStore adapters
├── link/         # deterministic linker + address normalizer
├── mcp/          # stdio MCP server (Track 1 artifact)
├── profile/      # workspace profiler (CSV/JSON/FASTA/MD parsers)
├── render/       # Miro renderer + interpretation + planner
├── server/       # FastAPI Live Ask app
├── cli.py        # top-level CLI (profile, link, ask, mcp, serve, ...)
└── query.py      # answer_question + provenance trace extraction

ExampleData/
├── AustinPermits/      # Texas Open Data workspace (Track 1)
├── CompanyA_AgriTrait/ # Biotech demo A (Track 2)
└── CompanyB_Fermentation/

docs/
├── mcp-server.md           # MCP API reference
├── agent-runtime.md        # Agents Track runtime reference
├── deploy.md               # Railway / Miro Developer app setup
├── architecture.md         # Whole-system architecture
├── ingestion.md / linking.md / miro-renderer.md  # Layer references
└── miro-fundamental-functionality.md             # Renderer behavior contract

skills/dataroot-texas/SKILL.md   # Claude Code skill (Track 1 artifact)
scripts/fetch_austin.py          # Socrata downloader for the four Austin slices
```

## Quick reference

```bash
# core pipeline
dataroot init                                  # scaffold .dataroot/ and .kb
dataroot profile <path>                        # ingest a folder
dataroot link                                  # detect repeated IDs (and addresses if DATAROOT_LINK_ADDRESS_JOIN=1)
dataroot infer-domain-spec                     # Role A
dataroot apply-domain-spec                     # Role B
dataroot ask "<question>"                      # Role C — the Live Ask agent

# search and traversal
dataroot search <query>                        # full-text search
dataroot list --type table                     # filtered list
dataroot show <slug>                           # full record
dataroot graph <slug> --depth 1                # connected subgraph

# servers
dataroot serve                                 # FastAPI Miro panel
dataroot mcp                                   # stdio MCP server
python -m dataroot.mcp                         # equivalent
```

Notable env vars (full table in [`docs/deploy.md`](docs/deploy.md)):

| Variable                            | Effect                                                |
|-------------------------------------|-------------------------------------------------------|
| `OPENAI_API_KEY`                    | Enables LLM interpreter and Miro planner              |
| `MIRO_ACCESS_TOKEN`                 | Required for `ask_and_render` and Miro panel          |
| `DATAROOT_LINK_ADDRESS_JOIN=1`      | Emits address-keyed cross-table relationships         |
| `DATAROOT_SERVER_KB_BACKEND=gitkb`  | Forces real GitKB on the FastAPI app                  |
| `DATAROOT_USE_TIDBIT_INTERPRETER=0` | Forces deterministic interpreter                       |
| `DATAROOT_USE_MIRO_PLANNER=0`       | Forces deterministic Miro planner                      |

## Attribution

The Texas Open Data Track datasets are City of Austin / Austin Development
Services public data, used under the
[City of Austin Open Data Terms](https://data.austintexas.gov/stories/s/ranj-cccq).
Per-dataset slugs, URLs, fetch dates, SoQL filters, and renames are
recorded in
[`ExampleData/AustinPermits/SOURCES.md`](ExampleData/AustinPermits/SOURCES.md).

The biotech demo data in `ExampleData/CompanyA_AgriTrait/` and
`ExampleData/CompanyB_Fermentation/` is fully synthetic.

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
