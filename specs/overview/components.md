# DataRoot — Component Registry

**Component count: 56.** This registry is the parity backbone: `spec.tech.md` and `spec.sme.md`
cover these exact 56 IDs in this exact order. Areas reflect the repo's real structure:
`CORE` = the DataRoot Python lineage agent (`src/dataroot/`), `DFM` = the DFDMaker demo-site backend
(`demo-site/backend/`), `WEB` = the demo-site React/Vite frontend (`demo-site/frontend/`),
`DATA` = data assets, `OPS` = tooling/build/tests.

Status legend: `implemented` / `partial` / `stub` / `dead` / `data-asset`.

| ID | Component | Primary anchor | Status |
|----|-----------|----------------|--------|
| DATA-CORE-001 | DataRoot CLI (`dataroot` console script, 14 subcommands) | `src/dataroot/cli.py:18` | implemented |
| DATA-CORE-002 | Config & env loader (backend selection, `.env`/`config.toml`) | `src/dataroot/config.py:31` | implemented |
| DATA-CORE-003 | KBStore protocol & document model | `src/dataroot/kb/base.py:11` | implemented |
| DATA-CORE-004 | GitKB store adapter (shells to `git kb`) | `src/dataroot/kb/gitkb_store.py:22` | implemented |
| DATA-CORE-005 | Local markdown store + markdown (de)serialization | `src/dataroot/kb/local_store.py:14` | implemented |
| DATA-CORE-006 | Workspace profiler (CSV/JSON/FASTA/MD → KB records) | `src/dataroot/profile/workspace.py:24` | implemented |
| DATA-CORE-007 | Deterministic linker (repeated-ID + column overlap) | `src/dataroot/link/linker.py:26` | implemented |
| DATA-CORE-008 | Address-key normalizer (optional address join) | `src/dataroot/link/address_match.py:77` | implemented |
| DATA-CORE-009 | Domain-spec infer/apply (agent Roles A & B) | `src/dataroot/domain.py:29` | implemented |
| DATA-CORE-010 | Agent runner (single tool-calling loop) | `src/dataroot/agent/runner.py:22` | implemented |
| DATA-CORE-011 | ToolExecutor (9-tool dispatcher) | `src/dataroot/agent/tools.py:14` | implemented |
| DATA-CORE-012 | Per-role tool allowlists & schemas | `src/dataroot/agent/tool_sets.py:12` | implemented |
| DATA-CORE-013 | LLM client (Codex/OpenAI) for the agent | `src/dataroot/agent/codex_client.py:30` | implemented |
| DATA-CORE-014 | Deterministic query fallback (`answer_question`) | `src/dataroot/query.py:15` | implemented |
| DATA-CORE-015 | Query tools (table filtering, candidate paths) | `src/dataroot/query_tools.py:20` | implemented |
| DATA-CORE-016 | Tidbit interpreter (claims, proof rows) | `src/dataroot/render/interpretation.py:12` | implemented |
| DATA-CORE-017 | Miro board planner | `src/dataroot/render/miro_plan.py:61` | implemented |
| DATA-CORE-018 | Miro REST renderer | `src/dataroot/render/miro.py:1` | implemented |
| DATA-CORE-019 | Miro board refresh / replace tool | `src/dataroot/render/miro_refresh.py:137` | implemented |
| DATA-CORE-020 | FastAPI Live Ask server (`/api/ask-render`, workspaces) | `src/dataroot/server/app.py:94` | implemented |
| DATA-CORE-021 | GitKB runtime bootstrap (server) | `src/dataroot/server/bootstrap.py:16` | implemented |
| DATA-CORE-022 | stdio MCP server (8 bounded tools, hard caps) | `src/dataroot/mcp/server.py:1` | implemented |
| DATA-DFM-001 | PenFile model (ERD/DFD/layout/review schema) | `demo-site/backend/models/pen.py:345` | implemented |
| DATA-DFM-002 | Source-table model (deterministic parser output) | `demo-site/backend/models/source.py:26` | implemented |
| DATA-DFM-003 | DB models (User/Project/Member/Invite/Waitlist) | `demo-site/backend/models/db_models.py:21` | implemented |
| DATA-DFM-004 | File parsers (CSV/Excel) + column profiler | `demo-site/backend/parsers/profiler.py:181` | implemented |
| DATA-DFM-005 | PEN builder (tables → PenFile, apply-proposal) | `demo-site/backend/generators/pen_builder.py:170` | implemented |
| DATA-DFM-006 | Normalization proposal detectors | `demo-site/backend/generators/proposals.py:402` | implemented |
| DATA-DFM-007 | ERD→DFD sync engine (validate + propagate) | `demo-site/backend/generators/sync_engine.py:52` | implemented |
| DATA-DFM-008 | DFD builder (ERD→DFD construction) | `demo-site/backend/generators/dfd_builder.py:143` | implemented |
| DATA-DFM-009 | Diagram-rules engine (ERD/DFD rule catalog + gate) | `demo-site/backend/generators/diagram_rules.py:567` | implemented |
| DATA-DFM-010 | SQL/DBML/Mermaid exporters | `demo-site/backend/generators/sql.py:103` | implemented |
| DATA-DFM-011 | Typed-ops service (assistant-safe edits) | `demo-site/backend/services/ops_service.py:163` | implemented |
| DATA-DFM-012 | Project persistence (DB store + FS service) | `demo-site/backend/services/project_store.py:20` | implemented |
| DATA-DFM-013 | Repo-analysis pipeline (code → ERD/DFD) | `demo-site/backend/repo_cli.py:82` | implemented |
| DATA-DFM-014 | Auth, sessions & invite-link sharing | `demo-site/backend/auth.py:75` | implemented |
| DATA-DFM-015 | LLM features (data Ask + diagram chat, MiniMax) | `demo-site/backend/llm/minimax.py:56` | implemented |
| DATA-DFM-016 | DFDMaker FastAPI app (routes, exports, admin) | `demo-site/backend/main.py:51` | implemented |
| DATA-DFM-017 | SQL DDL importer (DDL text → PenFile via sqlglot) | `demo-site/backend/generators/sql_import.py:1` | implemented |
| DATA-WEB-001 | Frontend shell, routing & tabs (`App.tsx`) | `demo-site/frontend/src/App.tsx:127` | implemented |
| DATA-WEB-002 | ERD canvas editor (React Flow) | `demo-site/frontend/src/components/ERDCanvas.tsx:829` | implemented |
| DATA-WEB-003 | DFD canvas editor (context + level-1 tabs) | `demo-site/frontend/src/components/DFDCanvas.tsx:429` | implemented |
| DATA-WEB-004 | Diagram auto-layout engine (ELK/route/label) | `demo-site/frontend/src/components/diagram/layout/optimizeLayout.ts:14` | implemented |
| DATA-WEB-005 | Sidebar workspace (Ask/Proposals/Errors/Chat) | `demo-site/frontend/src/components/SidebarGrading.tsx:19` | implemented |
| DATA-WEB-006 | Export, inspector & schema panels | `demo-site/frontend/src/components/ExportPanel.tsx:19` | implemented |
| DATA-WEB-007 | API client, sync hooks & polling | `demo-site/frontend/src/config/api.ts:10` | implemented |
| DATA-WEB-008 | Landing, auth & sharing UI | `demo-site/frontend/src/components/LandingMinimal.tsx:46` | implemented |
| DATA-WEB-009 | Data-demo "Ask" view + demo loaders | `demo-site/frontend/src/components/datademo/loadDemo.ts:17` | implemented |
| DATA-DATA-001 | PEN (`*.dfd.json`) example/demo datasets | `demo-site/frontend/public/austin_permits.dfd.json` | data-asset |
| DATA-DATA-002 | ExampleData workspaces (Austin + biotech) | `ExampleData/AustinPermits/raw` | data-asset |
| DATA-DATA-003 | Agent role prompts (Markdown) | `src/dataroot/agent/prompts/query_agent.md` | data-asset |
| DATA-OPS-001 | Austin Socrata fetcher + demo/registry generators | `scripts/fetch_austin.py:1` | implemented |
| DATA-OPS-002 | MCP launchers, git-kb wrappers & verifier | `scripts/verify_mcp.py:1` | implemented |
| DATA-OPS-003 | Containerization & deploy (Docker, Railway) | `Dockerfile:1` | implemented |
| DATA-OPS-004 | Claude Code skill (Texas Open Data) | `skills/dataroot-texas/SKILL.md:1` | data-asset |
| DATA-OPS-005 | Test suites (dataroot + demo-site repo-analysis) | `tests/` | implemented |
