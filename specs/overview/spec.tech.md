# DataRoot — Technical Spec

**Component count: 56.** One section per component, same IDs/titles/order as `components.md`.
Each requirement is tagged `REQ-DATA-NNN`. All `file:line` cites verified against the working tree
on 2026-06-22. _Amended 2026-07-05: added DATA-DFM-017 (SQL DDL importer) and REQ-DATA-067…071;
cites for not-yet-written code are path-only until implementation lands._

---

## Area: DATA-CORE — DataRoot lineage agent (`src/dataroot/`)

### DATA-CORE-001 — DataRoot CLI
- **What.** `argparse` CLI exposed as console script `dataroot` (`pyproject.toml:21` → `dataroot.cli:main`,
  `src/dataroot/cli.py:18`). Defines 14 subcommands: `init, profile, link, infer-domain-spec,
  apply-domain-spec, list, show, search, graph, ask, miro, miro-refresh-board, serve, mcp`
  (`src/dataroot/cli.py:22-74`).
- **I/O.** Reads cwd; `serve` runs uvicorn (`cli.py:79-83`); `mcp` calls `run_stdio()` (`cli.py:85-88`);
  `ask` prints answer and persists artifacts (`cli.py:172-176`); `graph`/`show` print JSON.
- **Rules.** `init --backend` only allows `gitkb` (`cli.py:23`). All data commands load config then build a
  store, exiting 1 if the store can't be made (`cli.py:115-116,262-266`).
- **REQ-DATA-001** The CLI MUST dispatch each of the 14 subcommands to its handler and exit non-zero on
  unknown command (`cli.py:198`).
- **REQ-DATA-002** `ask` MUST print the answer AND persist inquiry/provenance artifacts (`cli.py:172-176`).

### DATA-CORE-002 — Config & env loader
- **What.** `DataRootConfig` dataclass + `load_config`/`write_config` (`src/dataroot/config.py:11,31,45`).
- **I/O.** Resolves KB backend from `DATAROOT_KB_BACKEND` env, else `.dataroot/config.toml`, else default
  `gitkb` (`config.py:36-42`). Loads `.env` into `os.environ` without overriding existing vars
  (`config.py:64-79`).
- **Rules.** env var wins over config file; `.dataroot/config.toml` parsed line-wise (`config.py:53-61`).
- **REQ-DATA-003** Backend resolution order MUST be env → toml → `"gitkb"` (`config.py:36-42`).
- **REQ-DATA-004** `.env` loading MUST NOT overwrite a variable already present in the environment
  (`config.py:73`).

### DATA-CORE-003 — KBStore protocol & document model
- **What.** `DocumentRecord`, `SearchResult`, `GraphNode/Edge/Result`, and the `KBStore` Protocol
  (`src/dataroot/kb/base.py:11,28,37,51,58`).
- **I/O.** `DocumentRecord` carries `doc_type/slug/title/frontmatter/body`; `normalized_frontmatter()`
  re-injects type/slug/title (`base.py:20-25`).
- **Rules.** The protocol is the persistence boundary; both GitKB and Local stores implement it.
- **REQ-DATA-005** Every record persisted MUST expose normalized frontmatter containing type/slug/title
  (`base.py:20-25`).

### DATA-CORE-004 — GitKB store adapter
- **What.** `GitKBStore` shells out to the `git kb` CLI for persistence, search, commit, graph
  (`src/dataroot/kb/gitkb_store.py:22`).
- **I/O.** `is_available()` checks `git` + `git-kb` on PATH and `git kb --version` rc==0
  (`gitkb_store.py:29-39`); `write` serializes a record to markdown then invokes git-kb (`gitkb_store.py:44`).
- **Rules.** Adapter intentionally does NOT reimplement GitKB behavior (`gitkb_store.py:1-5`).
- **REQ-DATA-006** The adapter MUST report unavailable when either `git` or `git-kb` is absent, or
  `git kb --version` is non-zero (`gitkb_store.py:30-39`).

### DATA-CORE-005 — Local markdown store
- **What.** `LocalMarkdownStore` (`src/dataroot/kb/local_store.py:14`) — a filesystem KBStore used by unit
  tests and as the FastAPI default backend (`server/app.py` defaults `backend="local"`).
- **I/O.** Reads/writes markdown docs with YAML frontmatter; markdown (de)serialization lives in
  `src/dataroot/kb/markdown.py` (`record_to_markdown`, `markdown_to_record`, `append_links`).
- **Rules.** Mirrors the GitKB store's surface so the agent/tools are backend-agnostic.
- **REQ-DATA-007** The local store MUST implement the same `KBStore` surface (write/read/list/search/graph/
  commit/update) used by `ToolExecutor` (`kb/local_store.py`, `agent/tools.py:21-59`).

### DATA-CORE-006 — Workspace profiler
- **What.** `profile_workspace(path, store)` walks a folder, parses each file, writes KB records
  (`src/dataroot/profile/workspace.py:24`).
- **I/O.** Returns `ProfileSummary(files_seen, records_written, skipped_files)` (`workspace.py:16-21,46`).
  Parser dispatch in `src/dataroot/profile/parsers.py` (CSV/JSON/FASTA/MD); slugging in `profile/slug.py`.
- **Rules.** Ignores `.git/.kb/.dataroot/.opencode/__pycache__/node_modules` (`workspace.py:13,53`); a file
  that fails to parse becomes an error record rather than aborting the run (`workspace.py:38-40`).
- **REQ-DATA-008** A parse failure on one file MUST NOT abort profiling; it MUST be recorded and counted as
  skipped (`workspace.py:36-40,46`).
- **REQ-DATA-009** Profiling MUST commit the written records to the store (`workspace.py:45`).

### DATA-CORE-007 — Deterministic linker
- **What.** `link_workspace(store)` adds structural, repeated-ID, column-overlap (and optional address)
  links across KB docs (`src/dataroot/link/linker.py:26`).
- **I/O.** Returns `LinkSummary(relationship_docs, documents_updated, links_added)` (`linker.py:19-23`).
  Writes `relationships/<id>` docs and appends wikilinks to source docs.
- **Rules.** ID detection via `ID_RE` (`linker.py:15`); address join only when enabled
  (`linker.py:37`, gated by `DATAROOT_LINK_ADDRESS_JOIN`).
- **REQ-DATA-010** Linking MUST be deterministic (no LLM) and idempotent — re-running only appends links
  that change content (`linker.py:44-50`).
