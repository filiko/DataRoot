# GitKB Before/After Comparison Report

**Date:** 2026-05-16
**Legacy KB:** `.kb.legacy-20260516-133107`
**Fresh KB:** `.kb`
**Context:** Legacy KB was incompatible with git-kb 0.2.6 (required upgrade/recovery). Fresh KB was created so git-kb + AgenticFlow could work. This report compares what changed — what improved, what was lost, and what should be migrated back.

---

## Executive Summary

| | Fresh KB | Legacy KB |
|---|---|---|
| **Files** | 16 | 3,207 |
| **Size** | 1.80 MB | 21.07 MB |
| **Markdown docs** | 4 (context placeholders only) | 1,860 |
| **Works for git-kb 0.2.6** | ✅ Yes (out of box) | ❌ No (requires upgrade) |
| **AgenticFlow MCP compatible** | ✅ Yes | ❌ No (wrong structure) |
| **Domain knowledge preserved** | ❌ No | ✅ Yes |
| **Context contract (immutable/extensible/overridable)** | ✅ Defined | ❌ Absent |

The reset traded ~21 MB of rich scientific domain knowledge for a clean, compatible, AgenticFlow-ready foundation. The trade was necessary — legacy couldn't be used without fixing — but significant knowledge was lost. A phased migration plan can recover the high-value parts.

---

## 1. Inventory Comparison

### 1.1 File Counts and Total Size

| Metric | Fresh KB | Legacy KB | Delta |
|--------|----------|-----------|-------|
| Total files | 16 | 3,207 | −3,191 |
| Total size | 1.80 MB | 21.07 MB | −19.27 MB |
| Markdown docs | 4 | 1,860 | −1,856 |
| Store/config files | ~12 | ~1,347 | ~−1,335 |

### 1.2 Section Structure Side-by-Side

```
FRESH KB workspaces/main/          LEGACY KB workspaces/main/
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
context/                          tables/          (79 docs)
  ├── immutable/                  columns/         (603 docs)
  │   ├── project-brief.md  [10l] row_groups/     (824 docs)
  │   └── architecture.md   [10l] source_files/  (47 docs)
  ├── extensible/                 candidates/      (184 docs)
  │   └── tech.md          [10l] measurements/   (122 docs)
  └── overridable/               workspaces/      (1 doc)
      └── active.md        [10l]
```

**[10l] = 10 lines — placeholder content only**

### 1.3 Legacy KB Section Breakdown

| Section | Docs | Domain Areas |
|---------|------|--------------|
| `row_groups/` | 824 | assays, bioreactor_ops, compounds, fermentation_runs, field_ops, harvest_logs, inquiries, inventory, lab_notes, protocols, registries, trials |
| `columns/` | 603 | Same 13 domains — per-column schema, type, nulls, uniqueness, PK/FK flags |
| `candidates/` | 184 | compounds (terpene synthases, FASTA-derived), inquiries, protocols, sequences |
| `tables/` | 79 | One doc per source table with schema, sample rows, column links |
| `measurements/` | 122 | Per-column statistics: min, max, mean, count |
| `source_files/` | 47 | Path, size, row count, file type per source file |
| `workspaces/` | 1 | Workspace configuration |

**13 domain areas:** `assays`, `bioreactor_ops`, `compounds`, `fermentation_runs`, `field_ops`, `harvest_logs`, `inquiries`, `inventory`, `lab_notes`, `protocols`, `registries`, `reports`, `sequences`, `trials`

---

## 2. Concrete Legacy Document Examples

### Example A — Table Document

**Path:** `workspaces/main/tables/assays/gcms_metabolite_assays_2026_q1.csv.md`

| Field | Value |
|-------|-------|
| **Title** | gcms_metabolite_assays_2026_q1.csv |
| **Type** | table |
| **Rows** | 36 |
| **Columns** | 12 (assay_id, run_id, strain_id, metabolite_id, measured_value, unit, method, pass_fail, notes + 3 None) |

**Content summary:** The document describes a GC-MS metabolite assay results table. It links to its source file and to all 12 column sub-documents. Five sample rows are embedded as JSON — the first shows assay `B-ASSAY-GCMS-010` from run `B-RUN-FERM-030`, strain `B-STR-YE-017`, metabolite `B-MET-EHEX` (ethyl hexanoate), measured at 28 mg/L with notes "Initial ester detection at bench scale."

