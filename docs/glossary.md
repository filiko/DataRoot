---
purpose: Key terms and definitions for DataRoot.
prerequisites: none
read-when: Reading the spec, clarifying terminology.
---

# Glossary — docs/glossary.md

Key terms and definitions used throughout the DataRoot project.

← Back to [README.md](../README.md)

**System Map**: DataRoot's source-agnostic inventory of an enterprise data ecosystem — `EnterpriseSystem` → `AccessSurface` → `DataObject` → `DataField`, plus `BusinessRule`, `Connector`, `DataFlow`, and typed `Evidence`. The canonical core artifact; the PenFile ERD/DFD and GitKB docs are projections of it. Full builder spec: [`docs/data-access-map.md`](data-access-map.md).

**Business-rule verification**: deciding, with evidence, whether a stated business rule actually holds — traced across three layers: the English rule, the ERD structure that encodes it (cardinality/keys/referential integrity), and the real systems/surfaces where the data is entered/extracted (the System Map). A rule is `enforced`, a `gap`, `deferred`, or `unverifiable` per layer. Steering doc: [`docs/business-rule-verification.md`](business-rule-verification.md).

**GitKB**: distributed knowledge graph protocol with sparse sync, FTS5 + vector search, and tree-sitter code intelligence. DataRoot persists every workspace document through GitKB's CLI. See https://gitkb.com/ and the [GitKB releases](https://github.com/gitkb/gitkb-releases).

**KBStore**: DataRoot's abstraction over the document store. Two implementations: `GitKBStore` (wraps the `git-kb` CLI; production path) and `LocalMarkdownStore` (pure Markdown; used in tests only).

**MCP (Model Context Protocol)**: standardized stdio JSON-RPC protocol for exposing tools to an AI agent. DataRoot exposes its own bounded MCP server and calls GitKB through the `git-kb` CLI.

**DataRoot MCP server**: the stdio MCP server *DataRoot itself ships* at `src/dataroot/mcp/server.py`. Exposes eight bounded tools (`list_datasets`, `summarize_workspace`, `kb_search`, `kb_list`, `kb_show`, `query_table`, `kb_graph`, `ask`) over JSON-RPC. Launched by `dataroot mcp` or `python -m dataroot.mcp`. The full reference is in [`docs/mcp-server.md`](mcp-server.md). The bundled WSL launcher used by Codex is `scripts/start-mcp.sh`. The in-process verifier is `scripts/verify_mcp.py`.

**GitKB MCP server**: GitKB's own MCP server (separate project — not DataRoot's). DataRoot does **not** call GitKB's MCP server; it shells out to the `git-kb` CLI directly.

**Hard cap**: an upper bound the DataRoot MCP server enforces on every tool's result size — 50 search hits, 100 list records, 200 table rows, depth 3 for graph traversal. Caller-supplied limits above the cap are clamped silently and the actual cap is reported in the response.

**Live Ask**: DataRoot's end-to-end "user types a question, agent answers, and provenance is persisted" loop. Implemented by `query.answer_question` plus `persist_answer_artifacts`. Reachable via the FastAPI endpoint (`/api/ask`) or via the MCP server's `ask` tool.

**Workspace**: one named entry in `src/dataroot/server/app.py:COMPANIES`. Each workspace points at a folder of raw data. Three are registered today: `austin_permits` (Texas Open Data Track), `company_a` (CropProtectorAI biotech demo), `company_b` (BioReactorAI biotech demo). Aliases like `"austin"`, `"texas"`, `"cropprotectorai"` resolve to these keys.

**Provenance trace**: the structured record of what artifacts informed an agent's answer. JSON object with `nodes`, `edges`, `stages`, `provenance_summary`, persisted under `provenance_traces/<timestamp>` and returned to the UI/API caller.

**Lineage edge**: an inferred relationship between two artifacts (e.g., harvest log row references cultivar ID, or two permit rows share an `address_key`).

**`address_key`**: the canonical join key produced by `src/dataroot/link/address_match.py` — uppercase, no punctuation, USPS-style suffixes (`BOULEVARD`→`BLVD`), unit/suite trailers stripped. Lets the Austin workspace link records across datasets that express the same address differently. Heuristic, not exact identity.

**Domain Spec**: a YAML file (`.dataroot/domain_spec.yaml`) produced by Role A that defines entities, relationships, aliases, units, and traversal hints for a workspace.

**Cultivar**: a plant line with specific genetic and phenotypic traits (CropProtectorAI demo domain).

**Terpene synthase (TPS)**: a class of enzymes that produce terpenoid compounds. The genes encoding these are what we trace through FASTAs (CropProtectorAI demo domain).

**Titer**: the concentration of a compound in a sample (typical units: % w/w or mg/g).

**Station**: a monitoring location in the water quality domain (smoke-test domain).

**Wikilink**: `[[slug]]` syntax that GitKB indexes as a graph edge between documents.

**Role A / Role B / Role C**: the three agent roles — Domain Spec Generator, Domain Spec Applier, Query Agent. All run on the same `runner.py` loop with different system prompts and tool allowlists. See [`docs/agent-runtime.md`](agent-runtime.md).

**FK (foreign key)**: a column whose values reference rows in another table. The linker infers FK relationships from column names and value overlap.

**PK (primary key)**: a column with unique values that identify rows in a table. The linker marks likely PKs from unique_count ≈ row_count.

← Back to [README.md](../README.md)