- **REQ-DATA-011** Address-key links MUST only be emitted when the address join is enabled (`linker.py:37`).

### DATA-CORE-008 — Address-key normalizer
- **What.** `normalize_address` / `address_key` produce a canonical join key from a free-text address
  (`src/dataroot/link/address_match.py:63,77`).
- **I/O.** String in → normalized token string / hash key out; helpers tokenize and split unit numbers
  (`address_match.py:89,97`).
- **REQ-DATA-012** Two addresses that differ only by formatting/case/unit-notation MUST produce the same
  `address_key` (`address_match.py:77`).

### DATA-CORE-009 — Domain-spec infer/apply (Roles A & B)
- **What.** `infer_domain_spec(store, output_path)` (Role A) writes `.dataroot/domain_spec.yaml`;
  `apply_domain_spec(store, spec_path)` (Role B) enriches KB docs (`src/dataroot/domain.py:29,90`).
- **I/O.** `DomainSpecSummary(entities, relationships, output_path)` and `ApplyDomainSummary(updated_docs)`
  (`domain.py:18,25`).
- **REQ-DATA-013** Role A MUST emit a domain spec summarizing detected entities + relationships
  (`domain.py:29`); Role B MUST report the count of documents it enriched (`domain.py:90`).

### DATA-CORE-010 — Agent runner
- **What.** `Runner.run(system_prompt, tools, messages, tool_executor, temperature)` — a single
  harness-agnostic tool-calling loop (`src/dataroot/agent/runner.py:22,28`).
- **I/O.** Tools are JSON schemas (not SDK objects); loop keeps calling the client while tool calls remain
  and an executor is provided (`runner.py:53-76`). Returns `AgentResult`.
- **Rules.** If no executor is passed, it returns after the first round, surfacing tool calls
  (`runner.py:53`).
- **REQ-DATA-014** The runner MUST continue executing tool calls and feeding `role:"tool"` results back
  until the model stops requesting tools (`runner.py:53-76`).

### DATA-CORE-011 — ToolExecutor
- **What.** `ToolExecutor.__call__` dispatches tool names to KBStore-backed functions
  (`src/dataroot/agent/tools.py:14,20`).
- **I/O.** Handles `kb_search, kb_semantic, kb_show, kb_list, kb_graph, kb_update, query_table,
  find_candidate_paths, log_inquiry, render_provenance` (`tools.py:21-58`); unknown tool → `ValueError`
  (`tools.py:59`).
- **Rules.** `kb_update` appends wikilinks then commits (`tools.py:61-69`); `log_inquiry` writes
  `inquiries/<timestamp>` (`tools.py:71-73`).
- **REQ-DATA-015** Every supported tool MUST map to a concrete store operation; an unrecognized tool MUST
  raise (`tools.py:21-59`).

### DATA-CORE-012 — Per-role tool allowlists & schemas
- **What.** `TOOLS` dict mapping each role to its allowed JSON tool schemas; `get_tools(role)`
  (`src/dataroot/agent/tool_sets.py:12,239`).
- **I/O.** Role A (`domain_spec_generator`) = read-only search/show/list (`tool_sets.py:13-58`); Role B
  (`domain_spec_applier`) = show + update (`tool_sets.py:60-92`); Role C (`query_agent`) = full read +
  log_inquiry + render_provenance (`tool_sets.py:93-235`).
- **REQ-DATA-016** Tool scope MUST be enforced per role — Role A/B/C have distinct allowlists; only C may
  render provenance (`tool_sets.py:12-235`).

### DATA-CORE-013 — LLM client (Codex/OpenAI)
- **What.** `CodexClient` wraps the chat-completion call returning an `AgentResult` with tool calls
  (`src/dataroot/agent/codex_client.py:15,30`); `_is_minimax(model)` switches provider behavior
  (`codex_client.py:26`).
- **REQ-DATA-017** The client MUST return tool calls in the shape the runner expects
  (`{"function":{"name","arguments"},"id"}`) (`codex_client.py`, consumed at `runner.py:55-60`).

### DATA-CORE-014 — Deterministic query fallback
- **What.** `answer_question(store, question, limit)` — a no-LLM answerer with domain-specific shortcuts
  and a generic ID/graph/search path (`src/dataroot/query.py:15`).
- **I/O.** Tries CompanyA readiness / PMR-gene, CompanyB fermentation, upcoming-availability, threshold
  exceedances, then ID-centered graph + full-text search, deduped (`query.py:16-60`).
- **Rules.** ID extraction via `ID_RE` (`query.py:12`); always returns a cited answer string, never
  fabricates (`query.py:45-60`).
- **REQ-DATA-018** When no LLM key is present, the system MUST still return a cited answer via this
  deterministic fallback (`query.py:15`, README "Graceful degradation").

### DATA-CORE-015 — Query tools
- **What.** `query_table`, `find_candidate_paths`, `rows_for_id`, `threshold_exceedances`
  (`src/dataroot/query_tools.py:20,38,62,85`).
- **I/O.** `query_table` filters table-doc rows with a limit; `find_candidate_paths` walks the graph between
  start/target terms up to a depth; both return `TableQueryResult` rows / path lists.
- **REQ-DATA-019** `query_table` MUST honor the row `limit` and filter spec; `find_candidate_paths` MUST
  bound traversal depth (`query_tools.py:20,38`).

### DATA-CORE-016 — Tidbit interpreter
- **What.** Turns raw provenance tidbits into human-readable `InterpretedClaim`s + `ProofRow`s, with an
  LLM path and a deterministic fallback (`src/dataroot/render/interpretation.py:12,21,31`).
- **Rules.** `DataTidbitInterpretation.source` defaults to `"deterministic_fallback"` (`interpretation.py:39`);
  forced deterministic via `DATAROOT_USE_TIDBIT_INTERPRETER=0`.
- **REQ-DATA-020** Interpretation MUST degrade to a deterministic claim set when the model is disabled or
  unavailable (`interpretation.py:39`).

### DATA-CORE-017 — Miro board planner
- **What.** `plan_miro_board(...)` builds a `BoardPlan` of `BoardCard`/`BoardConnection`
  (`src/dataroot/render/miro_plan.py:24,36,44,61`), with a deterministic plan path (`miro_plan.py:95`).