**Why an agent needs this:** Without it, an agent has no way to know the table exists, what columns it has, or what its sample data looks like. It can't answer "what metabolites were measured?" or "which assays passed?"

**Fresh equivalent:** ❌ None. No table documents exist.

---

### Example B — Column Document

**Path:** `workspaces/main/columns/assays/gcms_metabolite_assays_2026_q1.csv/assay_id.md`

| Field | Value |
|-------|-------|
| **Title** | assay_id |
| **Type** | column |
| **Inferred type** | string |
| **Null %** | 0.0 |
| **Unique values** | 36 |
| **Likely PK** | ✅ true |
| **Likely FK** | ❌ false |

**Content summary:** Documents the `assay_id` column from the GC-MS assays table. Records inferred type (string), null percentage (0%), unique count (36). Flagged as likely primary key. Ten sample values show the naming pattern: `B-ASSAY-GCMS-010` through `B-ASSAY-GCMS-019`. Links to parent table and source file.

**Why an agent needs this:** An agent can correctly interpret assay IDs — they're the primary key, all present (no nulls), exactly 36 unique values. Without this, the agent sees raw CSV and must infer this itself.

**Fresh equivalent:** ❌ None.

---

### Example C — Row Group Document

**Path:** `workspaces/main/row_groups/assays/gcms_metabolite_assays_2026_q1.csv/b-assay-gcms-010.md`

| Field | Value |
|-------|-------|
| **Title** | B-ASSAY-GCMS-010 |
| **Type** | row_group |
| **Table** | gcms_metabolite_assays_2026_q1.csv |
| **Row index** | 1 |
| **Key column** | assay_id |
| **Key value** | B-ASSAY-GCMS-010 |

**Content summary:** Captures the complete provenance of a single assay row. The full row JSON is embedded: `run_id: B-RUN-FERM-030`, `strain_id: B-STR-YE-017`, `metabolite_id: B-MET-EHEX`, `measured_value: 28`, `unit: mg/L`, `method: GC-MS`, `pass_fail: pass`, `notes: "Initial ester detection at bench scale"`. Detected IDs extracted from the row: `B-MET-EHEX`, `B-RUN-FERM-030`, `B-STR-YE-017`, `GC-MS`.

**Why an agent needs this:** Enables traceability — "what did assay B-ASSAY-GCMS-010 actually show?" returns the full record. Also serves as stored evidence for claims. Without row groups, the agent must parse the raw CSV and find the row itself.

**Fresh equivalent:** ❌ None.

---

### Example D — Measurement Document

**Path:** `workspaces/main/measurements/assays/gcms_metabolite_assays_2026_q1.csv/measured_value.md`

| Field | Value |
|-------|-------|
| **Title** | measured_value |
| **Type** | measurement |
| **Inferred type** | int |
| **Count** | 36 |
| **Min** | 2.0 |
| **Max** | 410.0 |
| **Mean** | 61.9167 |

**Content summary:** Describes the `measured_value` measurement column from the metabolite assays table. Detected via column profiling. Values range from 2.0 to 410.0 mg/L with a mean of ~62. Sample values: `[11, 12, 14, 145, 18, 19, 2, 22, 24, 245]`. Links to parent table and column documents.

**Why an agent needs this:** Knows the statistical distribution of measured values without parsing CSV. Can answer "are measurements typically low or high?" or "are there outlier values?" instantly.

**Fresh equivalent:** ❌ None.

---

### Example E — Candidate Entity Document

**Path:** `workspaces/main/candidates/compounds/terpene_synthases.fasta/a-gen-tps-lim1.md`

| Field | Value |
|-------|-------|
| **Title** | A-GEN-TPS-LIM1 |
| **Type** | candidate_entity |
| **Source** | compounds/terpene_synthases.fasta |
| **Entity** | limonene synthase |
| **Organism** | Solanum lycopersicum |
| **Sequence length** | 345 aa |
| **Links** | UniProt:P83955, PMID:10472364 |

**Content summary:** Describes a candidate entity parsed from a FASTA header. The raw header was: `A-GEN-TPS-LIM1| limonene synthase| Solanum lycopersicum| 559 amino acids| produces limonene| uniprot:P83955| PMID:10472364`. Parsed into fields (id, entity, variant, length, product, uniprot, pmid). A 345-character sequence sample is included. Links to the source FASTA file.

