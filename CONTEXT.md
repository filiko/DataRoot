# DataRoot — CONTEXT.md

---
purpose: Master context file for DataRoot.
read-when: Every session start. For depth on any topic, follow the link.
---

Read this entire document before writing code. For depth on any topic,
follow the link to the referenced doc in `docs/`. When something
contradicts an earlier section, the later section wins. When something
is ambiguous, ask the human. Do not invent.

## 0. TL;DR

DataRoot is a data-lineage agent that turns an arbitrary folder of
heterogeneous files into a queryable provenance graph.

It works in four stages:

1. **Profile** — scan a folder, produce generic KB document records (source_file, table,
   column, row_group, candidate_entity, measurement, relationship).
2. **Infer Domain Spec** — Role A proposes `.dataroot/domain_spec.yaml`
   (entities, relationships, aliases, units, traversal hints). Human reviews.
3. **Apply Domain Spec** — Role B enriches KB docs with domain tags, labels,
   wikilinks. No raw files modified.
4. **Answer + Provenance** — Role C traverses the graph, returns a cited
   answer with a structured provenance trace. Optional Miro rendering (Tier 2).

The lab/research demo is the polished hackathon story. A water-quality
smoke-test dataset proves the architecture is generic.

Differentiator: every other RAG demo answers a question. DataRoot returns
a question plus a provenance graph the researcher uses to design the next
experiment.

→ See `docs/architecture.md` for full problem statement and scope.

## 1. Why this exists

Research orgs have data scattered across spreadsheets, sequence files,
compound DBs, protocols, instrument exports, field logs, and inquiry records.
Answering "do we have anything that can do X" requires traversing all of
these. Today it takes three teams and two weeks. The work is mechanical,
lookup-heavy, and exactly what an agent should do.

→ See `docs/architecture.md` §1 for full context.

## 2. Scope

### Tier 1 (must work)

- Generic workspace profiler: CSV, XLSX, JSON, Markdown/text, FASTA.
- Generic KB document records: workspace, source_file, table, column, row_group,
  candidate_entity, measurement, relationship, domain_spec, inquiry,
  provenance_trace.
- KBStore adapter: GitKBStore first + LocalMarkdownStore fallback only.
- Generic linker: file→table, table→column, likely PK/FK, repeated IDs,
  date/time, geo/location, measurement/unit, text mentions.
- `dataroot infer-domain-spec` → Role A, human reviews output.
- `dataroot apply-domain-spec` → Role B.
- `dataroot link` → deterministic wikilink inference.
- `dataroot ask "..."` → Role C, streaming answer + provenance JSON.
- Lab/research demo pack + water_quality smoke-test.

### Tier 2 (cut if behind)

- Miro REST renderer (Tier 2, not Tier 1).
- Cytoscape/HTML fallback.
- Web UI.

### Out of scope

- Perfect arbitrary dataset understanding.
- Production OAuth, multi-user auth.
- Live external datastore integrations.
- Full Miro MCP integration.
- Mirage integration.
- Production-grade ontology extraction.

→ See `docs/architecture.md` §2 for tier breakdown and full list.

## 3. Architecture overview

```
Raw Folder / ExampleData
        ↓
DataRoot Workspace Profiler
        ↓
Generic KB Document Records (source_file, table, column, row_group,
                 candidate_entity, measurement, relationship)
        ↓
GitKB / KBStore
        ↓
Domain Spec Generator Agent (Role A)
        ↓
Reviewable .dataroot/domain_spec.yaml
        ↓
Apply Domain Spec (Role B)
        ↓
Enriched KB Graph
        ↓
Query Agent (Role C)
        ↓
Cited Answer + Provenance JSON + Inquiry Log
        ↓
Optional Miro Board
```

**KBStore backends:** DataRoot talks to persistence through a small
`read/search/write/update/commit` adapter. GitKBStore is preferred and
implements those methods with `git kb` / `git-kb mcp` commands. The
science/domain pipeline never writes repository docs directly. A
LocalMarkdownStore remains only as a demo fallback if GitKB is unavailable.
Backend selected in `.dataroot/config.toml`. Tier 1 should target GitKB first.

