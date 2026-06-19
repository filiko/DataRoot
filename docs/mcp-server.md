# DataRoot MCP server

The DataRoot stdio MCP server (`src/dataroot/mcp/server.py`) wraps the
existing `ToolExecutor` (`src/dataroot/agent/tools.py`) with a small set of
**bounded, well-scoped tools** that an external agent can use to explore a
DataRoot workspace, answer questions, and persist provenance traces.

Server name: `dataroot-texas`. Default workspace: `austin_permits`.

## Launch

```bash
dataroot mcp                       # via the CLI
python -m dataroot.mcp             # equivalent module entry
bash scripts/start-mcp.sh          # WSL launcher used by Codex / Claude Code
```

The server speaks the MCP stdio transport (JSON-RPC over stdin/stdout).
Connect any MCP-compatible client — Claude Code, the `mcp` CLI, a custom
runner — and call `tools/list` to discover the tool surface.

`scripts/start-mcp.sh` is the supported launcher when an MCP client on
Windows reaches into WSL (Codex, Claude Code's MCP integration). It
activates the WSL virtualenv, sources `.env`, exports
`DATAROOT_LINK_ADDRESS_JOIN=1` and `PYTHONPATH=src`, and `exec`s the
module entry. Keep any wrapper silent on stdout — anything printed
before the MCP handshake corrupts JSON-RPC framing.

## GitKB requirement

The server **fails to start** if `git-kb` is not on `PATH`:

```
DataRoot MCP server failed to start: git-kb CLI is not available on PATH.
The DataRoot MCP server requires the real GitKB backend
(https://github.com/gitkb/gitkb-releases). On Windows install via WSL per
the project README.
```

There is no LocalMarkdownStore fallback. This is intentional: every
DataRoot artifact in production is sourced from real GitKB, and silent
fallbacks have caused production / mock divergence in the past.

## Hard caps

Every tool clamps its result size silently. A caller may ask for more, but
the server returns at most the cap. The clamped value and the cap are
included in the response so the caller can detect truncation.

| Tool                | Cap                                |
|---------------------|------------------------------------|
| `kb_search`         | 50 hits                            |
| `kb_list`           | 100 records                        |
| `query_table`       | 200 rows                           |
| `kb_graph`          | depth 3                            |
| `kb_show`           | 1 record (no cap needed)           |
| `summarize_workspace` | n/a (returns counts only)        |
| `list_datasets`     | n/a (workspace count is small)     |
| `ask`               | n/a (caps come from underlying tools) |

## Workspaces

The server resolves a workspace from the `workspace` argument on every tool
(default: `austin_permits`). Aliases are accepted — e.g. `"austin"`,
`"permits"`, `"texas"`, `"opendata"` all map to `austin_permits`. The full
alias map lives in `src/dataroot/server/app.py`.

Available workspaces:

| Key              | Label                       | Raw data                                 |
|------------------|-----------------------------|------------------------------------------|
| `austin_permits` | Austin Permits Explorer     | `ExampleData/AustinPermits/raw`          |
| `company_a`      | CropProtectorAI             | `ExampleData/CompanyA_AgriTrait/raw`     |
| `company_b`      | BioReactorAI                | `ExampleData/CompanyB_Fermentation/raw`  |

Use `list_datasets` first if the user has not named a workspace.

## Tools

### `list_datasets`

**Purpose.** Discovery — list every workspace registered in DataRoot, with
raw-data paths.

**Input.**

```json
{ "type": "object", "properties": {}, "additionalProperties": false }
```

**Output.**

```json
{
  "workspaces": [
    { "key": "austin_permits", "label": "Austin Permits Explorer", "raw_path": "ExampleData/AustinPermits/raw" },
    { "key": "company_a",      "label": "CropProtectorAI",         "raw_path": "ExampleData/CompanyA_AgriTrait/raw" },
    { "key": "company_b",      "label": "BioReactorAI",             "raw_path": "ExampleData/CompanyB_Fermentation/raw" }
  ],
  "default": "austin_permits"
}
```

**Errors.** None expected — the workspace registry is in-process.

---

### `summarize_workspace`

**Purpose.** Summary — counts of KB records by `doc_type` for a workspace.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string", "description": "Workspace key (default 'austin_permits')." }
  },
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "label": "Austin Permits Explorer",
  "raw_path": "ExampleData/AustinPermits/raw",
  "record_count": 1284,
  "by_type": {
    "source_file": 4,
    "table": 4,
    "column": 92,
    "row_group": 1100,
    "relationship": 84
  },
  "attribution": "City of Austin Open Data Terms — https://data.austintexas.gov/stories/s/ranj-cccq"
}
```

**Errors.** Unknown workspace key → `{"error": "unknown workspace ...", "tool": "summarize_workspace"}`.

---

### `kb_search`

**Purpose.** Bounded full-text search over KB documents. Hard cap: 50 results.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string" },
    "query":     { "type": "string", "description": "Search query." },
    "limit":     { "type": "integer", "description": "Max results (capped at 50)." }
  },
  "required": ["query"],
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "limit": 50,
  "cap": 50,
  "results": [
    { "slug": "row_groups/permits/issued_construction_permits.csv/2025-1234567-bp", "doc_type": "row_group", "score": 4.2, "title": "2025-1234567 BP", "snippet": "..." }
  ]
}
```