**Why an agent needs this:** Supports compound/candidate discovery. An agent can answer "what is A-GEN-TPS-LIM1?" with biological context — it's a limonene synthase from tomato, produces the monoterpene limonene, has literature provenance. Without this, the agent sees a FASTA file with no domain context.

**Fresh equivalent:** ❌ None.

---

## 3. Fresh Context Documents — Full Analysis

### 3.1 `context/immutable/project-brief.md` (10 lines)

```
slug:     context/immutable/project-brief
title:   "Project Brief"
status:  draft
priority: medium
---
DataRoot is a local project managed by AgenticFlow.
Replace this seed with the product purpose, runtime model,
and non-negotiable constraints.
```

**What it provides:** A defined, structured slot with frontmatter (id, slug, title, type, status, priority). Establishes that a project brief must exist and should contain purpose, runtime model, constraints.

**What it is missing:** Everything. The body is a placeholder instruction, not actual project purpose, users, vision, or constraints.

**vs. legacy:** Legacy had no top-level project brief. Project identity was implicit in domain docs. The fresh version creates an explicit expectation — but someone must fill it.

---

### 3.2 `context/immutable/architecture.md` (10 lines)

```
slug:     context/immutable/architecture
title:   "Architecture"
status:  draft
priority: medium
---
Document the core architecture, data flow, ownership
boundaries, and places agents must inspect before
changing behavior.
```

**What it provides:** A slot for system architecture documentation with explicit guidance to document places agents must inspect before changing behavior.

**What it is missing:** No actual component inventory, data flow, integration points, or architecture decisions.

**vs. legacy:** Legacy had no architecture document. The data shape was documented (via tables/columns/row_groups) but not the code/system architecture.

---

### 3.3 `context/extensible/tech.md` (10 lines)

```
slug:     context/extensible/tech
title:   "Tech Context"
status:  draft
priority: medium
---
Document languages, frameworks, build commands, test
commands, deployment targets, and local environment
constraints.
```

**What it provides:** A slot for the complete technology stack — languages, frameworks, tooling, commands, deployment targets, environment constraints.

**What it is missing:** All actual tech stack details.

**vs. legacy:** Legacy had no technology context document at all.

---

### 3.4 `context/overridable/active.md` (10 lines)

```
slug:     context/overridable/active
title:   "Active Context"
status:  draft
priority: medium
---
Track current work, immediate plans, known blockers, and
task-specific context that can be updated frequently.
```

**What it provides:** A slot for ephemeral, frequently-updated context — current work, immediate plans, blockers, task-specific state.

**What it is missing:** All actual work-in-progress, focus areas, blockers.

**vs. legacy:** Legacy had no overridable context slot. Ongoing work was not explicitly tracked in a shareable document.

---

## 4. Side-by-Side: Fresh vs Legacy Equivalent

### 4.1 Project Context — Legacy (implicit) vs Fresh (explicit)

```
LEGACY KB — No project-brief equivalent.
  Project identity was distributed across domain docs.
  An agent had to infer "what is DataRoot?" from:
    - Table names (gcms_metabolite_assays, fermentation_runs...)
    - Column contexts (metabolite_id, measured_value...)
    - Source file paths (assays/, compounds/, etc.)
  There was no single document answering:
    "What is this project, what does it do, who is it for?"

FRESH KB — context/immutable/project-brief.md
  id: 019e327d-01cc-7913-90c0-d5572256ea85
  slug: context/immutable/project-brief
  title: "Project Brief"
  body: "DataRoot is a local project managed by
        AgenticFlow. Replace this seed..."

  ✅ Explicit slot exists and expects actual content
  ❌ Content is placeholder — must be filled manually
  ➡️ This is the RIGHT structure, wrong content
```

---

### 4.2 Table-Level Knowledge — Legacy (rich) vs Fresh (absent)

```
LEGACY KB — .kb.legacy/.../tables/assays/gcms_metabolite_assays_2026_q1.csv.md
  slug: tables/assays/gcms_metabolite_assays_2026_q1.csv
  row_count: 36, column_count: 12
  header_row: [assay_id, run_id, strain_id, metabolite_id,
               measured_value, unit, method, pass_fail, notes...]
  sample_rows: [B-ASSAY-GCMS-010: {measured_value: 28, unit: mg/L,
               metabolite_id: B-MET-EHEX, notes: "Initial ester detection..."}...]
  links: → source_file, → 12 column sub-docs

FRESH KB — (no equivalent)
  No table documents. No row counts. No column lists.
  No sample rows. No source file links.
  ➡️ An agent cannot discover what datasets exist via the KB.
     It must use filesystem search or external context.
```

