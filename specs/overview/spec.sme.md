# DataRoot — Plain-Language Spec

**Component count: 56.** Same components, same IDs, same order as `components.md` and `spec.tech.md`,
written for a non-engineer. No code references.

This repository holds **two related products**:

- **DataRoot** (the `src/` half): point it at a messy folder of files and it builds a searchable
  "knowledge graph," then lets you ask plain-English questions and get cited answers that can be drawn
  as a Miro board.
- **DFDMaker** (the `demo-site/` half): upload a spreadsheet (or analyze a code repo) and it draws you a
  database diagram (an ERD) and a data-flow diagram (a DFD), checks them for design mistakes, and exports
  the database setup as SQL.

---

## DATA-CORE — The DataRoot lineage agent

- **DATA-CORE-001 — Command-line tool.** The `dataroot` command. One tool with 14 actions (set up, ingest
  a folder, link records, infer/apply a domain spec, search, show, graph, ask, draw on Miro, run a server).
- **DATA-CORE-002 — Settings loader.** Decides which storage backend to use and reads secrets from a `.env`
  file, never overwriting values you already set.
- **DATA-CORE-003 — Document model.** The shared definition of "a knowledge document" (its type, name,
  contents) that everything else reads and writes.
- **DATA-CORE-004 — GitKB connector.** Talks to the external "git-kb" tool that actually stores, searches,
  and version-controls the knowledge graph. It checks git-kb is installed before doing anything.
- **DATA-CORE-005 — Local file storage.** A simpler storage option that keeps documents as plain Markdown
  files, used for testing and as the default for the web server.
- **DATA-CORE-006 — Folder profiler.** Walks a folder, reads each CSV/JSON/FASTA/Markdown file, and turns
  it into knowledge documents. If one file can't be read, it notes the problem and keeps going.
- **DATA-CORE-007 — Linker.** Connects related documents automatically by spotting the same IDs and shared
  columns across files. It is rule-based (no AI) so results are repeatable.
- **DATA-CORE-008 — Address matcher.** Turns messy street addresses into a single standard key, so records
  about the same place can be joined even when the text differs.
- **DATA-CORE-009 — Domain expert (setup).** Two assistant roles: one proposes a "domain spec" describing
  your data's entities and relationships; the other applies that spec to tag and cross-link the documents.
- **DATA-CORE-010 — Agent loop.** The engine that lets the assistant take a question, call tools, read the
  results, and keep going until it has an answer.
- **DATA-CORE-011 — Tool box.** The set of nine actions the assistant can take (search, show, list, graph,
  update, query a table, find paths, log the inquiry, draw the board). Anything outside this list is
  refused.
- **DATA-CORE-012 — Role permissions.** Each assistant role only gets the tools it's allowed to use, so the
  query assistant can read and draw but can't quietly rewrite your knowledge base.
- **DATA-CORE-013 — AI connection.** The piece that actually talks to the language model when one is
  available.
- **DATA-CORE-014 — No-AI answer mode.** A built-in fallback that answers questions with citations using
  only rules and search, so you still get a cited answer even without an AI key.
- **DATA-CORE-015 — Query helpers.** Utilities to filter rows in a table document and to trace connection
  paths between things in the graph.
- **DATA-CORE-016 — Plain-English explainer.** Turns raw evidence into readable "claims" and a proof table,
  with a no-AI fallback.
- **DATA-CORE-017 — Board planner.** Decides what cards and connections should appear on the Miro board.
- **DATA-CORE-018 — Board drawer.** Actually creates the board in Miro and returns its link.
- **DATA-CORE-019 — Board refresher.** Re-draws or cleans up an existing Miro board, with a "dry run"
  preview that changes nothing.
- **DATA-CORE-020 — Web server.** The website/API that runs the "Live Ask" experience and knows about the
  prepared example datasets (a farm-trait company, a fermentation company, and Austin permits).
- **DATA-CORE-021 — Server start-up prep.** On launch it gets the git-kb storage ready (identity, indexing)
  when that backend is selected.