- **Rules.** Deterministic planner forced via `DATAROOT_USE_MIRO_PLANNER=0`.
- **REQ-DATA-021** The planner MUST produce a board plan without an LLM when the planner is disabled
  (`miro_plan.py:95`).

### DATA-CORE-018 — Miro REST renderer
- **What.** Renders a provenance trace as a Miro board via the Miro REST API
  (`src/dataroot/render/miro.py:1`); layout constants for frames/lanes/cards (`miro.py:18-45`).
- **I/O.** Reads `MIRO_ACCESS_TOKEN`; `render_provenance_to_miro(...)` returns a board URL (used by
  `cli.py:186`).
- **REQ-DATA-022** Rendering MUST require a Miro access token and return the board URL on success
  (`miro.py`, consumed at `cli.py:186-195`).

### DATA-CORE-019 — Miro board refresh / replace tool
- **What.** `refresh_ask_board(root, board_id, preserve_title, dry_run, replace_existing)` plans and
  optionally executes a board refresh (`src/dataroot/render/miro_refresh.py:137`).
- **I/O.** Returns a `BoardRefreshResult` (rendered demos, deleted count, plan) (`miro_refresh.py:79`);
  append-only vs replace-existing modes (`miro_refresh.py:206`).
- **REQ-DATA-023** `--dry-run` MUST compute the plan without mutating the board (`cli.py:250-252`,
  `miro_refresh.py:137`).

### DATA-CORE-020 — FastAPI Live Ask server
- **What.** FastAPI app exposing the Live Ask pipeline; `POST /api/ask-render` and per-company workspaces
  (`src/dataroot/server/app.py:1`). `COMPANIES` registry = company_a / company_b / austin_permits
  (`app.py:94-113`) plus `COMPANY_ALIASES` (`app.py:114`).
- **I/O.** `AskRenderRequest(company, question, board_id, use_agent, include_proof)` (`app.py:53-58`);
  workspaces resolve to `ExampleData/<...>/raw` (`app.py:98,104,110`).
- **Rules.** Backend defaults to local store but `DATAROOT_SERVER_KB_BACKEND=gitkb` forces GitKB
  (`app.py:19-20`, README).
- **REQ-DATA-024** The server MUST resolve a requested company (by key or alias) to a profiled workspace,
  erroring on unknown names (`app.py:94-114,684-687`).

### DATA-CORE-021 — GitKB runtime bootstrap (server)
- **What.** `bootstrap_gitkb_runtime(root)` prepares the GitKB runtime on server start (author config,
  optional code index) (`src/dataroot/server/bootstrap.py:16`).
- **Rules.** Gated by `_server_wants_gitkb()` (`bootstrap.py:50`); `_ensure_author_config()` sets git
  identity from `GITKB_AUTHOR_NAME/EMAIL` (`bootstrap.py:71`).
- **REQ-DATA-025** Bootstrap MUST run only when the server is configured for the GitKB backend
  (`bootstrap.py:50`).

### DATA-CORE-022 — stdio MCP server
- **What.** stdio MCP server wrapping `ToolExecutor` with 8 bounded tools for the Texas Open Data track
  (`src/dataroot/mcp/server.py:1`); entry `python -m dataroot.mcp` (`src/dataroot/mcp/__main__.py`).
- **I/O.** Tools: `list_datasets, summarize_workspace, kb_search, kb_list, kb_show, query_table, kb_graph,
  ask_and_render`. Hard caps: SEARCH 50 / LIST 100 / TABLE 200 / GRAPH depth 3 (`server.py:37-40`).
- **Rules.** Refuses to start without `git-kb` (`server.py:60-68`); no LocalMarkdownStore fallback; clamps
  over-large requests silently and reports the cap (`server.py:8-17`).
- **REQ-DATA-026** The MCP server MUST require GitKB and MUST NOT fall back to a local store
  (`server.py:60-68`).
- **REQ-DATA-027** Every tool MUST clamp results to its hard cap and report the cap in the response
  (`server.py:8-17,37-40`).

---

## Area: DATA-DFM — DFDMaker demo-site backend (`demo-site/backend/`)

### DATA-DFM-001 — PenFile model
- **What.** Pydantic `PenFile` — the canonical `*.dfd.json` project file
  (`demo-site/backend/models/pen.py:345`), `documentType: "dashbot.dfdmaker"` (`pen.py:346`).
- **Shape.** `project, sources, erd (entities/relationships), dfd (external_entities/processes/data_stores/
  data_flows), layout, styles, postgres, review` (`pen.py:345-356`). ERD types: `Entity` (`pen.py:58`),
  `Attribute` (`pen.py:42`), `Relationship` (`pen.py:89`); DFD types: `Process` w/ optional
  `level_1_diagram` (`pen.py:130,140`), `DataStore` (`pen.py:143`), `DataFlow` (`pen.py:153`).
- **Rules.** Legacy `list[str]` warnings are auto-migrated to `WarningEntry` objects (`pen.py:322-332`);
  SQL exporters read `erd`+`postgres` only (`pen.py:13`).
- **REQ-DATA-028** The PEN schema MUST keep ERD and DFD as separate object graphs cross-linked by IDs
  (`mapped_erd_entity`, `mapped_relationship_id`, `dfd_process_id`) (`pen.py:96,147,158`).
- **REQ-DATA-029** Structural warnings MUST be typed `WarningEntry(rule_id, severity, node_kind, ...)`
  (`pen.py:298-314`).
- **Schema 0.2 (2026-07-05).** Additive fields: `Entity.indexes: list[IndexDef]` (`IndexDef {id, name,
  attribute_ids, unique}` — attribute IDs, not names, so indexes survive renames), `Entity.description`,
  `Entity.color`, `Attribute.enum_values: list[str] | None` (`pen.py`).
- **REQ-DATA-071** Schema 0.2 additions MUST be optional-with-defaults so `schemaVersion` 0.1 project JSON
  validates unchanged (`pen.py`, `tests/test_pen_model_migration.py`).

### DATA-DFM-002 — Source-table model
- **What.** `SourceColumn` + `SourceTableModel` — deterministic parser output (no LLM)
  (`demo-site/backend/models/source.py:11,26`).
- **Shape.** Column carries inferred_type, null_rate, unique_rate, cardinality, sample/unique values,
  role_candidates, possible_semantic_type (`source.py:11`); table defaults `header_row=1,
  data_start_row=2` (`source.py:26`).