---

### 4.3 Column Statistics — Legacy (rich) vs Fresh (absent)

```
LEGACY KB — .kb.legacy/.../columns/assays/.../assay_id.md
  inferred_type: string, null_pct: 0.0
  unique_count: 36, is_likely_pk: true, is_likely_fk: false
  sample_values: [B-ASSAY-GCMS-010, -011, -012, -013, -014...]

LEGACY KB — .kb.legacy/.../columns/assays/.../measured_value.md
  inferred_type: int, count: 36, min: 2.0, max: 410.0, mean: 61.9167
  detected_from: column_profile

FRESH KB — (no column docs exist)
  ➡️ An agent cannot ask "what is the range of measured_value?"
     or "is assay_id a primary key?" via the KB.
```

---

### 4.4 Row-Level Provenance — Legacy (rich) vs Fresh (absent)

```
LEGACY KB — .kb.legacy/.../row_groups/assays/.../b-assay-gcms-010.md
  row_data: {
    assay_id: B-ASSAY-GCMS-010,
    run_id: B-RUN-FERM-030,
    strain_id: B-STR-YE-017,
    metabolite_id: B-MET-EHEX,
    measured_value: 28, unit: mg/L, method: GC-MS,
    pass_fail: pass,
    notes: "Initial ester detection at bench scale"
  }
  detected_ids: [B-MET-EHEX, B-RUN-FERM-030, B-STR-YE-017, GC-MS]

FRESH KB — (no row_group docs exist)
  ➡️ "What did assay B-ASSAY-GCMS-010 show?" cannot be answered
     from the KB. Requires raw CSV access.
```

---

### 4.5 Context Stability Levels — Legacy (absent) vs Fresh (present)

```
LEGACY KB — No stability taxonomy.
  Documents were type: table, column, row_group, etc.
  No concept of "this doc changes often" vs "this doc is foundational."
  Context was implicitly distributed — agents had no contract
  to reason about.

FRESH KB — Three-tier stability model:
  immutable/   → Core truths, rare changes (project-brief, architecture)
  extensible/   → Evolving, can be extended (tech, product)
  overridable/  → Current state, changes frequently (active, progress)

  ✅ Agents can reason about what is stable vs volatile
  ✅ AgenticFlow MCP context injection maps directly to this structure
```

---

## 5. Improvements from the Reset

| # | Improvement | Detail |
|---|-------------|--------|
| 1 | **git-kb 0.2.6 works out of box** | Legacy required an upgrade/recovery step that failed or was not run. Fresh KB initializes and operates correctly with git-kb 0.2.6 and AgenticFlow MCP. |
| 2 | **AgenticFlow MCP context structure** | Fresh `context/immutable/` + `context/extensible/` + `context/overridable/` maps directly to how AgenticFlow injects context via MCP. Legacy's `tables/columns/row_groups/` structure was not designed for MCP context injection. |
| 3 | **Clean context contract with stability levels** | Fresh defines a clear, predictable context shape. Agents know what changes (overridable) vs what persists (immutable). Legacy had no such contract. |
| 4 | **No upgrade dependency or failure mode** | Legacy could fail on `git kb list` or MCP calls without recovery. Fresh eliminates that entire failure category. |
| 5 | **AGENTS.md with full code intelligence tools** | Fresh AGENTS.md includes `kb_symbols`, `kb_callers`, `kb_callees`, `kb_impact`, `kb_semantic`, `kb_dead_code`, `kb_smart_context`, `kb_index` — the complete code intelligence toolchain. Legacy AGENTS.md had partial coverage. |
| 6 | **Seven defined context document slots** | project-brief, patterns, architecture, product, tech, active, progress — a known interface. Legacy had no defined context interface; context was embedded in domain docs. |
| 7 | **Separation of concerns** | Fresh cleanly separates "eternal truths" (immutable), "evolving patterns" (extensible), and "current state" (overridable). Legacy mixed data records (row_groups, measurements) with documentation in the same namespace. |
| 8 | **Workspace discipline enforced** | Fresh AGENTS.md includes explicit multi-agent coordination rules: scoped commits with pathspecs, workspace ownership, context lock state machine. |

---

## 6. Regressions and Loss