- **DATA-CORE-022 — Plug-in (MCP) server.** A small, safe server other AI tools can plug into. It only
  offers eight actions and caps result sizes, and refuses to run without git-kb installed.

## DATA-DFM — DFDMaker (the diagram web app)

- **DATA-DFM-001 — Project file format.** The single file (a `.dfd.json`) that stores a whole DFDMaker
  project: its tables (ERD), its data-flow diagram (DFD), the on-screen layout, settings, and any open
  review notes. Version 0.2 adds optional extras — table indexes (speed-up hints for the database),
  columns restricted to a fixed list of values, and a description and color per table — and older project
  files still open unchanged.
- **DATA-DFM-002 — Spreadsheet read-out.** A neutral description of a parsed spreadsheet table and its
  columns (data types, how unique each column is, likely role), produced without any AI.
- **DATA-DFM-003 — Accounts & projects database.** The tables that store users, projects (with the whole
  project file inside), who can access each project, invite links, and waitlist sign-ups.
- **DATA-DFM-004 — File readers.** Read CSV and Excel files, figure out where the header row is, and profile
  each column. Only spreadsheets are accepted.
- **DATA-DFM-005 — Diagram builder.** Turns the parsed tables into a project: it creates entities, gives each
  one an ID primary key and created/updated timestamps, and proposes clean-ups you can accept or reject.
- **DATA-DFM-006 — Suggestion finder.** Spots common database design issues (a column that should be its own
  table, a list that should become a lookup table, hidden links between sheets, many-to-many links needing a
  join table) and raises them as review questions.
- **DATA-DFM-007 — ERD↔DFD keeper.** Keeps the data-flow diagram in sync with the table diagram, and reports
  conflicts (e.g. a flow pointing at something that no longer exists) so a broken project can't be saved.
- **DATA-DFM-008 — Flow-diagram generator.** Builds the data-flow diagram from the tables: a store per table
  and a process plus two arrows per relationship, while leaving anything you edited by hand untouched.
- **DATA-DFM-009 — Design-rules checker.** A catalog of structural rules (orphan tables, "black hole" and
  "miracle" processes, floating stores, etc.) that flags problems every time you ingest or edit, and can
  auto-fix derived diagram objects without ever changing your tables.
- **DATA-DFM-010 — Exporters.** Produce the equivalent PostgreSQL setup script, plus DBML and Mermaid diagram
  text. The SQL is checked for validity; if something's off it adds a warning comment instead of failing.
  The script now also includes any indexes, fixed-value lists, and table descriptions you've defined.
- **DATA-DFM-011 — Safe-edit operations.** A fixed list of 19 allowed edits (add/rename/delete tables,
  columns, relationships, indexes, flows, move things, answer a proposal, change settings). Deletes clean up
  anything that depended on them.
- **DATA-DFM-012 — Saving & loading.** Stores projects in the database (and can read/write project files on
  disk), tracks who can see each one, and uses a revision number so two people don't overwrite each other.
- **DATA-DFM-013 — Code-repo analyzer.** Points at a codebase, gathers evidence (its files, its web routes,
  its data models, optional git-kb symbols), keeps only the trustworthy facts, and compiles them into a
  diagram project.
- **DATA-DFM-014 — Sign-in & sharing.** Invite-only sign-up, password login, and share links. Each project
  has an owner and editors; only the owner can delete it or make invites, and expired/used-up invites are
  refused. A demo mode can skip login entirely.
- **DATA-DFM-015 — Built-in AI helpers.** A scripted "ask the data" answer feature and a chat that explains
  your diagram. Both fail softly with a friendly message rather than erroring.
- **DATA-DFM-016 — The web service.** The application that ties all the above routes together: uploading,
  loading examples, editing, validating, exporting, the waitlist, an admin viewer, and serving the website.
  Every change is validated and version-bumped before it's saved.
- **DATA-DFM-017 — SQL importer.** Paste or upload an existing database setup script (SQL) and it becomes a
  project: tables, columns, keys, and relationships are read out of the script, anything it can't understand
  is listed as a warning instead of failing, and the result goes through the same checks as every other way
  of creating a project. It understands PostgreSQL scripts best and can also read MySQL and SQLite ones.

