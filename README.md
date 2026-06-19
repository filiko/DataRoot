# DataRoot

DataRoot is now centered on a Nexus Agriscience ERD/DFD demo application backed
by DFDMaker's diagram model, editor, rules engine, and exporters.

The repository still includes the original DataRoot profiling and Ask pipeline:
it ingests CSV, JSON, FASTA, Markdown, and XLSX files into a searchable KB,
links records by repeated IDs and optional address keys, and answers questions
with cited provenance. That pipeline now returns in-app JSON/provenance results
instead of rendering to an external board service.

## Main App

The active application lives in `demo-site/`.

- Full Nexus Ag example set: `demo-site/frontend/public/nexus/00_nexus_master.dfd.json`
  through `11_finance_ai.dfd.json`.
- DFD/ERD editor, auto-layout, validation rules, warnings, Level 1 DFD support,
  repo-analysis import, and SQL/Mermaid/DBML exports from DFDMaker.
- Behavioral overlay fields used by the Nexus examples:
  `Entity.domain`, `Entity.connects`, `dfd.business_rules`, and
  `dfd.connectors`.
- Business Rules and Connectors tabs for lifecycle gates, invariants,
  cross-service seams, fan-outs, and shared middleware.

Run it locally:

```bash
cd demo-site/backend
AUTH_DISABLED=1 SECRET_KEY=demo-secret python -m uvicorn main:app --host 127.0.0.1 --port 3282

cd ../frontend
npm install
npm run dev
# http://localhost:7668
```

Open `/nexusag` to load the Nexus master map and module carousel.

## DataRoot Ask Pipeline

The core Python package remains available for file profiling, graph linking,
domain-spec work, and cited answers.

```bash
dataroot init
dataroot profile ExampleData/AustinPermits/raw
dataroot link
dataroot ask "Which permit records share an address with code complaints?"
```

The FastAPI Ask API is non-board-based:

```bash
uvicorn dataroot.server.app:app --host 127.0.0.1 --port 8000
# POST /api/ask with {"company":"austin_permits","question":"..."}
```

The stdio MCP server exposes eight bounded tools:

```bash
dataroot mcp
PYTHONPATH=src python scripts/verify_mcp.py
```

Tool names: `list_datasets`, `summarize_workspace`, `kb_search`, `kb_list`,
`kb_show`, `query_table`, `kb_graph`, and `ask`.

## Project Layout

```text
demo-site/
  backend/      DFDMaker-derived FastAPI backend and diagram rule engine
  frontend/     Nexus-first React/Vite ERD/DFD editor

src/dataroot/
  agent/        tool-calling roles and prompts
  kb/           GitKB and local markdown stores
  link/         deterministic ID/address linker
  mcp/          stdio MCP server
  profile/      workspace profilers
  render/       non-board provenance interpretation helpers
  server/       non-board Ask API
  cli.py        profile, link, ask, mcp, serve

ExampleData/
  AustinPermits/
  CompanyA_AgriTrait/
  CompanyB_Fermentation/
```

## Environment

| Variable | Effect |
| --- | --- |
| `DATAROOT_LINK_ADDRESS_JOIN=1` | Enables address-keyed cross-table relationships. |
| `DATAROOT_SERVER_KB_BACKEND=gitkb` | Forces the FastAPI Ask API to use GitKB. |
| `OPENAI_API_KEY` or `MINIMAX_API_KEY` | Enables optional LLM-backed Ask behavior. |
| `AUTH_DISABLED=1` | Enables demo-site local no-login mode. |
| `SECRET_KEY` | Required for stable demo-site sessions. |

## Attribution

Austin permit demo data is City of Austin / Austin Development Services public
data under the City of Austin Open Data Terms. The biotech workspaces and Nexus
Agriscience examples are synthetic.