| # | Regression | Detail |
|---|-------------|--------|
| 1 | **Table schema knowledge gone** | 79 table documents lost. An agent can't ask "what columns does `gcms_metabolite_assays` have?" via the KB. |
| 2 | **Column statistics gone** | 603 column documents with inferred types, null%, unique counts, PK/FK flags lost. Agents lose the ability to understand column semantics from the KB. |
| 3 | **Row-level provenance gone** | 824 row_group documents lost. Full record retrieval for specific assay/run/harvest events is impossible via the KB. |
| 4 | **Source file tracking gone** | 47 source_file documents lost. File inventory, sizes, row counts — all requiring filesystem access now. |
| 5 | **Candidate/protocol domain gone** | 184 candidate_entity documents lost. Compound discovery, sequence context, literature references — all gone. |
| 6 | **Measurement statistics gone** | 122 measurement documents with min/max/mean distributions lost. Agents can't know value ranges without parsing CSV. |
| 7 | **Cross-domain relationship graph lost** | Legacy had traversable chains: `table → columns → row_groups → source_file → measurements`. Agents could navigate domain knowledge. Fresh has no such navigation. |
| 8 | **13 domain categories absent** | assays, bioreactor_ops, compounds, fermentation_runs, field_ops, harvest_logs, inquiries, inventory, lab_notes, protocols, registries, reports, sequences, trials — the entire scientific domain map is gone. |
| 9 | **Data provenance evidence absent** | Legacy could answer "what evidence supports table X?" via row_group provenance docs. Fresh cannot. |
| 10 | **Agentic domain memory absent** | Agents cannot answer domain questions: "what metabolites were measured in fermentation run X?" or "what terpene synthase candidates exist?" — domain knowledge removed. |

---

## 7. Recommended Migration Plan

### Phase 1: Project Context Foundation *(Highest value, lowest risk)*

**Goal:** Fill the four fresh context slots with actual project knowledge.

1. **`context/immutable/project-brief.md`** — populate with:
   - Project purpose (what problem does DataRoot solve?)
   - Primary users/personas
   - Non-negotiable constraints
   - Foundational decisions already made

2. **`context/immutable/architecture.md`** — populate with:
   - Component inventory (what services/repos exist)
   - Data flow between components
   - Ownership boundaries
   - Key integration points
   - "Places agents must inspect before changing behavior"

3. **`context/extensible/tech.md`** — populate with:
   - Language, framework, tooling versions
   - Build/test/deploy commands
   - Local environment constraints
   - Project structure overview

4. **`context/overridable/active.md`** — populate with:
   - Current focus areas
   - Recent completions
   - Known blockers

**Why first:** These 4 docs have the highest leverage for general agent productivity. They establish the foundation without touching any domain data. Risk is low — filling placeholder docs doesn't break compatibility.

---

### Phase 2: Table/Source Metadata Migration *(High value, medium effort)*

**Goal:** Give agents a map of available data domains without migrating all 1,800+ individual docs.

1. **Create `context/extensible/data-domains.md`** summarizing all 13 domain areas:
   - For each domain: what it contains, key tables, estimated column/row counts, source file refs
   - Example: "assays/ — GC-MS and analytical assay results. Key tables: gcms_metabolite_assays_2026_q1.csv (36 rows, 12 cols). Source: assays/gcms_metabolite_assays_2026_q1.csv"

2. **Create a source file index** (`context/extensible/source-inventory.md`):
   - All 47 source files with path, type (CSV/FASTA), size, row count
   - Compact table format — one entry per source file

**Why second:** Phase 1 gives project identity; Phase 2 gives data map. Agents can now answer "what data do we have?" in aggregate.

---

### Phase 3: Selective Domain Detail Migration *(Lower priority, selective)*

**Goal:** Recover high-value domain details without overwhelming the fresh structure.

1. **Row group sampling** — pick top 10-20 most important row_group docs (e.g., key fermentation runs, key assay results) and create indexed summaries rather than migrating all 824 individually.

2. **Measurement summaries per table** — create one doc per table with column statistics:
   ```yaml
   gcms_metabolite_assays_2026_q1.csv:
     measured_value: {min: 2.0, max: 410.0, mean: 61.9, unit: mg/L}
     assay_id: {unique: 36, nulls: 0%, type: string}
   ```
   This replaces 122 individual measurement docs with ~79 compact summaries.

3. **Candidate entity index** — create `context/extensible/candidate-index.md` summarizing 184 candidate entities by category (compounds, protocols, sequences) rather than all individual docs.