## DATA-WEB — DFDMaker website (what you see in the browser)

- **DATA-WEB-001 — App frame.** The overall page with its ERD / DFD / Schema / Export tabs, plus special
  pages for docs, the demo, and accepting an invite link. It always sends your login cookie with requests.
- **DATA-WEB-002 — Table-diagram editor.** The interactive ERD canvas where you add and edit tables,
  columns, and relationships, with crow's-foot notation. New tables automatically get an ID key and audit
  timestamps; deleting a table asks you to confirm the knock-on removals. Tables can show a custom color
  and description, and columns limited to a fixed list of values get a small badge.
- **DATA-WEB-003 — Flow-diagram editor.** The interactive DFD canvas, with a top-level "Context" view and a
  detailed view for each process. Moving things auto-saves, and renaming/reconnecting arrows goes through the
  safe-edit operations.
- **DATA-WEB-004 — Auto-arrange.** The behind-the-scenes engine that tidies a diagram: it lays out the boxes,
  picks where arrows attach, routes them at right angles, and places labels so they don't overlap.
- **DATA-WEB-005 — Side panel.** The left workspace with four tabs: Ask, Proposals (accept/reject
  suggestions), Errors (design problems found), and Chat (talk to the AI about your diagram).
- **DATA-WEB-006 — Export & inspector panels.** A viewer to copy or download the SQL/Mermaid/DBML/project
  file, a read-only schema browser (which also lists each table's indexes), and a collapsible banner that
  summarizes current warnings.
- **DATA-WEB-007 — Server connection & live sync.** The code that calls the backend and keeps multiple
  collaborators in sync by quietly checking every few seconds whether someone else changed the project.
- **DATA-WEB-008 — Landing, login & sharing screens.** The marketing/landing pages, the invite-gated
  sign-up/login card, the early-access waitlist form, and the share-link dialog. The starting screen also
  accepts a SQL script (dropped as a file or pasted) to create a project from an existing database.
- **DATA-WEB-009 — Demo "Ask" view & loaders.** The scripted question-and-answer demo with preset questions,
  plus the buttons that load the bundled example projects.

## DATA-DATA — Bundled data

- **DATA-DATA-001 — Example project files.** Ready-made `.dfd.json` projects (Austin permits, an example
  store, DFDMaker's own self-portrait, a candidate exercise) used as demos and starting points.
- **DATA-DATA-002 — Example source datasets.** Raw input folders the DataRoot pipeline ingests: four City of
  Austin public datasets and several synthetic company datasets. The company sets include "expected answers"
  for checking the assistant.
- **DATA-DATA-003 — Assistant instructions.** The written system prompts that define how each of the three
  assistant roles behaves.

## DATA-OPS — Tools, packaging, and tests

- **DATA-OPS-001 — Data downloaders.** A script that fetches the four Austin datasets (renaming columns to
  the expected names) and generators for the synthetic company data and the prepared Austin demo project.
- **DATA-OPS-002 — Plug-in launchers & checker.** Scripts that start the plug-in (MCP) server on Windows via
  WSL, a wrapper for the git-kb tool, and a self-check that confirms the plug-in server is healthy without
  any special setup.
- **DATA-OPS-003 — Packaging & deployment.** The container recipe (which installs the git-kb tool) and the
  hosting configuration for both halves of the project.
- **DATA-OPS-004 — Claude Code skill.** A documented add-on that teaches an AI assistant how to use the
  DataRoot plug-in safely (bounded queries, attribution required, no personal data).
- **DATA-OPS-005 — Automated tests.** Two test suites: one for the DataRoot pipeline (storage, linking, Miro
  drawing, the plug-in server) and one for DFDMaker that verifies the code-repo analyzer produces a valid
  project from trustworthy facts only, the SQL importer reads scripts correctly (with a "round trip" check
  that re-exports what it imported), and old project files still open.