- **REQ-DATA-030** Parsed columns MUST record profiling stats and role candidates used downstream by the
  PEN builder (`source.py:11`).

### DATA-DFM-003 — DB models
- **What.** SQLModel tables: `User` (`db_models.py:21`), `Project` w/ `pen_json` JSON column
  (`db_models.py:30`), `ProjectMember` (composite PK, role) (`db_models.py:41`), `Invite`
  (`db_models.py:50`), `WaitlistSubmission` (`db_models.py:62`).
- **REQ-DATA-031** A project's full PEN MUST be persisted as a JSON column with a monotonically increasing
  `revision` (`db_models.py:30`).

### DATA-DFM-004 — File parsers + column profiler
- **What.** `parse_csv` (DuckDB sniff + pandas fallback) (`parsers/csv_parser.py:15`), `parse_excel`
  (.xlsx/.xls, header heuristics, multi-table split) (`parsers/excel.py:190`), and `profile_column`
  (`parsers/profiler.py:181`) with type inference (`profiler.py:78`) and role detection (`profiler.py:133`).
- **Rules.** Header row = first row >50% non-numeric strings (`excel.py:38,47`); type inference requires
  >70% dominance (`profiler.py:87-95`); unsupported extension → `HTTPException 400` (`main.py:112`).
- **REQ-DATA-032** Parsing MUST be deterministic and emit `SourceTableModel`s with per-column profiles
  (`csv_parser.py:15`, `excel.py:190`, `profiler.py:181`).
- **REQ-DATA-033** Only `.csv/.xlsx/.xls` MUST be accepted; other types rejected (`main.py:106-112`).

### DATA-DFM-005 — PEN builder
- **What.** `build_pen_file(tables, project_name, source_paths)` converts profiled tables into a PenFile
  (`generators/pen_builder.py:170`); `apply_proposal(pen, proposal_id, answer_index)` applies a reviewed
  proposal (`pen_builder.py:219`).
- **Rules.** Auto-adds UUID PK + `created_at/updated_at` audit timestamps (`pen_builder.py:50,64`); proposal
  dispatch by type: entity_split/foreign_key/enum_to_lookup/many_to_many_join (`pen_builder.py:262,333,
  368,423`); `answer_index` 0=accept / 1=reject / 2=pending (`pen_builder.py:236`); calls
  `propagate_erd_to_dfd` after build/accept.
- **REQ-DATA-034** Every built entity MUST get a UUID primary key and audit timestamps unless overridden
  (`pen_builder.py:50,64,170`).
- **REQ-DATA-035** Accepting a proposal MUST mutate the ERD then re-propagate the DFD
  (`pen_builder.py:219`, `sync_engine.py:219`).

### DATA-DFM-006 — Normalization proposal detectors
- **What.** Deterministic signal detection → `ReviewProposal`s: `detect_entity_splits` (`proposals.py:54`),
  `detect_enum_candidates` (`proposals.py:104`), `detect_cross_sheet_fks` (`proposals.py:148`),
  `detect_many_to_many` (`proposals.py:267`); `generate_proposals(tables)` runs all (`proposals.py:402`).
  `generate_erd_m2m_proposals(pen)` covers the blank-canvas path (`proposals.py:325`).
- **Rules.** Confidence scores are fixed per signal (e.g. FK verified=0.9 else 0.5, `proposals.py:148`).
- **REQ-DATA-036** Proposals MUST be derived deterministically from column stats / cardinality, not an LLM
  (`proposals.py:54,104,148,267`).

### DATA-DFM-007 — ERD→DFD sync engine
- **What.** `validate(pen)` returns referential `Conflict`s; `propagate_erd_to_dfd(pen)` rebuilds DFD from
  ERD and writes back `dfd_process_id` (`generators/sync_engine.py:52,219`).
- **Rules.** Conflict types incl. `STORE_MAPS_MISSING_ENTITY`, `FLOW_MISSING_FROM/TO_NODE` (blocking),
  `PROCESS/FLOW_ORPHANED_RELATIONSHIP`, `FLOW_MANUAL_STORE_TO_STORE` (warning), `DIRECT_M2M_NO_JOIN`
  (blocking) (`sync_engine.py:21-27,72-211`). Propagation preserves existing layout positions
  (`sync_engine.py:239`).
- **REQ-DATA-037** `validate` MUST flag dangling DFD references to missing ERD entities/relationships and
  unresolved M2M proposals as blocking (`sync_engine.py:72-108,163-211`).
- **REQ-DATA-038** Propagation MUST be ID-keyed and preserve user-modified objects and existing node
  positions (`sync_engine.py:219-241`, `dfd_builder.py:186,241`).

### DATA-DFM-008 — DFD builder
- **What.** `build_dfd_from_erd(erd, existing_dfd)` — one DataStore per accepted entity, one Process + two
  DataFlows per accepted relationship (`generators/dfd_builder.py:143`); `infer_process_name`
  (`dfd_builder.py:28`); `_auto_layout_dfd` (`dfd_builder.py:103`).
- **Rules.** Skips `review_status=="rejected"` (`dfd_builder.py:181,229`); auto-gen orphans dropped,
  user-modified kept (`dfd_builder.py:204,328`); flow built only if both endpoint stores exist
  (`dfd_builder.py:236`).
- **REQ-DATA-039** DFD generation MUST match objects by stable ID, never by name (`dfd_builder.py:1-11`).

### DATA-DFM-009 — Diagram-rules engine
- **What.** Structural rule engine over ERD+DFD; `apply_rules_gate(pen)` is the single gate run at ingest
  and on every patch (`generators/diagram_rules.py:567`); `detect_violations` (`diagram_rules.py:489`).
- **Catalog.** ERD-01 orphan entity (`:121`), ERD-03 self-M2M (`:143`), ERD-04 orphan FK (`:171`),
  DFD-01 floating store (`:199`), DFD-02 black hole (`:230`), DFD-03 miracle (`:254`), DFD-04 grey hole
  (`:278`), DFD-05 disconnected process (`:327`), DFD-06 floating external (`:349`), DFD-08 ext→ext
  (`:369`), DFD-10 read-only store (`:391`), DFD-11 write-only store (`:411`). ERD-02 / DFD-07 / DFD-09
  are mapped from `sync_engine` conflicts via `_SYNC_ENGINE_RULE_MAP` (`diagram_rules.py:432,440`). Catalog
  doc: `demo-site/backend/generators/diagram_rules.md`. _Schema 0.2 adds ERD-05 index integrity: an
  `IndexDef` referencing a missing or rejected attribute ID → warning (`diagram_rules.py`)._
