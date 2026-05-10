# CompanyA — Agricultural / Crop Trait Selection

> **Domain:** Crop breeding, trait selection, genotyping, greenhouse trials, field readiness, seed inventory
> **Demo Question:** "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"

## Overview

CompanyA is an agricultural R&D company developing tomato cultivars for climate resilience and disease resistance. Their data is scattered across breeding registries, genotyping files, greenhouse trial exports, seed inventory spreadsheets, field operations logs, and lab notebooks.

This dataset demonstrates DataRoot's ability to traverse from a customer trait request → trait ontology → gene/marker catalog → cultivar registry → genotyping evidence → greenhouse trials → field trials → seed inventory → field deployment readiness → final recommendation.

## Golden Path Entities

| Entity ID | Type | Description |
|-----------|------|-------------|
| A-INQ-001 | inquiry | Customer request: drought + PMR tolerance for tomato, spring planting |
| A-TRT-DRT | trait | Drought tolerance |
| A-TRT-PMR | trait | Powdery mildew resistance |
| A-GEN-DRT2 | gene/marker | Drought response marker 2 |
| A-GEN-PMR3 | gene/marker | Powdery mildew resistance marker 3 |
| A-CUL-TOM-014 | cultivar | Solara-14 — **PRIMARY CANDIDATE** |
| A-CUL-TOM-022 | cultivar | DryShield-22 — partial, field pending |
| A-CUL-TOM-031 | cultivar | Arida-31 — drought only, no PMR |
| A-TRL-GH-001-008 | greenhouse trial | Greenhouse validation for A-CUL-TOM-014 and A-CUL-TOM-022 |
| A-TRL-FD-002 | field trial | Field trial in A-FLD-BLOCK-3, 2025-Fall, passed |
| A-INV-SEED-02 | seed inventory | 2,400 units, 94% germ, released |
| A-FLD-BLOCK-3 | field block | Texas Zone 8, ready, 1,200 m², window 2026-04-20 to 2026-05-18 |

## File Inventory

### Inquiries
- `inquiries/customer_trait_requests.json` — 4 inquiries (A-INQ-001 through A-INQ-004)

### Registries
- `registries/trait_ontology.csv` — 12 traits (A-TRT-*)
- `registries/marker_gene_catalog.csv` — 20 markers (A-GEN-*)
- `registries/cultivar_registry.csv` — 18 cultivars (A-CUL-*)

### Sequences
- `sequences/tomato_trait_markers.fasta` — 20 FASTA entries with parseable headers

### Trials
- `trials/greenhouse_trials_2026_q1.csv` — 30 greenhouse trial records
- `trials/field_trials_2025.csv` — 20 field trial records

### Inventory & Operations
- `inventory/seed_inventory.csv` — 20 seed inventory records
- `field_ops/field_blocks.csv` — 14 field block definitions

### Protocols (4)
- `protocols/A-PROT-001_drought_drydown_assay.md`
- `protocols/A-PROT-002_powdery_mildew_challenge.md`
- `protocols/A-PROT-003_marker_genotyping.md`
- `protocols/A-PROT-004_field_readiness_review.md`

### Lab Notes (5)
- `lab_notes/2026-03-18_labnote_pmr_review.md`
- `lab_notes/2026-03-22_labnote_drought_field_inspection.md`
- `lab_notes/2026-04-04_labnote_seed_qc.md`
- `lab_notes/2026-02-10_labnote_genotyping_batch.md`
- `lab_notes/2026-04-10_labnote_q1_summary.md`

### Reports
- `reports/soil_report_A-FLD-BLOCK-3.md` — soil analysis for field block 3

### Expected Answers & Provenance
- `expected_answers/A-INQ-001_expected_answer.md`
- `provenance_targets/A-INQ-001_trace.json`

## Known Edge Cases / Missing Data

| Entity | Issue | Impact |
|--------|-------|--------|
| A-CUL-TOM-022 | Field trial A-TRL-FD-008 showed unexpected PMR susceptibility | On hold pending retest; not field_ready |
| A-CUL-TOM-031 | Missing PMR marker (A-GEN-PMR3) | Only suitable for drought-only inquiries |
| A-FLD-BLOCK-7 | Small block with inconclusive results | Retesting of A-CUL-TOM-022 delayed |
| A-CUL-TOM-027 | Triple drought marker line | Early stage; field trial cancelled |
| A-INV-SEED-17 | Germination 84% below threshold | On hold_early_stage |
| A-TRL-FD-017 | Field trial cancelled due to weather | A-CUL-TOM-024 PMR data incomplete |

## Demo Answer Summary

**Primary recommendation:** Deploy **A-CUL-TOM-014 (Solara-14)** for the spring planting request.

- Both target markers confirmed (A-GEN-DRT2, A-GEN-PMR3)
- Greenhouse validation passed for both traits
- Field trial A-TRL-FD-002 passed in Texas Zone 8 (2025-Fall)
- Released seed inventory (A-INV-SEED-02): 2,400 units at 94% germination
- Field block A-FLD-BLOCK-3: 1,200 m², ready, window 2026-04-20 to 2026-05-18

**Secondary candidate:** A-CUL-TOM-022 (DryShield-22) — has both markers and greenhouse validation but field validation is incomplete.

**Not sufficient for this inquiry:** A-CUL-TOM-031 (Arida-31) — drought-only, lacks PMR package.

## Usage

```bash
dataroot ingest ExampleData/CompanyA_AgriTrait/raw
dataroot link
dataroot ask "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"
```