**Why third:** Row groups and candidates are high-value but high-volume. Selective migration preserves access without flooding the fresh KB.

---

### Phase 4: Validation

After each phase:

```bash
# Confirm documents accessible
git kb list --json

# Confirm context structure works for AgenticFlow
git kb list --path context/

# Spot-check specific document retrieval
git kb show context/extensible/data-domains
git kb show tables/assays/gcms_metabolite_assays_2026_q1.csv

# Confirm cross-document linking works
git kb graph context/immutable/project-brief
```

---

## 8. Before/After Summary Table

| Aspect | Before (Legacy) | After (Fresh) | Verdict |
|--------|-----------------|---------------|---------|
| Total files | 3,207 | 16 | Regression |
| Total size | ~21 MB | ~1.8 MB | Regression |
| git-kb 0.2.6 compatibility | ❌ Requires upgrade | ✅ Out of box | Improvement |
| AgenticFlow MCP compatible | ❌ Wrong structure | ✅ 3-tier context | Improvement |
| Context stability contract | ❌ Absent | ✅ immutable/extensible/overridable | Improvement |
| Code intelligence tools | Partial | Full toolchain | Improvement |
| AGENTS.md workspace discipline | Partial | Full (context lock, scoped commits) | Improvement |
| Table documents | 79 | 0 | Regression |
| Column documents | 603 | 0 | Regression |
| Row group documents | 824 | 0 | Regression |
| Source file documents | 47 | 0 | Regression |
| Candidate documents | 184 | 0 | Regression |
| Measurement documents | 122 | 0 | Regression |
| Project context (explicit) | ❌ No | ✅ Placeholder exists | Partial |
| Architecture document | ❌ No | ✅ Placeholder exists | Partial |
| Tech context document | ❌ No | ✅ Placeholder exists | Partial |
| Active/overridable context | ❌ No | ✅ Placeholder exists | Partial |
| Domain navigation graph | ✅ Present | ❌ Absent | Regression |
| Data provenance evidence | ✅ Present (row_groups) | ❌ Absent | Regression |
| Column statistics (min/max/mean) | ✅ Present | ❌ Absent | Regression |
| 13 domain categories | ✅ All present | ❌ All absent | Regression |

---

## 9. Per-Dataset GitKB Derivability

This section shows what GitKB can derive from each DataRoot dataset — but only after DataRoot generates the knowledge docs. GitKB itself derives nothing from raw files.

---

### 9.1 CompanyA_AgriTrait

**Raw files:** 32 CSV, 9 MD, 5 JSON, 2 FASTA across 10 domain areas

| Domain | Key files |
|--------|-----------|
| compounds | compounds.csv, compounds_pubchem_enriched.csv, gene_catalog.csv, terpene_synthases.fasta |
| field_ops | field_blocks.csv, field_operations_log_2025.csv, soil_reports_2026.csv (+ 3 more) |
| harvest_logs | essential_oil_harvests.csv |
| inquiries | compound_blend_requests.json, customer_trait_requests.json, inquiry_log_with_pubchem_refs.csv |
| inventory | essential_oil_inventory.csv, seed_inventory.csv, seed_inventory_qc_records_2026.csv |
| lab_notes | lims_entries_2026_q1.csv |
| protocols | 6 LN-2026-xxxx.md protocol logs, protocol_registry.csv, protocol_parameters.csv |
| registries | cultivar_registry.csv, trait_ontology.csv, pedigree_crossing_records.csv (+ 6 more) |
| sequences | tomato_trait_markers.fasta, opencode.json |
| trials | field_trials_2025.csv, greenhouse_trials_2026_q1.csv (+ 2 more) |

**Legacy KB coverage:** ✅ Fully profiled — all 10 domains had table, column, row_group, measurement, source_file, and candidate docs generated.

**Current KB:** 5 hand-crafted demo docs (`gitkb-demo/companya-overview`, `structured-solara-14-answer`, etc.) — useful for search but not DataRoot-generated structure.

**After DataRoot re-profiles, GitKB enables:**

```bash
git kb search "Solara-14"          # finds cultivar row groups and provenance docs
git kb search "terpene synthase"   # finds candidate entities from FASTA headers
git kb show tables/registries/cultivar_registry.csv   # full table schema
git kb show columns/trials/greenhouse_trials_2026_q1.csv/cultivar_id
git kb graph tables/registries/cultivar_registry.csv  # traverse → columns → row_groups
```

