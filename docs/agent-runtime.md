---
purpose: How the three agent roles work, the runner, and the prompts.
prerequisites: CONTEXT.md, docs/architecture.md
read-when: Building the agent layer, writing prompts, understanding tool scoping.
---

# Agent runtime — docs/agent-runtime.md

How DataRoot's three agent roles work, the single runner, the
prompt structure, and failure-mode handling.

← Back to [CONTEXT.md](../CONTEXT.md)

## 4.0 Agent runtime architecture

DataRoot uses one model (Codex), one API client, and one agent
runner. The pipeline calls the runner three times with three
different configurations — these are the three "roles." Roles are
not separate services or plugins; they are system-prompt + tool-set
combinations passed to the same runner.

### Components

- `src/dataroot/agent/codex_client.py` — single Codex API wrapper.
  Owns the API key, request/response handling, retry logic.
- `src/dataroot/agent/runner.py` — single tool-calling loop.
  Signature: `run(system_prompt, tools, user_input) -> AgentResult`.
  Handles the message loop, tool dispatch, and structured output
  parsing. Harness-agnostic: tools are JSON schemas, not SDK objects.
- `src/dataroot/agent/prompts/` — one hand-authored markdown file
  per role. These are the agent's brain for each job.
- `src/dataroot/agent/tool_sets.py` — maps role name to the list of
  tool schemas that role is allowed to call. Roles are scoped: the
  Domain Spec Generator cannot write to the KB; the Query Agent
  cannot modify the domain spec.

### The three roles

**Role A — Domain Spec Generator.** Runs once per workspace, after
profile. Reads generic GitKB documents (workspace, source_file,
table, column, candidate_entity) and proposes a reviewable
`.dataroot/domain_spec.yaml`. Output is a YAML document; the human
reviews and edits before Stage 3 runs.

**Role B — Domain Spec Applier.** Runs once per workspace, after
the human accepts the domain spec. Walks KB documents and enriches
them with tags, labels, wikilinks, and domain-specific entity names
based on the spec. Mostly deterministic; Codex is invoked only for
fuzzy matches the deterministic linker can't resolve confidently.

**Role C — Query Agent.** Runs every time a user asks a question.
Decomposes the question, traverses the graph using the domain-
specific tools, recovers from missing data, and emits a cited
answer plus a structured provenance trace. This is the agent that
Agents Track judges will see in the demo.

### CLI entry points

- `dataroot infer-domain-spec` → Role A
- `dataroot apply-domain-spec` → Role B
- `dataroot ask "..."` → Role C

GitKB is not a role. GitKB is the document substrate the agent
calls into through the KBStore adapter. GitKB has no model and no
agency — it persists, searches, returns, commits, and traverses on demand.

## 4.2 Tools (role-annotated)

Each tool's JSON schema lives in `src/dataroot/agent/tool_sets.py`.
The role tag indicates which role(s) include the tool in their
allowed tool set. A tool used by multiple roles is defined once
and referenced by each role's tool list.

### GitKB-backed tools

Called through GitKBStore, which may use `git kb` CLI commands or
`git-kb mcp` under the hood. We do not re-implement GitKB's document
search/write/traversal behavior.

- `kb_search(query)` — FTS5 over all KB docs.
  Roles: A, C
- `kb_semantic(query, limit)` — vector search if enabled, else FTS fallback.
  Roles: C
- `kb_show(slug)` — full doc content with frontmatter.
  Roles: A, B, C
- `kb_list(type, status, tags, path)` — filtered list of docs.
  Roles: A, C
- `kb_graph(slug, direction, depth)` — graph traversal from a doc.
  Roles: C
- `kb_update(slug, content)` — write changes back to a KB doc.
  Roles: B only.

### DataRoot-specific tools

Thin wrappers over KB plus domain logic:

- `resolve_compound(query)` — natural language to compound slugs
  with confidence. Embedding lookup over compound flavor
  descriptors; FTS fallback.
  Roles: C
- `find_cultivars_producing(compound_slugs)` — given compounds,
  walks compound → gene → cultivar via kb_graph.
  Roles: C
