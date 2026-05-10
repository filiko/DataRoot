# DataRoot — Hackathon Submission

**Pitch.** Point DataRoot at a folder of heterogeneous files (CSV, JSON,
FASTA, Markdown — including real public datasets), and it ingests them
into a GitKB-backed provenance graph, links them by repeated IDs and
normalized addresses, and exposes a Live Ask agent that answers any
question with cited evidence rendered as a Miro board.

Same project, two tracks.

---

## Tracks targeted

### Agents Track

DataRoot's Live Ask is an autonomous, tool-using agent — not a chatbot
wrapper. The behavior is concentrated in `src/dataroot/agent/`:

- A single tool-calling loop (`runner.py`) the model drives end-to-end.
- Nine tools (`tools.py`, schemas in `tool_sets.py`) — search, graph
  traversal, table query, candidate-path discovery, KB read/write,
  inquiry logging, Miro render.
- Three role-scoped tool allowlists (Domain Spec Generator, Domain Spec
  Applier, Query Agent) — the model can't escape its scope.
- Two real external-system effects per turn: write `inquiries/<timestamp>`
  + provenance trace into GitKB, and call the Miro REST API to render the
  trace as an interactive board.
- Deterministic fallback for every LLM-driven layer
  (`render/interpretation.py`, `render/miro_plan.py`, `query.py`) — the
  agent degrades gracefully if `OPENAI_API_KEY` is missing or the model
  errors.

Reference: [`docs/agent-runtime.md`](docs/agent-runtime.md).

### Brainforge / Vicinity Texas Open Data Track

Same pipeline, pointed at four real City of Austin public datasets, with
both technical artifacts the track explicitly rewards:

- **MCP server** — `src/dataroot/mcp/server.py`. Stdio MCP, eight bounded
  tools, hard caps (50 / 100 / 200 / depth-3), GitKB-only. Reference:
  [`docs/mcp-server.md`](docs/mcp-server.md).
- **Claude Code skill** — `skills/dataroot-texas/SKILL.md`. Documents the
  tool surface, safe-use rules, and question shapes the workspace handles
  well. No canned answers — the user supplies arbitrary prompts.

Datasets (City of Austin / Austin Development Services public data, used
under the [City of Austin Open Data Terms](https://data.austintexas.gov/stories/s/ranj-cccq)):

| Slug          | Title                         |
|---------------|-------------------------------|
| `3syk-w9eu`   | Issued Construction Permits   |
| `n8ck-xkda`   | Plan Review Cases             |
| `6wtj-zbtb`   | Austin Code Complaint Cases   |
| `ttd7-isgm`   | Austin Code Task List         |

Per-dataset URLs, fetch parameters, SoQL filters, and column renames
applied at fetch time are recorded in
[`ExampleData/AustinPermits/SOURCES.md`](ExampleData/AustinPermits/SOURCES.md).

---

## What the agent does autonomously

Given a free-form question against a workspace, the Query Agent:

1. **Decomposes** the question against the domain spec
   (`.dataroot/domain_spec.yaml`) — entities, relationships, traversal hints.
2. **Plans a multi-hop traversal** by choosing among `kb_search`,
   `kb_graph`, `query_table`, `find_candidate_paths`, and `kb_show` in
   whatever order the question demands.
3. **Recovers from gaps** — when a path can't be resolved, the prompt
   forces an explicit "lineage gap" admission and the deterministic
   fallback in `query.py` produces a cited answer anyway.
4. **Persists** an `inquiries/<timestamp>` doc and a structured
   provenance trace into GitKB.
5. **Renders** the trace to a Miro board via REST: claim cards labeled by
   source dataset, citation badges, an optional precise-proof frame.

---

## Technical artifacts

| Artifact                | Path                                                                   |
|-------------------------|------------------------------------------------------------------------|
| MCP server (stdio)      | [`src/dataroot/mcp/server.py`](src/dataroot/mcp/server.py)             |
| MCP API reference       | [`docs/mcp-server.md`](docs/mcp-server.md)                             |
| Claude Code skill       | [`skills/dataroot-texas/SKILL.md`](skills/dataroot-texas/SKILL.md)     |
| Agent loop              | [`src/dataroot/agent/runner.py`](src/dataroot/agent/runner.py)         |
| Tool dispatch           | [`src/dataroot/agent/tools.py`](src/dataroot/agent/tools.py)           |
| Per-role tool allowlists | [`src/dataroot/agent/tool_sets.py`](src/dataroot/agent/tool_sets.py)  |
| Address normalizer      | [`src/dataroot/link/address_match.py`](src/dataroot/link/address_match.py) |
| Austin downloader       | [`scripts/fetch_austin.py`](scripts/fetch_austin.py)                   |
| Austin attribution      | [`ExampleData/AustinPermits/SOURCES.md`](ExampleData/AustinPermits/SOURCES.md) |
| Hosted-deploy guide     | [`docs/deploy.md`](docs/deploy.md)                                     |

---

## Reproducibility

A judge cloning the repo can reach a working Live Ask in five steps. All
require `git-kb` on `PATH` (Linux/macOS native; Windows via WSL —
`https://github.com/gitkb/gitkb-releases`).

```bash
git clone <this repo> dataroot && cd dataroot
pip install -e .

# Texas Open Data path
git kb --version
python scripts/fetch_austin.py
export DATAROOT_LINK_ADDRESS_JOIN=1
dataroot profile ExampleData/AustinPermits/raw
dataroot link
uvicorn dataroot.server.app:app --host 0.0.0.0 --port 8000
# open http://localhost:8000/miro/, pick "Austin Permits Explorer"

# Agents Track path
dataroot profile ExampleData/CompanyA_AgriTrait/raw
dataroot link
dataroot ask "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"

# MCP server (with git-kb available)
dataroot mcp                       # native CLI
python -m dataroot.mcp             # equivalent module entry point
bash scripts/start-mcp.sh          # WSL launcher used by Codex / Claude Code
```

Test suite + MCP verification:

```bash
pytest                                   # 77 tests pass; GitKB-gated MCP test skips cleanly when git-kb is absent
python scripts/verify_mcp.py             # 8 in-process JSON-RPC checks against the MCP server
```

`scripts/verify_mcp.py` builds the server, exercises `tools/list` and
`tools/call` through the same handlers an external client would use, and
prints a pass/fail matrix — handy when you don't want to wire a stdio
client just to confirm the server is healthy.

---

## Live demo links

> _Update with the demo URLs before submission._

- Hosted Live Ask (Railway): `https://<railway-domain>/miro/`
- Recorded walkthrough: `<video URL>`
- Shared Miro demo board: `https://miro.com/app/board/<id>/`

---

## License

[Apache 2.0](LICENSE).