**Errors.** Unknown workspace; missing `query` → schema validation error.

---

### `kb_list`

**Purpose.** Bounded enumeration of KB documents by type or path prefix.
Hard cap: 100 records.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string" },
    "type":      { "type": "string", "description": "Document type filter (e.g. 'table', 'row_group')." },
    "path":      { "type": "string", "description": "Slug path prefix filter." },
    "limit":     { "type": "integer", "description": "Max results (capped at 100)." }
  },
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "limit": 100,
  "cap": 100,
  "truncated": true,
  "records": [
    { "slug": "tables/permits/issued_construction_permits.csv", "type": "table", "title": "issued_construction_permits.csv" }
  ]
}
```

`truncated` is `true` when the underlying list exceeded the cap.

---

### `kb_show`

**Purpose.** Fetch a single KB record (frontmatter + body) by slug.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string" },
    "slug":      { "type": "string", "description": "Document slug." }
  },
  "required": ["slug"],
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "record": {
    "frontmatter": { "doc_type": "row_group", "table": "...", "row_data": { ... } },
    "body": "# 2025-1234567 BP\n..."
  }
}
```

**Errors.** Slug not in KB → underlying `ToolExecutor` raises and the
server returns `{"error": "...", "tool": "kb_show"}`.

---

### `query_table`

**Purpose.** Bounded row query against a profiled table. Hard cap: 200 rows.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace":  { "type": "string" },
    "table_slug": { "type": "string", "description": "Slug of the table record." },
    "filters":    { "type": "array", "items": {"type": "object"}, "description": "List of {column, op, value} clauses." },
    "limit":      { "type": "integer", "description": "Max rows (capped at 200)." }
  },
  "required": ["table_slug"],
  "additionalProperties": false
}
```

Filter clause shape (matches `dataroot.query_tools.query_table`):

```json
{ "column": "status", "op": "==", "value": "Active" }
```

Supported ops: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `in`.

**Output.**

```json
{
  "workspace": "austin_permits",
  "limit": 200,
  "cap": 200,
  "rows": [
    { "permit_id": "2025-1234567 BP", "status": "Active", "address": "1623 S LAMAR BLVD", "...": "..." }
  ]
}
```

---

### `kb_graph`

**Purpose.** Connected subgraph of a KB record. Hard cap: depth 3.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string" },
    "slug":      { "type": "string", "description": "Document slug to traverse from." },
    "direction": { "type": "string", "enum": ["both", "in", "out"], "description": "Edge direction (default 'both')." },
    "depth":     { "type": "integer", "description": "Traversal depth (capped at 3)." }
  },
  "required": ["slug"],
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "depth": 3,
  "cap": 3,
  "graph": {
    "nodes": ["row_groups/permits/.../bp", "relationships/address__1623_s_lamar_blvd"],
    "edges": [{ "source": "row_groups/...", "target": "relationships/address__1623_s_lamar_blvd", "label": "shares address" }]
  }
}
```