**Agent questions unlocked:**
- "What cultivars are field_ready and have marker A-GEN-PMR3?"
- "What terpene synthase candidates exist and what organisms do they come from?"
- "Which greenhouse trials passed and what were the trait outcomes?"
- "What is the pedigree of Solara-14?"

---

### 9.2 CompanyB_Fermentation

**Raw files:** ~20 CSV, 1 JSON, 1 FASTA across 10 domain areas

| Domain | Key files |
|--------|-----------|
| assays | gcms_metabolite_assays_2026_q1.csv, gcms_raw_data_B-RUN-FERM-033_2026-03-26.csv |
| bioreactor_ops | bioreactor_schedule.csv |
| fermentation_runs | fermentation_runs_2026_q1.csv, ferm_run_log_B-RUN-FERM-033.csv, run_log_2024_q1–q4.csv |
| inquiries | product_profile_requests.json |
| inventory | strain_bank_inventory_Q1_2026.csv, strain_inventory.csv (+ 1 more) |
| lab_notes | lims_entries_2026_q1.csv |
| protocols | protocol_registry.csv, protocol_registry_live.csv, protocol_parameters.csv |
| registries | strain_registry.csv, metabolite_catalog.csv, media_formulation_catalog.csv (+ 4 more) |
| reports | qc_release_status.csv |
| sequences | strain_pathway_markers.fasta |

**Legacy KB coverage:** ✅ Fully profiled — all 10 domains had table, column, row_group, measurement, source_file, and candidate docs generated.

**Current KB:** ❌ No CompanyB docs in any active KB.

**After DataRoot re-profiles, GitKB enables:**

```bash
git kb search "B-ASSAY-GCMS"       # finds row_group docs for individual assay records
git kb search "ethyl hexanoate"    # finds metabolite rows and measurements
git kb show tables/assays/gcms_metabolite_assays_2026_q1.csv
git kb show measurements/assays/gcms_metabolite_assays_2026_q1.csv/measured_value
git kb graph tables/fermentation_runs/fermentation_runs_2026_q1.csv
```

**Agent questions unlocked:**
- "What metabolites were measured in fermentation run B-RUN-FERM-030?"
- "What is the GC-MS measured_value range across all assays?"
- "Which strains are in the bank inventory and what is their status?"
- "What media formulations were used in Q1 2026 runs?"

---

### 9.3 CompanyC_GeneticEngineering

**Raw files:** 4 CSV — all in `registries/`

| File | Content |
|------|---------|
| cell_line_registry.csv | Cell line IDs, parent lines, edit types, status |
| cell_line_registry_expanded.csv | Extended version of above |
| gene_target_catalog.csv | Gene target IDs, gene names, CRISPR context |
| guide_rna_library.csv | gRNA IDs, sequences, targets, efficiency scores |

**Legacy KB coverage:** ❌ Never profiled. CompanyC did not exist in the legacy KB.

**Current KB:** ❌ Nothing.

**After DataRoot profiles, GitKB enables:**

```bash
git kb search "CRISPR"             # finds gene target and gRNA docs
git kb show tables/registries/guide_rna_library.csv
git kb show columns/registries/guide_rna_library.csv/efficiency_score
git kb graph tables/registries/cell_line_registry.csv
```

**Agent questions unlocked:**
- "What cell lines are active and what edits do they carry?"
- "Which gRNAs target a given gene and what are their efficiency scores?"
- "What is the parent line of cell line C-CL-xxxx?"

---

### 9.4 AustinPermits

**Raw files:** 6 CSV — civic/municipal data

| Domain | Files |
|--------|-------|
| code_complaints | code_complaint_cases.csv, code_complaint_cases_may_2026.csv |
| code_tasks | code_task_list.csv |
| permits | construction_permits_2025_history.csv, issued_construction_permits.csv |
| reviews | plan_review_cases.csv |

**Legacy KB coverage:** ❌ Never profiled. Entirely new domain for DataRoot.

**Current KB:** ❌ Nothing.

**After DataRoot profiles, GitKB enables:**

```bash
git kb search "construction permit"   # finds table and row docs
git kb show tables/permits/issued_construction_permits.csv
git kb search "code complaint"        # finds complaint row groups
git kb graph tables/reviews/plan_review_cases.csv
```