- **Rules.** `apply_rules_gate` regenerates the derived DFD, replaces `pen.review.warnings`, and filters
  `dismissed_warnings` (`diagram_rules.py:567-584`); auto-fix deletes only DFD/derived objects, never ERD
  (`diagram_rules.py:501`).
- **REQ-DATA-040** The gate MUST recompute warnings on every ingest/patch and never auto-mutate the ERD or
  sources (`diagram_rules.py:501,567`).

### DATA-DFM-010 — SQL/DBML/Mermaid exporters
- **What.** `export_sql` (`generators/sql.py:103`), `export_mermaid` (`sql.py:156`), `export_dbml`
  (`sql.py:212`). `dbml.py`/`mermaid.py` are 5-line re-export shims (`generators/dbml.py:4`,
  `generators/mermaid.py:4`).
- **Rules.** Read `erd`+`postgres` only, ignore layout, accepted entities only, topo-ordered tables, FK as
  ALTER constraints; validate via SQLGlot and downgrade failures to a comment warning (`sql.py:114,146`).
  _Schema 0.2: additionally emits `CREATE [UNIQUE] INDEX` per `Entity.indexes`, `CREATE TYPE ..._enum AS
  ENUM` for `Attribute.enum_values` (used as the column type), and `COMMENT ON TABLE` for
  `Entity.description`. Topo-sort first pass keys on "no outgoing relationships" (an entity that is only an
  FK target is a valid root), fixing the earlier misclassification._
- **REQ-DATA-041** SQL export MUST validate via SQLGlot and emit a warning comment rather than crashing on
  invalid DDL (`sql.py:146`).

### DATA-DFM-011 — Typed-ops service
- **What.** `OpsService.apply_op(pen, op, payload)` applies 19 typed operations through one dispatch table
  (`services/ops_service.py:163,166`).
- **Ops.** entity.add/update/delete, attribute.add/update/delete, relationship.add/update/delete/
  m2m_convert, index.add/update/delete (schema 0.2), dfd.flow.rename/reconnect/delete, layout.move_node,
  proposal.answer, postgres.update_settings (`ops_service.py:167-182`); unknown op → `ValueError`
  (`ops_service.py:186`).
- **Rules.** entity/relationship deletes cascade to dependent DFD objects (`ops_service.py:224-234,
  325-336`); `_proposal_answer` maps `{0:accepted,1:rejected,2:rejected}` (`ops_service.py:598`) — note 2
  differs from `pen_builder.apply_proposal` where 2=pending (flagged below).
- **REQ-DATA-042** Each op MUST validate inputs and cascade DFD cleanup; unknown ops MUST raise
  (`ops_service.py:163-186,224-234`).

### DATA-DFM-012 — Project persistence (DB store + FS service)
- **What.** `ProjectStore` (DB-backed: load/save/create/delete/list_for_user/get_revision)
  (`services/project_store.py:20,27,41,60,74,94`); `ProjectService` (filesystem `.dfd.json`
  open/save/delete) (`services/project_service.py:28,45,61`).
- **Rules.** `create` inserts an owner `ProjectMember` (`project_store.py:41`); `list_for_user` joins
  membership ordered by `updated_at` (`project_store.py:74`); FS `save` bumps revision and writes
  `model_dump_json(by_alias=True)` (`project_service.py:45`).
- **REQ-DATA-043** Persistence MUST enforce optimistic concurrency via `project.revision` and only return
  projects the user is a member of (`main.py:621-625`, `project_store.py:74`).

### DATA-DFM-013 — Repo-analysis pipeline
- **What.** `analyze_repo(repo, output, ...)` turns a code repo into a PEN via evidence→facts→compile
  (`repo_cli.py:82`). Stages: `build_inventory` (`repo_analysis/inventory.py:123`),
  `collect_fastapi_routes` (`repo_analysis/fastapi_provider.py:96`), `collect_model_evidence`
  (`repo_analysis/model_provider.py:142`), optional `collect_gitkb_evidence`
  (`repo_analysis/gitkb_provider.py:37`), `auto_accept_phase_a_facts` (`fastapi_provider.py:191`),
  `compile_pen_from_facts` (`repo_analysis/compiler.py:56`).
- **I/O.** Writes `project.json, decisions.json, inventory.json, evidence.jsonl, facts.jsonl,
  project.dfd.json, run-log.jsonl` (`repo_cli.py:114-...`). Models in `repo_analysis/models.py`.
- **Rules.** Only `status=="accepted"` facts are compiled (`compiler.py:52,56`); entities accepted at
  confidence ≥0.85 with auto-inserted UUID PK (`compiler.py:112`); a "User or Client" external entity and
  request/response + read/write flows are synthesized (`compiler.py:182,191`).
- **REQ-DATA-044** The compiler MUST emit a schema-valid PenFile built only from accepted facts
  (`compiler.py:52,56`, test `test_compiler_emits_valid_penfile` at
  `demo-site/backend/tests/test_repo_analysis_phase_a.py:129`).

### DATA-DFM-014 — Auth, sessions & invite sharing
- **What.** Invite-gated signup, password login, session cookie (`auth.py`), plus invite-link sharing &
  membership enforcement (`sharing.py`). `current_user` (`auth.py:75`), endpoints
  `/auth/signup|login|logout|me` (`auth.py:97,118,127,133`); `require_member`/`require_owner`
  (`sharing.py:23,38`); invite create/accept/peek (`sharing.py:64,89,117`).
- **Rules.** bcrypt 12 rounds, 72-byte truncation (`auth.py:18-19,22`); `AUTH_DISABLED=1` returns a local
  dev user (`auth.py:60-75`); invites default `max_uses=20`, expire in 7 days (`sharing.py:74-75`);
  roles = owner / editor.
- **REQ-DATA-045** Mutations MUST be gated by membership; owner-only actions (delete project, create
  invite) MUST require ownership (`main.py:436-443`, `sharing.py:38,64`).
- **REQ-DATA-046** An expired or exhausted invite MUST be rejected (HTTP 410) (`sharing.py:89`).

