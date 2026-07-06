# DataRoot — Steering

_Spec sheet generated 2026-06-22. Alias `data`, component-ID prefix `DATA`._
_Amended 2026-07-05: added DATA-DFM-017 (SQL DDL importer, `POST /schema/import-sql`) and PEN schema 0.2
(indexes, enum columns, table description/color) — see `overview/spec.tech.md` REQ-DATA-067…071._

## Source quality

- **Confidence: HIGH.** Grounded in gitkb code-intel (git-kb 0.2.12, indexed 2026-06-22) plus
  direct reads of source, config, README, and `.dfd.json` data assets.
- gitkb index: **1,360 symbols across 232 files** (the manifest records 231; gitkb's own stats
  print 232 — the discrepancy is gitkb counting the KB-root marker vs. tracked source files and is
  not load-bearing). Language breakdown: **python 1,078 symbols / 92 files (deep)**,
  **typescript 282 symbols / 56 files (deep)**, javascript 3 files (deep, 0 symbols), plus detected
  bash (2), css (2), dockerfile (1), html (1), json (28), markdown (38), toml (3), xml (6).
- Top directories by symbol weight: `demo-site` (648), `src` (515), `tests` (175), `scripts` (22).
- gitkb found **no inferred entrypoints and no traced flows** (both need `--refresh`); it listed
  100 "potentially dead" symbols — most are FastAPI route handlers and rule-detector functions that
  ARE reached at runtime via decorators / a dispatch table, so "dead" here means "no static caller
  edge," not genuinely unused. Treated accordingly below.

## What this repo is

DataRoot is a **two-application monorepo**, both centered on turning files into a queryable data
model. (1) `src/dataroot/` is the **DataRoot data-lineage agent** (a hackathon submission): it
ingests a folder of heterogeneous files (CSV/JSON/FASTA/Markdown) into a **GitKB-backed provenance
graph**, links records by repeated IDs and optional normalized addresses, and runs a tool-using
**Live Ask** agent (LLM + deterministic fallback) that answers questions with citations and renders
the provenance as a **Miro board**; it ships a FastAPI server, a stdio **MCP server**, a CLI, and a
Claude Code skill. (2) `demo-site/` is the **DFDMaker** web app (its own FastAPI backend + React/Vite
frontend) that ingests spreadsheets / analyzes repos, infers an **ERD**, propagates it to a **DFD**,
runs a structural **diagram-rules** engine, and exports SQL/DBML/Mermaid; its canonical project file
is the **PEN file** (`*.dfd.json`, `documentType: "dashbot.dfdmaker"`).

> Cross-repo note: the orchestrator's hint (a `dfd-maker` surfacing `dfd.business_rules[]` /
> `dfd.connectors[]` seeded by `demo-site/scripts/seed-nexus-behavior.mjs`, with DFDs under
> `frontend/public/nexus/`) does **NOT** match this repo. There is no `business_rules`/`connectors`
> field, no `demo-site/scripts/` directory, no seed script, and no `nexus/` DFD folder. The actual
> PEN schema is `project / sources / erd / dfd / layout / styles / postgres / review`
> (see `demo-site/backend/models/pen.py:345`). DFD JSONs live at `demo-site/frontend/public/*.dfd.json`
> and `demo-site/backend/demo_assets/*.dfd.json`. The "ERD/DFD parity source of truth" framing is
> directionally correct (this repo IS where ERD↔DFD models and the rule catalog live) but the field
> names and seeding mechanism cited were wrong.

## Known repo facts

### Stack
- **Python ≥3.11** (`pyproject.toml:6`) — package `dataroot` built from `src/` (setuptools).
  Runtime deps: fastapi, mcp, openai, requests, starlette, uvicorn (`pyproject.toml:7-14`);
  optional `xlsx`→openpyxl, `dev`→pytest (`pyproject.toml:16-18`).
- **demo-site backend**: separate Python FastAPI app (`demo-site/backend/requirements.txt`,
  16 deps incl. fastapi, uvicorn, sqlmodel, pydantic, bcrypt, openpyxl, requests). Not part of the
  `dataroot` package; imported by adding its own roots to `sys.path` (`demo-site/backend/main.py:24-28`).
- **demo-site frontend**: React 19 + Vite 8 + TypeScript ~6 + Tailwind 3, React Flow (`@xyflow/react`),
  elkjs layout, jsPDF/html-to-image export (`demo-site/frontend/package.json`).
- External runtime dependency: **`git-kb` CLI must be on PATH** for the dataroot KB backend
  (`src/dataroot/kb/gitkb_store.py:29`); the MCP server refuses to start without it
  (`src/dataroot/mcp/server.py:60`).