**Agent questions unlocked:**
- "How many construction permits were issued in 2025?"
- "What is the status of plan review case #xxxx?"
- "What code complaints are open in May 2026?"

---

### 9.5 water_quality

**Raw files:** 4 CSV — environmental monitoring data

| File | Content |
|------|---------|
| standards.csv | Water quality regulatory standards by parameter |
| stations.csv | Monitoring station registry (IDs, locations) |
| water_quality_measurements_2024.csv | Measurement readings for 2024 |
| water_quality_measurements_expanded.csv | Extended measurements dataset |

**Legacy KB coverage:** ❌ Never profiled. Entirely new domain for DataRoot.

**Current KB:** ❌ Nothing.

**After DataRoot profiles, GitKB enables:**

```bash
git kb search "pH"                    # finds measurement rows and column stats
git kb show tables/water_quality_measurements_2024.csv
git kb show measurements/.../pH       # min/max/mean across station readings
git kb show tables/stations.csv
```

**Agent questions unlocked:**
- "Which stations had measurements above the regulatory standard for nitrates?"
- "What is the average pH across all stations in 2024?"
- "What parameters does the standards table define thresholds for?"

---

### 9.6 Summary: What GitKB Can Derive Per Dataset

| Dataset | Tables | Columns | Row Groups | Measurements | Candidates | Agent Usability |
|---------|--------|---------|------------|--------------|------------|-----------------|
| CompanyA | ~25 | ~200 | ~400 | ~50 | ~120 | Full domain graph |
| CompanyB | ~20 | ~150 | ~250 | ~70 | ~60 | Full domain graph |
| CompanyC | ~4 | ~20 | ~50 | ~5 | ~0 | Registry lookup |
| AustinPermits | ~6 | ~50 | ~100 | ~10 | ~0 | Civic record lookup |
| water_quality | ~4 | ~20 | ~200 | ~20 | ~0 | Station/measurement lookup |

*Row counts are estimates based on file count and type. Actual numbers depend on DataRoot profiling results.*

**Key point:** None of this exists in any active KB today. The legacy KB had CompanyA + CompanyB only. CompanyC, AustinPermits, and water_quality have never been ingested. Every row above depends on DataRoot running its profiling pipeline and writing compatible docs.

---

## Appendix: Raw Inventory Data

### Commands Used

```powershell
# Fresh KB
Get-ChildItem -LiteralPath .kb -Recurse -File | Measure-Object -Property Length -Sum

# Legacy KB
Get-ChildItem -LiteralPath .kb.legacy-20260516-133107 -Recurse -File | Measure-Object -Property Length -Sum

# Legacy section file counts
Get-ChildItem -LiteralPath .kb.legacy-20260516-133107\workspaces\main -Directory | ForEach-Object {
    $count = (Get-ChildItem -LiteralPath $_.FullName -Recurse -File | Measure-Object).Count
    [PSCustomObject]@{Section=$_.Name; Files=$count}
}

# Fresh KB sections
Get-ChildItem -LiteralPath .kb\workspaces\main -Directory
```

### Fresh KB Files (16 total, 1.80 MB)

```
.kb/workspaces/main/context/
  └── context/
      ├── extensible/tech.md           (10 lines — placeholder)
      └── immutable/
          ├── architecture.md          (10 lines — placeholder)
          └── project-brief.md          (10 lines — placeholder)
      └── overridable/
          └── active.md                (10 lines — placeholder)
(+ ~12 store/config files: AGENTS.md, store docs, etc.)
```

### Legacy KB Section Counts

| Section | Files |
|---------|-------|
| `row_groups/` | 824 |
| `columns/` | 603 |
| `candidates/` | 184 |
| `tables/` | 79 |
| `measurements/` | 122 |
| `source_files/` | 47 |
| `workspaces/` | 1 |
| **Total** | **1,860 markdown docs** |

### Legacy Domain Coverage

13 domain areas across all sections:
`assays`, `bioreactor_ops`, `compounds`, `fermentation_runs`, `field_ops`, `harvest_logs`, `inquiries`, `inventory`, `lab_notes`, `protocols`, `registries`, `reports`, `sequences`, `trials`

---

*Report generated: 2026-05-16*
*Fresh KB: `.kb` — 16 files, 1.80 MB, 4 context documents (placeholders)*
*Legacy KB: `.kb.legacy-20260516-133107` — 3,207 files, 21.07 MB, 1,860 markdown docs*