- `check_inventory(cultivar_slug)` — "is this planted, where,
  when's harvest" by walking cultivar → planting → harvest.
  Roles: C
- `project_timeline(cultivar_slug, target)` — projects product
  availability based on planting/harvest state.
  Roles: C
- `render_provenance(trace, mode)` — renders provenance trace
  to Miro or Cytoscape. Mode is "miro" or "html".
  Roles: C
- `log_inquiry(question, answer, trace)` — writes the customer
  question, agent's answer, and provenance trace as a new KB doc
  of type `inquiry`.
  Roles: C

### Pipeline-level operations

Not agent tools — invoked from the CLI deterministically:

- `profile_workspace(path)` — Stage 1; deterministic Python.
- `infer_domain_spec(workspace)` — Stage 2; invokes Role A.
- `apply_domain_spec(spec)` — Stage 3; invokes Role B.

## 4.3 System prompt outlines

### Role A — Domain Spec Generator prompt

```
You are DataRoot's Domain Spec Generator. Your job is to read
generic KB documents produced by the workspace profiler and
propose a domain-specific specification.

You will read:
- One workspace doc
- Multiple source_file docs
- Multiple table docs
- Multiple column docs
- Any candidate_entity docs

Your output: a YAML file at .dataroot/domain_spec.yaml with:
- domain_name: short human-readable name
- entities: list of {name, description, maps_from (table/key_column or measure_columns)}
- relationships: list of {from, to, type, confidence, review_warnings}
- important_columns: list of columns that matter for the domain
- traversal_hints: natural language hints for how to traverse this domain
- aliases: column name aliases
- units: detected measurement units

Be conservative. If you're not confident about a relationship,
mark it with a warning. The human will review this before it goes
into the pipeline. Do not invent entities that aren't clearly
supported by the data.
```

### Role B — Domain Spec Applier prompt

```
You are DataRoot's Domain Spec Applier. Your job is to enrich
KB documents using an accepted domain spec.

You will read:
- .dataroot/domain_spec.yaml (the accepted spec)
- All existing KB docs

For each KB doc:
- Add domain-specific tags and labels based on the spec
- Add wikilinks for relationships defined in the spec
- Add aliases for columns that match the spec's column aliases
- Do NOT modify raw source files
- Do NOT fabricate relationships not in the spec

Call kb_update for docs that need changes. For fuzzy matches
that the deterministic linker couldn't resolve, use your best
judgment and mark confidence in the wikilink comment.
```

### Role C — Query Agent prompt

```
You are DataRoot, an agent that answers research-data questions
by traversing a knowledge graph of profiled artifacts.

Identity: DataRoot is a data-lineage agent that answers questions
by searching, traversing, and citing specific artifacts.

Domain primer: Read .dataroot/domain_spec.yaml first. It defines
the entities, relationships, aliases, units, important columns,
and traversal hints for this workspace. Follow its guidance.

Tool usage rules:
- Use kb_search and kb_graph to explore before making claims
- Use find_candidate_paths when the question implies a multi-hop traversal
- Use query_table to get specific rows
- Cite every factual claim with [citation: <slug>] referring to a KB doc
- If a path can't be found, say so explicitly — don't fabricate
- If the domain spec is missing or low-confidence, fall back to generic traversal
- If lineage is incomplete, explicitly note the gap

Output format:
- Streaming natural-language answer
- At the end, emit a <provenance> block with the structured trace

Failure modes:
- If a station/entity can't be resolved, say so and suggest alternatives
- If no results match the query, say so explicitly
- If data is missing for part of the traversal, note the gap explicitly
```

### Provenance block format

```xml
<provenance>
{
  "question": "...",
  "nodes": [
    {"id": "n1", "slug": "tables/water_quality", "label": "water_quality", "stage": "table"},
    ...
  ],
  "edges": [
    {"from": "n1", "to": "n2", "label": "has_column", "evidence": "water_quality → station_id"},
    ...
  ],
  "stages": ["query", "table", "column", "answer"]
}
</provenance>
```

← Back to [CONTEXT.md](../CONTEXT.md)