### DATA-DFM-015 — LLM features (data Ask + diagram chat)
- **What.** `answer_question` over bundled demo CSVs (`llm/ask.py:28`) and `chat_about_diagram`
  (`llm/minimax.py:56`); MiniMax via Anthropic-compatible endpoint (`minimax.py:20-22`); `ask_about_data`
  returns cited JSON (`minimax.py:92`).
- **Rules.** Both LLM paths never raise — they return friendly/cited fallbacks on failure
  (`minimax.py:56,92`); answers capped (~130 words chat, 3 sources for Ask) (`minimax.py:47,137`).
- **REQ-DATA-047** LLM calls MUST degrade gracefully (no exception) and the data Ask MUST return at most 3
  cited sources (`minimax.py:56,92,137`).

### DATA-DFM-016 — DFDMaker FastAPI app
- **What.** `FastAPI(title="DFDMaker API")` wiring all routes (`demo-site/backend/main.py:51`): ingest,
  blank/example/morsat0/claude-eval/repo-analysis schema creation (`main.py:129,161,202,213,224,246,305`),
  SQL DDL import (`POST /schema/import-sql`, → DATA-DFM-017),
  project CRUD + ops + layout patch (`main.py:360-680`), validate/analyze, chat/ask, exports, waitlist,
  admin waitlist viewer (`main.py:1050`), and SPA static fallback (`main.py:1100-1119`).
- **Rules.** SessionMiddleware + CORS (`main.py:60-82`); `init_db` on startup (`main.py:85-87`); imports
  resolve by injecting backend dirs into `sys.path` (`main.py:24-28`); `apply_rules_gate` runs on every
  create/import (`main.py:152,169,...`).
- **REQ-DATA-048** Every project mutation route MUST run validation/rules and bump revision before saving
  (`main.py:638-651,710-713`).

### DATA-DFM-017 — SQL DDL importer
- **What.** `import_sql(sql_text, dialect="auto", project_name)` parses DDL into a `PenFile`
  (`demo-site/backend/generators/sql_import.py`), backed by a shared type-affinity table
  (`demo-site/backend/generators/sql_types.py`: `PG_CANONICAL_TYPES` + sqlglot `DataType.Type` →
  `pg_type` map). Exposed via `POST /schema/import-sql` (`main.py`), body
  `{sql, dialect: auto|postgres|mysql|sqlite, project_name}`; response `{project_id, pen}` matches the
  other ingest routes.
- **Shape.** Two-pass sqlglot walk: pass 1 collects `CREATE TABLE` → `Entity`/`Attribute`
  (column constraints → `key_role`/`nullable`/`default`/`check_constraint`; composite PK collapses to
  first-column primary + warning); pass 2 resolves FKs from inline `REFERENCES`, table-level constraints,
  and `ALTER TABLE ADD CONSTRAINT` → `Relationship` + `RelationshipPostgres`. `CREATE INDEX` →
  `Entity.indexes`; `CREATE TYPE ... AS ENUM` / MySQL `ENUM(...)` → `Attribute.enum_values`;
  `COMMENT ON TABLE` → `Entity.description`. Cardinality heuristic: FK column unique → 1:1, else N:1;
  `from_min=0` when the FK column is nullable. `dialect="auto"` tries postgres → mysql → sqlite and picks
  the parse yielding CREATE TABLEs with fewest errors.
- **Rules.** Finishes through the standard ingest recipe: auto-layout (`pen_builder`), 
  `propagate_erd_to_dfd`, `apply_rules_gate`, `ProjectStore.create`. Views/inserts/triggers/unknown
  statements are skipped with warnings, never fatal.
- **REQ-DATA-067** SQL import MUST parse via sqlglot with per-statement error isolation — one
  unparseable/unsupported statement becomes a warning, never a whole-import failure; the route returns 422
  only when zero tables parse (`sql_import.py`).
- **REQ-DATA-068** Imported column types MUST map through the canonical type-affinity table onto the
  `pg_type` canon, with `type_fallback` warnings whenever fidelity is lost (dropped varchar lengths, TIME,
  binary → text) (`sql_types.py`).
- **REQ-DATA-069** FKs MUST be resolved in a second pass over collected tables — covering inline
  REFERENCES, table-level constraints, and trailing/forward-referencing `ALTER TABLE ADD CONSTRAINT` —
  producing `Relationship` + `RelationshipPostgres` with the unique→1:1 / else N:1 cardinality heuristic
  (`sql_import.py`).
- **REQ-DATA-070** SQL import MUST terminate through the standard ingest recipe (auto-layout,
  `propagate_erd_to_dfd`, `apply_rules_gate`, `ProjectStore.create`) and surface skipped constructs as
  `WarningEntry(rule_id="IMPORT-01")` in `pen.review.warnings` (`sql_import.py`, `main.py`).

---

## Area: DATA-WEB — DFDMaker frontend (`demo-site/frontend/`)

### DATA-WEB-001 — Frontend shell, routing & tabs
- **What.** Single-component app, path-based routing via `window.location.pathname`
  (`src/App.tsx:127`); tabs ERD/DFD/Schema/Export (`App.tsx:114,322`); pseudo-routes `/docs`, `/demo`,
  `/invite/:token` (`App.tsx:330,167,179`). `main.tsx` patches `fetch` to always send credentials
  (`src/main.tsx:9-11`).
- **Rules.** Render gates: docs → loading → login → landing → projects → editor (`App.tsx:330-388`);
  auto-arrange iterates ERD + DFD-root + each level-1 scope (`App.tsx:259`); PDF export via toPng + jsPDF
  (`App.tsx:300`).
- **REQ-DATA-049** The shell MUST gate views by auth/pen state and route `/docs`, `/demo`, `/invite/:token`
  without a router library (`App.tsx:167,179,330-388`).

### DATA-WEB-002 — ERD canvas editor
- **What.** React Flow ERD editor (`src/components/ERDCanvas.tsx:829`) with `TableNode` (`:188`),
  `CardinalityEdge` crow's-foot markers (`:361`), `penToFlow` (`:426`), entity/relationship dialogs
  (`:544,:736`). _Schema 0.2: `TableNode` renders `Entity.color` as a header tint, `Entity.description`
  as a tooltip, and an enum badge on attributes with `enum_values` (read-only rendering first)._