---

### `ask`

**Purpose.** Answer a free-form question against a workspace and return the
clean answer plus persisted inquiry/provenance trace metadata.

**Input.**

```json
{
  "type": "object",
  "properties": {
    "workspace": { "type": "string" },
    "question":  { "type": "string", "description": "Free-form question about the workspace." },
    "use_agent": { "type": "boolean", "description": "Use the OpenAI-backed agent path instead of deterministic fallback." }
  },
  "required": ["question"],
  "additionalProperties": false
}
```

**Output.**

```json
{
  "workspace": "austin_permits",
  "question": "What's happening at 1623 S Lamar?",
  "answer": "PMR3 and PMR4 support the PMR trait.",
  "inquiry": "inquiries/20260510123045",
  "provenance_trace": "provenance_traces/20260510123045",
  "node_count": 7,
  "edge_count": 9,
  "stages": ["query", "retrieval", "evidence_path", "answer"],
  "trace": { "nodes": [], "edges": [], "stages": [] },
  "answer_source": "deterministic_fallback",
  "use_agent": false
}
```

**How it composes.** `ask` reuses the FastAPI app's live-ask helpers so the
MCP response matches the HTTP `/api/ask` response shape for answer and
provenance data. The wiring is:

1. Wrap the cached `GitKBStore` handle in a `CompanyWorkspace` and call
   `dataroot.server.app._answer_live_ask`.
2. If the agent's structured trace is missing or malformed, fall back to
   `dataroot.query._extract_provenance(answer)`.
3. Persist the inquiry + provenance via
   `dataroot.query.persist_answer_artifacts`.
4. Strip the embedded `<provenance>` block from the answer text using
   `dataroot.server.app._strip_provenance` before returning.

**Source-field meanings.**

| Field           | Values                            | Meaning                              |
|-----------------|-----------------------------------|--------------------------------------|
| `answer_source` | `agent`, `deterministic_fallback` | Which path produced the answer text. |
| `use_agent`     | `true`, `false`                   | Whether the caller requested the OpenAI-backed agent path. |

**Errors.**

- `OPENAI_API_KEY` or model provider credentials are required only when
  `use_agent` is true. Deterministic fallback remains available without
  external model credentials.
- Question yields no provenance → returns an answer string explaining the
  retrieval failure; no exception is raised.

## Calling the server

A minimal `tools/call` JSON-RPC request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "kb_search",
    "arguments": { "workspace": "austin_permits", "query": "1623 S Lamar", "limit": 10 }
  }
}
```

The response wraps a `TextContent` whose `text` is the JSON-encoded payload
above. Errors are surfaced the same way — the server never crashes a
client connection on a per-call exception.

## Reusing as a library

The server is composable. To embed it in tests or a different transport:

```python
from dataroot.mcp.server import build_server, _dispatch

server = build_server()                              # returns a configured mcp.Server
result = _dispatch("kb_search", {"query": "permit"}) # call dispatch directly, bypass the transport
```

`tests/test_mcp_server.py` uses this pattern to exercise the dispatch layer
without binding a stdio client.

## Verifying the server

Run the bundled in-process verifier:

```bash
PYTHONPATH=src python scripts/verify_mcp.py
```

The script builds the server, calls its registered `list_tools` and
`call_tool` handlers through the same entry points an external client
would use, and prints an 8-row pass/fail matrix covering tool descriptors,
`list_datasets`, the unknown-tool error path, `summarize_workspace`,
`kb_search` / `kb_graph` cap clamping, and the git-kb-missing failure
mode. It runs without a real `git-kb` install (uses an in-memory
`LocalMarkdownStore` for the workspace-dependent checks); the production
server still requires real GitKB.

## Related

- Skill that documents safe-use rules and example invocations:
  `skills/dataroot-texas/SKILL.md`
- Underlying tool dispatch: `src/dataroot/agent/tools.py`
- Address normalizer used by `query_table` filters: `src/dataroot/link/address_match.py`
- Workspace registration: `src/dataroot/server/app.py` (`COMPANIES`, `COMPANY_ALIASES`)
- Dataset attribution: `ExampleData/AustinPermits/SOURCES.md`
