---
name: dataroot-texas
description: Use when a user wants to explore Austin (or other Texas) public-data slices via DataRoot's MCP server and render the answer on a Miro provenance board. Activates when the question is about Austin building permits, plan reviews, code complaints, or code enforcement tasks.
---

# DataRoot Texas Open Data

This skill lets an agent query the DataRoot Live Ask pipeline against bounded
slices of City of Austin open data and render the answer as a Miro provenance
board. It is purpose-built for the Brainforge / Vicinity Texas Open Data
Track, but the same skill works against any other workspace DataRoot has
profiled (CompanyA, CompanyB, etc.).

## What this skill does

The user types any free-form question about an Austin workspace. DataRoot's
MCP server calls into the existing pipeline (`profile` → `link` →
`answer_question` → `interpret` → `miro_plan` → `render_provenance_to_miro`)
and returns:

- A natural-language answer
- A Miro board URL with evidence cards labeled by source dataset slug
- The full provenance trace (nodes, edges, source rows)

The skill is generic — there are no canned questions or stored answers. The
user supplies the prompt, the workspace supplies the data, the renderer draws
the graph.

## MCP server

Server name: `dataroot-texas`. Launch over stdio (any of the three works):

```
dataroot mcp                       # native CLI
python -m dataroot.mcp             # equivalent module entry
bash scripts/start-mcp.sh          # WSL launcher used by Codex / Claude Code
```

Requires `git-kb` on `PATH` (https://github.com/gitkb/gitkb-releases). On
Windows, install via WSL per the top-level `README.md`. The server refuses to
start if `git-kb` is unavailable — there is no LocalMarkdownStore fallback.

`scripts/start-mcp.sh` is the supported entry when an MCP client running
on Windows reaches into WSL: it activates the WSL virtualenv, sources
`.env`, exports `DATAROOT_LINK_ADDRESS_JOIN=1`, and execs the server. Keep
any wrapper silent on stdout — anything printed before the MCP handshake
corrupts JSON-RPC framing.

To sanity-check the server without binding a stdio client, run the
in-process verifier:

```
PYTHONPATH=src python scripts/verify_mcp.py
```

It exercises `tools/list` and `tools/call` through the same handlers an
external client would use and prints an 8-row pass/fail matrix. Works
without a real `git-kb` install.

## Tools available (with bound limits)

| Tool                  | Purpose                                             | Hard cap                  |
|-----------------------|-----------------------------------------------------|---------------------------|
| `list_datasets`       | Discovery — list every workspace                    | n/a                       |
| `summarize_workspace` | Counts of KB records by `doc_type`                  | n/a                       |
| `kb_search`           | Bounded full-text search                            | 50 results                |
| `kb_list`             | Enumerate by type or path prefix                    | 100 records               |
| `kb_show`             | Fetch one record (frontmatter + body)               | 1 record                  |
| `query_table`         | Filtered row query against a profiled table        | 200 rows                  |
| `kb_graph`            | Connected subgraph traversal                        | depth 3                   |
| `ask_and_render`      | Answer a question + render the Miro board          | n/a (caps via dependents) |

Every tool accepts an optional `workspace` argument (default
`"austin_permits"`, also accepts `"company_a"` / `"company_b"`). Use
`list_datasets` first if the user hasn't named a workspace.

## Datasets in the `austin_permits` workspace

Four bounded Socrata slices from `data.austintexas.gov` — see
`ExampleData/AustinPermits/SOURCES.md` for slugs, URLs, fetch dates, SoQL
filters, and attribution.

| Slug          | Title                         | Linking key       |
|---------------|-------------------------------|-------------------|
| `3syk-w9eu`   | Issued Construction Permits   | `permit_id`       |
| `n8ck-xkda`   | Plan Review Cases             | `permit_id`       |
| `6wtj-zbtb`   | Austin Code Complaint Cases   | `case_task_id`    |
| `ttd7-isgm`   | Austin Code Task List         | `case_task_id`    |

Cross-table address joins use a heuristic normalizer (`address_key` —
uppercase, no punctuation, USPS-style suffixes, unit trailers stripped). Treat
address-derived links as fuzzy matches, not exact identity.

## Question shapes the workspace handles well

- **Single-permit lookup.** "What is the status of permit 2025-123456?"
- **Address lookup.** "What's happening at 1623 S Lamar?"
- **Multi-hop traversal between datasets.** Plan review status → matching
  issued permits, or active complaints → matching open code tasks. The user
  is asking the system to *infer* the right entity by chaining evidence
  across datasets, not just look up an ID.
- **Status / aggregation slices.** "How many BP permits are still active in
  78704?" (`query_table` on `3syk-w9eu` with status / zip filters.)

These are illustrative shapes, not stored prompts — the renderer does not
have canned answers.

## Safe-use rules

- All four datasets are City of Austin public open data, used under the
  **City of Austin Open Data Terms** —
  `https://data.austintexas.gov/stories/s/ranj-cccq`. Cite the dataset slug
  whenever a specific row's fields are surfaced to the user.
- **Bounded queries only.** Each tool clamps to the cap above; don't try to
  work around the cap by chaining many calls. If a query genuinely needs more
  than 200 rows, propose narrowing the filter to the user instead.
- **Don't claim address joins are exact.** If two records share an
  `address_key`, say "these records appear to share an address" and let the
  user inspect both rows.
- **Never query for personally identifying owner data.** The slices used here
  omit owner PII; do not attempt to reconstruct it from other public sources.
- **Surface uncertainty.** If `query.answer_question` returns a low-confidence
  trace, say so in the answer the user sees.

## Example invocation flow

1. `list_datasets` — show the user what workspaces exist.
2. `summarize_workspace` (workspace=`austin_permits`) — confirm the four
   datasets are profiled with reasonable record counts.
3. `ask_and_render` — pass the user's free-form question, return the answer
   and the Miro board URL.

If the user wants to drill into a specific source row before deciding, route
through `kb_search` → `kb_show`, or `query_table` for filtered slices.

## References

- **Full MCP API reference (per-tool schemas, examples, errors):** `docs/mcp-server.md`
- **Hackathon submission overview:** `SUBMISSION.md`
- **Glossary (MCP / Live Ask / `address_key` / hard cap definitions):** `docs/glossary.md`
- MCP server implementation: `src/dataroot/mcp/server.py`
- WSL launcher used by Codex / Claude Code: `scripts/start-mcp.sh`
- In-process verifier: `scripts/verify_mcp.py`
- Underlying tool dispatch: `src/dataroot/agent/tools.py`
- Address normalizer: `src/dataroot/link/address_match.py`
- Workspace registration: `src/dataroot/server/app.py` (`COMPANIES` dict)
- Dataset attribution and SoQL filters: `ExampleData/AustinPermits/SOURCES.md`
- Agent loop (Agents Track angle): `docs/agent-runtime.md`
- Renderer behavior contract: `docs/miro-fundamental-functionality.md`