- **Rules.** Writes via direct `fetch` to `PATCH /schema/{id}/pen` (`:874`) and `POST /projects/{id}/ops`
  (`:957`); new entity auto-generates UUID PK + audit attrs (`:1030-1070`); entity delete uses
  `DELETE /schema/{id}/entity/{eid}` with 409→`?force=true` cascade confirm (`:985`).
- **REQ-DATA-050** ERD edits MUST persist through the typed-ops / full-pen endpoints and surface the cascade
  confirmation on conflict (`ERDCanvas.tsx:874,957,985`).

### DATA-WEB-003 — DFD canvas editor
- **What.** React Flow DFD editor (`src/components/DFDCanvas.tsx:429`) with a "Context" root tab plus one
  tab per process that has a `level_1_diagram` (`:434`); `dfdToFlow` builds nodes/edges (`:183`).
- **Rules.** Node drag → 500ms-debounced `patchLayout` (`:208`); edge ops `dfd.flow.reconnect/rename/
  delete` via `useProjectOps` (`:236,268,295`); wrapped in `DiagramThemeProvider` (`:449`).
- **REQ-DATA-051** DFD layout changes MUST be debounced and persisted via the layout-patch endpoint; flow
  edits MUST go through typed ops (`DFDCanvas.tsx:208,236-295`).

### DATA-WEB-004 — Diagram auto-layout engine
- **What.** Pure-TS layout pipeline under `src/components/diagram/layout/`: `optimizeDiagramLayout`
  orchestrates normalize → place → assign handles → route → label (`optimizeLayout.ts:14`). Stages:
  `buildDfdLayoutGraph/buildErdLayoutGraph` (`graphModel.ts:21,56`), `autoArrangeNodes` (ELK)
  (`elkLayout.ts:21`), `assignHandles` (`handleAssignment.ts:51`), `routeEdges` orthogonal
  (`orthogonalRouter.ts:15`), `placeEdgeLabels` (`labelPlacement.ts:11`), `repairNodeOverlaps`
  (`overlap.ts:4`).
- **Rules.** ELK produces candidate layouts that are scored; overlap repair is grid-snapped, ≤80 passes
  (`overlap.ts:4`); preset `label_t`/`label_offset` are honored (`labelPlacement.ts:11`).
- **REQ-DATA-052** Auto-arrange MUST output node/edge layout patches (`toLayoutNodePatch`/`toLayoutEdgePatch`
  at `optimizeLayout.ts:30,40`) consumable by `PATCH /schema/{id}/layout`.

### DATA-WEB-005 — Sidebar workspace
- **What.** Left-sidebar host with tabs Ask/Proposals/Errors/Chat (`src/components/SidebarGrading.tsx:19`),
  rendering `AskPanel`, `ProposalPanel`, `ErrorsPanel`, `ChatPanel` (`:79-90`). Proposals reviewed via
  `POST /schema/{id}/apply-proposal` + `PATCH /schema/{id}/pen` (`ProposalPanel.tsx:33,43`); errors via
  `GET /schema/{id}/analyze` (`ErrorsPanel.tsx:30`); chat via `POST /llm/chat` (`ChatPanel.tsx:41`).
- **Rules.** Errors tab shown only when `issueCount>0`; proposals badge = pending + warning-proposals
  (`SidebarGrading.tsx:25`, `ProposalPanel.tsx:229`).
- **REQ-DATA-053** The sidebar MUST surface live proposals, conflicts/static issues, and chat against the
  current project (`SidebarGrading.tsx:79-90`).

### DATA-WEB-006 — Export, inspector & schema panels
- **What.** `ExportPanel` (tabbed SQL/Mermaid/DBML/.pen viewer w/ copy+download, `GET /schema/{id}/export/
  {format}`) (`src/components/ExportPanel.tsx:19,31`); `SchemaInspector` read-only schema browser
  (`src/components/SchemaInspector.tsx:248`); `WarningsBanner` collapsible summary memoized to avoid
  re-render on polling (`src/components/WarningsBanner.tsx:75`). _Schema 0.2: `SchemaInspector` also lists
  each entity's `indexes`._
- **REQ-DATA-054** Export MUST fetch each format from the backend export route and allow copy/download
  (`ExportPanel.tsx:31`).

### DATA-WEB-007 — API client, sync hooks & polling
- **What.** `API` endpoint builder (`src/config/api.ts:10`) + hooks: `useFullPenReplace`
  (`hooks/useFullPenReplace.ts:6` → `PATCH /schema/{id}/pen`), `useLayoutPatch`
  (`hooks/useLayoutPatch.ts:31` → `PATCH /schema/{id}/layout`), `useProjectOps`
  (`hooks/useProjectOps.ts:17` → `POST /projects/{id}/ops`), `useProjectPolling` (2500ms revision poll,
  `hooks/useProjectPolling.ts:18`).
- **Rules.** `API_BASE = import.meta.env.VITE_API_URL || ''` (`api.ts:1`); polling skips when
  `document.hidden` and only refetches when server revision is ahead (`useProjectPolling.ts:44-61`).
- **REQ-DATA-055** Collaborator sync MUST poll revision on an interval and refetch the pen only when the
  server is ahead (`useProjectPolling.ts:44-61`).
- **REQ-DATA-056** All mutations MUST send the session cookie (global `fetch` credentials patch,
  `main.tsx:9-11`).

### DATA-WEB-008 — Landing, auth & sharing UI
- **What.** `LandingPage` theme router (`src/components/LandingPage.tsx:15`) → `LandingMinimal` (functional
  entry: upload/repo/import/loaders, `LandingMinimal.tsx:46`) or `LandingChalkboard`
  (`LandingChalkboard.tsx:322`); `LoginPage` invite-gated signup/login (`LoginPage.tsx:12`);
  `WaitlistSection` (`WaitlistSection.tsx:8`); `ShareDialog` invite-link modal (`ShareDialog.tsx:10`);
  `ProjectList` (`ProjectList.tsx:22`). _Schema 0.2: the upload entry also accepts `.sql` files and a
  paste-DDL action with a dialect select (default auto), via `src/components/sqlImport.ts` →
  `POST /schema/import-sql` (→ DATA-DFM-017)._
- **Rules.** Signup requires an invite code (`LoginPage.tsx:20`); share dialog builds
  `${origin}/invite/${token}` with 7-day/20-use copy (`ShareDialog.tsx:20-26`).
- **REQ-DATA-057** The default signup flow MUST require an invite code, and project sharing MUST issue a
  tokenized invite link (`LoginPage.tsx:20`, `ShareDialog.tsx:20`).