### Entrypoints
- CLI: `dataroot` console script → `dataroot.cli:main` (`pyproject.toml:21`, `src/dataroot/cli.py:18`).
  Subcommands: `init, profile, link, infer-domain-spec, apply-domain-spec, list, show, search, graph,
  ask, miro, miro-refresh-board, serve, mcp` (`src/dataroot/cli.py:22-74`).
- dataroot HTTP: `uvicorn dataroot.server.app:app` (`src/dataroot/server/app.py`); `POST /api/ask-render`.
- dataroot MCP: `python -m dataroot.mcp` → `run_stdio()` (`src/dataroot/mcp/__main__.py`, `server.py`).
- demo-site backend: `uvicorn main:app` (FastAPI `DFDMaker API`, `demo-site/backend/main.py:51`),
  default ports DATA=3282 / ROOT=7668 (`demo-site/README.md`).
- demo-site frontend: `vite` dev server (`demo-site/frontend/package.json:7`).

### Build / run / test / seed commands (verified)
- Install dataroot: `pip install .` (uses `pyproject.toml`); Docker via root `Dockerfile`
  (installs git-kb `GITKB_VERSION=0.1.55`, runs uvicorn; deploy via `railway.json`).
- dataroot tests: `pytest` (`pyproject.toml:33-35`, `pythonpath=["src"]`, `testpaths=["tests"]`);
  12 test modules under `tests/`.
- dataroot MCP verifier: `PYTHONPATH=src python scripts/verify_mcp.py` (in-process, no WSL needed).
- Austin data fetch ("seed"): `python scripts/fetch_austin.py` (Socrata downloader, stdlib only).
- CompanyC registry generator: `python scripts/gen_companyc_registries.py`.
- demo-site backend: `pip install -r demo-site/backend/requirements.txt`; run
  `python -m uvicorn main:app --port 3282` from `demo-site/backend` (`demo-site/README.md`).
- demo-site frontend: `npm run dev` / `build` (`tsc -b && vite build`) / `lint` (`eslint .`) /
  `preview` / `start` (`serve -s dist`) (`demo-site/frontend/package.json:6-12`).
- demo-site backend tests: `pytest` under `demo-site/backend/tests/` (`test_repo_analysis_phase_a.py`,
  `test_sql_import.py`, `test_pen_model_migration.py`; DDL fixtures in `tests/fixtures/ddl/`;
  `conftest.py` present).
- demo-site Austin demo builder: `python demo_data/build_austin_dfd.py <raw_ingest.json>`
  (`demo-site/demo_data/build_austin_dfd.py`).

### Notable env vars (verified in `.env.example` / code)
`OPENAI_API_KEY`, `DATAROOT_MODEL`, `DATAROOT_KB_BACKEND`, `DATAROOT_SERVER_KB_BACKEND`,
`DATAROOT_BOOTSTRAP_CODE_INDEX`, `DATAROOT_USE_MODEL_ASK`, `DATAROOT_USE_MIRO_PLANNER`,
`DATAROOT_LINK_ADDRESS_JOIN`, `GITKB_AUTHOR_NAME/EMAIL`, `MIRO_ACCESS_TOKEN`, `MIRO_BOARD_ID`
(root `.env.example`). demo-site backend adds `SECRET_KEY`, `AUTH_DISABLED`, `FRONTEND_ORIGIN`,
`COOKIE_SECURE`, `ADMIN_PASSWORD_HASH` (`demo-site/backend/main.py`).

## Unknown / needs human confirmation
- **Relationship between the two apps.** `demo-site/README.md` says DFDMaker was "copied from
  `DFDMaker/frontend` + `DFDMaker/backend`" (a sibling repo) and rebranded as the DataRoot pitch
  demo. Whether the two apps share any code at runtime, or are only co-located, is not provable from
  this repo alone — they have independent dependency manifests and import roots.
- **MiniMax / opencode usage.** `opencode.json` configures a MiniMax provider; `demo-site/backend/llm/minimax.py`
  is the chat backend. Whether MiniMax is the production LLM or a dev convenience is not stated.
- **gitkb 232-vs-231 file count** (see Source quality) — cosmetic, not verified to the file.
- The 100 "potentially dead" symbols are mostly decorator-registered routes / dispatch-table
  detectors; none were confirmed genuinely unreachable. A human should confirm any true dead code.
- demo-site `/schema/claude-eval` route notes its original eval fixture "isn't in the repo"
  (`demo-site/backend/main.py:229`); it stands in with the self-analysis demo.