**Data model summary:** Two layers. Layer 1 = raw source files (never
modified). Layer 2 = KB docs (generic types from profiling; domain types
after apply-domain).

**Project layout:**

```
dataroot/
├── CONTEXT.md                  # this file
├── docs/                      # topic depth files
├── src/dataroot/
│   ├── kb/                    # KBStore backends
│   ├── profile/               # workspace profiler + parsers
│   ├── link/                  # FK inference + wikilinks
│   ├── agent/
│   │   ├── codex_client.py    # single API wrapper
│   │   ├── runner.py          # single tool-calling loop
│   │   ├── tool_sets.py       # role → tool schema mapping
│   │   └── prompts/           # one .md per role
│   └── render/                # miro.py, cytoscape.py
├── ExampleData/
│   ├── water_quality/         # smoke-test
│   ├── CompanyA_AgriTrait/     # lab demo
│   └── CompanyB_Fermentation/
└── tests/
    └── test_demo_spine.py     # A-CUL-TOM-014 invariant check
```

→ See `docs/architecture.md` for full layout and .env.example contents.

## 4. Agent runtime

### 4.0 Architecture

DataRoot uses **one model (Codex), one API client, one runner**. The
pipeline calls the runner three times with three different configurations
— these are the three "roles." Roles are not separate services; they are
system-prompt + tool-set combinations passed to the same runner.

**Components:**
- `src/dataroot/agent/codex_client.py` — single Codex API wrapper. Owns
  API key, request/response, retry logic.
- `src/dataroot/agent/runner.py` — single tool-calling loop. Signature:
  `run(system_prompt, tools, user_input) -> AgentResult`. Harness-agnostic:
  tools are JSON schemas, not SDK objects.
- `src/dataroot/agent/prompts/` — one hand-authored markdown file per role.
- `src/dataroot/agent/tool_sets.py` — maps role name to allowed tool schemas.
  Roles are scoped: Role A cannot write to KB; Role C cannot modify domain spec.

**The three roles:**

| Role | Name | Runs | Output |
|------|------|------|--------|
| A | Domain Spec Generator | Once per workspace, after profile | `.dataroot/domain_spec.yaml` (human reviews) |
| B | Domain Spec Applier | Once per workspace, after spec accepted | Enriched KB docs |
| C | Query Agent | Every user question | Cited answer + provenance trace |

**CLI:** `dataroot infer-domain-spec` → A | `dataroot apply-domain-spec` → B | `dataroot ask "..."` → C

GitKB is not a role. GitKB is the document substrate the agent calls
via MCP/CLI through the KBStore adapter. GitKB has no model and no agency —
it persists, searches, returns, commits, and traverses on demand.

→ See `docs/agent-runtime.md` for full prompt structure, role-by-role
behavior specs, and failure-mode handling.

### 4.2 Tools (role-annotated)

Each tool's JSON schema lives in `src/dataroot/agent/tool_sets.py`.
Role tag shows which roles include the tool.

**GitKB tools** (called through the GitKBStore adapter; not re-implemented):

- `kb_search(query)` — FTS5 over KB docs. Roles: A, C
- `kb_semantic(query, limit)` — vector search or FTS fallback. Roles: C
- `kb_show(slug)` — full doc with frontmatter. Roles: A, B, C
- `kb_list(type, status, tags, path)` — filtered doc list. Roles: A, C
- `kb_graph(slug, direction, depth)` — graph traversal. Roles: C
- `kb_update(slug, content)` — write back to KB. Roles: B only

**DataRoot-specific tools:**

- `resolve_compound(query)` — natural language → compound slugs. Roles: C
- `find_cultivars_producing(compound_slugs)` — walks compound→gene→cultivar. Roles: C
- `check_inventory(cultivar_slug)` — planted/where/harvest. Roles: C
- `project_timeline(cultivar_slug, target)` — projects availability. Roles: C
- `render_provenance(trace, mode)` — renders trace to Miro or HTML. Roles: C
- `log_inquiry(question, answer, trace)` — writes inquiry KB doc. Roles: C

**Pipeline operations** (not agent tools — CLI deterministic):