### DATA-WEB-009 — Data-demo "Ask" view + demo loaders
- **What.** Scripted "Ask" panel hitting `POST /ask` (`datademo/AskPanel.tsx:24,35`) with preset questions
  (`datademo/demoData.ts:28`); `loadDemoProject` fetches a bundled `.dfd.json` and best-effort imports it
  (`datademo/loadDemo.ts:17`), with 4 demos registered (`loadDemo.ts:10`). Repo-analysis client helpers in
  `repoAnalysis.ts` (`analyzeRepository:51`, `analyzeRepositoryFolder:69`, `importDfdJsonFile:85`).
- **REQ-DATA-058** The Ask view MUST query the backend `/ask` route; demo loaders MUST fetch the bundled
  PEN file then import it (`AskPanel.tsx:35`, `loadDemo.ts:17`).

---

## Area: DATA-DATA — Data assets

### DATA-DATA-001 — PEN (`*.dfd.json`) example/demo datasets
- **What.** Bundled PenFile JSON used as demos/fixtures: `demo-site/frontend/public/*.dfd.json`
  (austin_permits, example_store, dfdmaker_self, morsat0_candidate_exercise) and
  `demo-site/backend/demo_assets/*.dfd.json`, plus copies at the demo-site root.
- **Shape.** `documentType: "dashbot.dfdmaker"`, schema `project/sources/erd/dfd/layout/styles/postgres/
  review` (verified in `demo-site/frontend/public/dfdmaker_self.dfd.json`).
- **REQ-DATA-059** Bundled `.dfd.json` files MUST validate against the `PenFile` model
  (`demo-site/backend/models/pen.py:345`).

### DATA-DATA-002 — ExampleData workspaces
- **What.** Raw source datasets the dataroot pipeline profiles: `ExampleData/AustinPermits/raw` (4 City of
  Austin slices), `ExampleData/CompanyA_AgriTrait` (incl. `expected_answers/`, `provenance_targets/`),
  `ExampleData/CompanyB_Fermentation`, `CompanyC_GeneticEngineering`, `water_quality`.
- **REQ-DATA-060** CompanyA/B MUST ship `expected_answers/` and `provenance_targets/` for output diffing
  (`ExampleData/CompanyA_AgriTrait/`, README "Biotech demo workspaces").

### DATA-DATA-003 — Agent role prompts
- **What.** Hand-authored system prompts, one per agent role: `src/dataroot/agent/prompts/
  domain_spec_generator.md`, `domain_spec_applier.md`, `query_agent.md` (packaged via
  `pyproject.toml:31`).
- **REQ-DATA-061** Each agent role MUST have its own prompt file packaged with the distribution
  (`pyproject.toml:30-31`).

---

## Area: DATA-OPS — Tooling, build, tests

### DATA-OPS-001 — Austin fetcher + demo/registry generators
- **What.** `scripts/fetch_austin.py` pulls four bounded Socrata slices and applies linker column renames
  (`scripts/fetch_austin.py:1`, stdlib only); `scripts/gen_companyc_registries.py` generates CompanyC CSVs;
  `demo-site/demo_data/build_austin_dfd.py` builds the pre-baked Austin PEN demo.
- **REQ-DATA-062** The fetcher MUST rename `permit_number→permit_id` and `foldernumber→case_task_id` to the
  shape the linker expects (`scripts/fetch_austin.py` docstring, README:96-98).

### DATA-OPS-002 — MCP launchers, git-kb wrappers & verifier
- **What.** `scripts/start-mcp.sh` (WSL launcher, silent on stdout) , `scripts/git-kb-wrapper.sh` /
  `scripts/git-kb.bat` (WSL passthrough to `~/git-kb`), `scripts/verify_mcp.py` (in-process JSON-RPC
  pass/fail matrix, no WSL needed) (`scripts/verify_mcp.py:1`), `scripts/compile_timer.py` (pipeline timer).
- **Rules.** `start-mcp.sh` exports `DATAROOT_LINK_ADDRESS_JOIN=1` and execs `python -m dataroot.mcp`,
  keeping stdout clean so JSON-RPC framing isn't corrupted.
- **REQ-DATA-063** The MCP launcher MUST emit nothing on stdout before the JSON-RPC handshake
  (`scripts/start-mcp.sh`, README:114-119).

### DATA-OPS-003 — Containerization & deploy
- **What.** Root `Dockerfile` (python:3.11-slim, installs git-kb `GITKB_VERSION=0.1.55`, pip-installs the
  package, runs uvicorn) (`Dockerfile:1`); `railway.json` deploys via the Dockerfile (`railway.json:1`);
  demo-site has its own `demo-site/backend/railway.toml` + `demo-site/frontend/railway.toml`.
- **Rules.** Image sets `DATAROOT_SERVER_KB_BACKEND=gitkb` and configures git identity (`Dockerfile:8,17-18`).
- **REQ-DATA-064** The container MUST bundle the git-kb CLI and a git identity so the GitKB backend works
  at runtime (`Dockerfile:14-18`).

### DATA-OPS-004 — Claude Code skill (Texas Open Data)
- **What.** `skills/dataroot-texas/SKILL.md` documents safe-use rules and question shapes for the DataRoot
  MCP server (`skills/dataroot-texas/SKILL.md:1`).
- **REQ-DATA-065** The skill MUST describe bounded, attribution-required, no-PII usage without hardcoding
  canned answers (`skills/dataroot-texas/SKILL.md`).

### DATA-OPS-005 — Test suites
- **What.** dataroot tests (`tests/`, 12 modules incl. `test_mcp_server.py`, `test_render_miro.py`,
  `test_profile_link.py`, `test_query_tools.py`, `test_server_app.py`) run via `pytest`
  (`pyproject.toml:33-35`); demo-site backend tests
  (`demo-site/backend/tests/`: `test_repo_analysis_phase_a.py` (12 tests), `test_sql_import.py` (SQL DDL
  importer + round-trip through `export_sql`, fixtures under `tests/fixtures/ddl/*.sql`),
  `test_pen_model_migration.py` (schema 0.1 JSON still validates)) with `conftest.py` path injection.
- **REQ-DATA-066** Repo-analysis tests MUST assert all 7 output artifacts are written and only accepted
  facts compile into the PEN (`test_repo_analysis_phase_a.py:239,158`).