- `profile_workspace(path)` — Stage 1.
- `infer_domain_spec(workspace)` — Stage 2, invokes Role A.
- `apply_domain_spec(spec)` — Stage 3, invokes Role B.

→ See `docs/agent-runtime.md` for full tool schemas and Role A/B/C prompts.

## 5. Traversal pattern (memorize this)

**Water-quality smoke test** ("Which stations exceeded nitrate limits in 2024?"):

```
[Query] "nitrate limits exceeded"
    │ kb_search("nitrate")
    ▼
[Tables] water_quality_measurements
    │ query_table(..., filters=[nitrate_mg_l > 10])
    ▼
[Rows] matching station_ids with high nitrate
    │ kb_graph to stations
    ▼
[Stations] names and locations
    │
    ▼
[Answer] cited response + provenance JSON + inquiry doc
```

**Lab/research demo** (CompanyA) follows the same generic pipeline.
The domain spec maps generic types to domain names. The traversal
pattern is identical; only the entity names change.

## 6. Synthetic dataset

Three datasets in `ExampleData/`:

1. **water_quality/** — EPA-style CSV, 12 stations, 200 rows. Smoke-test.
2. **CompanyA_AgriTrait/** — polished lab demo, agricultural trait data.
3. **CompanyB_Fermentation/** — same structure, fermentation domain.

**Demo spine invariant (CompanyA):**

```
A-CUL-TOM-014 appears in cultivar registry
A-CUL-TOM-014 has trait A-TRT-DRT (drought tolerance)
A-CUL-TOM-014 has marker A-GEN-PMR3 (powdery mildew resistance)
A-CUL-TOM-014 appears in greenhouse trials
A-CUL-TOM-014 appears in field trials
A-CUL-TOM-014 appears in seed inventory
A-CUL-TOM-014 appears in field readiness
A-CUL-TOM-022 appears and has a failure reason
```

This chain must hold. Write `test_demo_spine.py` to assert it.
If it breaks, the demo fails.

→ See `docs/synthetic-dataset.md` for column-level specs.

## 7. Miro renderer

Miro is a **renderer**, not the provenance itself. REST-first
(Authorization: Bearer token from .env). Swimlane layout, one
frame per stage. Only frames, shapes, sticky notes, connectors.
Cytoscape fallback if Miro fails.

`dataroot miro <provenance_slug>` is Tier 2, not Tier 1.

→ See `docs/miro-renderer.md` for layout math, payload shapes, OAuth.

## 8. Build plan summary

~30 hours. Hour 0-2: foundation + KBStore. Hour 2-8: profiler +
linking. Hour 11-18: Domain Spec Generator + apply-domain + query agent.
Hour 22-26: demo data + spine test. Hour 26-28: Tier 2.
Hour 28-30: buffer + demo polish.

Cut order if behind: Web UI → Miro → Tier 3 → Tier 2 features.
Always protect: profiler, linker, Domain Spec Generator, query agent.

→ See `docs/build-plan.md` for hour-by-hour.

## 9. Risks and demo invariants

1. **Demo spine must hold.** A-CUL-TOM-014 chain (above). Run `pytest
   tests/test_demo_spine.py` before the hackathon.
2. **Pin model + temperature.** Save a known-good transcript as backup.
3. **Pre-warm Miro board night before.** Test Cytoscape fallback path.
4. **Test on actual demo laptop, on demo network.** Pin every dependency.
5. **Generic profiler must pass on water_quality first.** If it breaks,
   fix before adding CompanyA features.

## 10. For the agent reading this

- Read this entire file. Don't skim.
- Follow links to `docs/` only when working on that topic.
- Test the water-quality smoke test at every checkpoint.
- Test the demo spine invariant at every checkpoint.
- DataRoot must not hardcode CompanyA/CompanyB, cultivar, compound,
  gene, strain, ferm_run, or assay into core traversal logic. Those
  are demo domain-pack labels only.
- When in doubt, look at §2 scope. If something isn't in Tier 1, don't
  build it until Tier 1 works.
- Ask the human before deciding anything that affects demo viability.

End of CONTEXT.md.
