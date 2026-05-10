# CompanyB — Fermentation / Microbial Strain Selection

> **Domain:** Microbial strain selection, fermentation runs, metabolite/compound assays, bioreactor scheduling, QC readiness
> **Demo Question:** "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?"

## Overview

CompanyB is a fermentation R&D company selecting microbial strains for flavor/aroma compound production. Their data is scattered across strain registries, metabolic pathway notes, FASTA files, fermentation run logs, GC-MS assay exports, media recipes, bioreactor schedules, QC records, and lab notebooks.

This dataset demonstrates DataRoot's ability to traverse from a product profile request → aroma profile ontology → target metabolites → pathway genes → strain registry → fermentation run evidence → GC-MS assay results → strain bank inventory → bioreactor scheduling → QC release status → scale-up timeline → final recommendation.

## Golden Path Entities

| Entity ID | Type | Description |
|-----------|------|-------------|
| B-INQ-001 | inquiry | Product team request: fruit-forward citrus ester, low temp, pilot scale, target 2026-05-15 |
| B-PROF-EST-01 | profile | Fruit-forward citrus ester profile |
| B-MET-EHEX | metabolite | Ethyl hexanoate — apple/pineapple/citrus |
| B-MET-EBUT | metabolite | Ethyl butyrate — pineapple/orange/sweet fruit |
| B-MET-EOCT | metabolite | Ethyl octanoate — orange peel/waxy/floral |
| B-GEN-AAT1 | pathway gene | Ester biosynthesis — produces EHEX and EBUT |
| B-GEN-EHT1 | pathway gene | Medium-chain ester biosynthesis — produces EOCT |
| B-STR-YE-017 | strain | Yeast EsterMax 17 — **PRIMARY CANDIDATE** |
| B-STR-YE-021 | strain | Yeast Citriflow 21 — bench validated, pilot pending |
| B-RUN-FERM-033 | fermentation run | 20L pilot run at 14°C, 96hr, completed |
| B-ASSAY-GCMS-018 | assay | EHEX: 42 mg/L (above target) |
| B-ASSAY-GCMS-019 | assay | EBUT: 31 mg/L (above target) |
| B-ASSAY-GCMS-020 | assay | EOCT: 18 mg/L (above target) |
| B-INV-STR-017 | strain inventory | 42 cryovials, 96% viability, released |
| B-BR-R2 | bioreactor | 50L, available 2026-04-28 to 2026-05-10 |
| B-QC-REL-005-008 | QC records | Contamination and identity checks passed |

## File Inventory

### Inquiries
- `inquiries/product_profile_requests.json` — 4 inquiries (B-INQ-001 through B-INQ-004)

### Registries
- `registries/product_profile_ontology.csv` — 6 profiles (B-PROF-*)
- `registries/metabolite_catalog.csv` — 30 metabolites (B-MET-*)
- `registries/pathway_gene_catalog.csv` — 22 pathway genes (B-GEN-*)
- `registries/strain_registry.csv` — 18 strains (B-STR-*)
- `registries/media_recipes.csv` — 8 media recipes (B-MEDIA-*)

### Sequences
- `sequences/strain_pathway_markers.fasta` — 20 FASTA entries with parseable headers

### Fermentation Data
- `fermentation_runs/fermentation_runs_2026_q1.csv` — 16 run records (B-RUN-FERM-030 through 045)
- `assays/gcms_metabolite_assays_2026_q1.csv` — 36 assay records (B-ASSAY-GCMS-010 through 045)

### Inventory & Operations
- `inventory/strain_inventory.csv` — 18 strain inventory records
- `bioreactor_ops/bioreactor_schedule.csv` — 12 bioreactor definitions (B-BR-R*)

### Protocols (4)
- `protocols/B-PROT-001_low_temp_fermentation.md`
- `protocols/B-PROT-002_gcms_ester_assay.md`
- `protocols/B-PROT-003_strain_identity_qc.md`
- `protocols/B-PROT-004_pilot_scaleup_review.md`

### Lab Notes (5)
- `lab_notes/2026-03-24_labnote_low_temp_ester_screen.md`
- `lab_notes/2026-04-08_labnote_strain_bank_viability.md`
- `lab_notes/2026-03-01_labnote_gcms_calibration.md`
- `lab_notes/2026-04-15_labnote_bioreactor_scheduling.md`
- `lab_notes/2026-04-28_labnote_q1_summary.md`

### Reports
- `reports/qc_release_status.csv` — 33 QC records (B-QC-REL-001 through 033)

### Expected Answers & Provenance
- `expected_answers/B-INQ-001_expected_answer.md`
- `provenance_targets/B-INQ-001_trace.json`

## Known Edge Cases / Missing Data

| Entity | Issue | Impact |
|--------|-------|--------|
| B-STR-YE-021 | No pilot-scale run completed; B-QC-REL-011 scaleup_review pending | On hold_scaleup; cannot recommend for immediate scale |
| B-INV-STR-028 | 86% viability — below 90% release threshold | Vanilla strain on hold_early_stage |
| B-INV-STR-025 | 88% viability — borderline | Floral strain on hold_early_stage pending review |
| B-STR-YE-018 | Produces banana ester (B-PROF-BANANA-04), not citrus | Wrong profile for B-INQ-001 |
| B-INQ-004 | No strain fully satisfies banana/tropical profile | Partial candidates only |
| B-BR-R7 | Under maintenance until late April | Temporarily unavailable |
| B-RUN-FERM-044 | Currently ongoing at 50L in B-BR-R2 | Must clear before B-BR-R2 can be booked for B-INQ-001 scale-up |

## Demo Answer Summary

**Primary recommendation:** Schedule **B-STR-YE-017 (Yeast EsterMax 17)** for pilot scale-up in B-BR-R2.

- Pathway genes confirmed: B-GEN-AAT1 (ester biosynthesis) + B-GEN-EHT1 (medium-chain ester)
- Target metabolites above threshold: EHEX 42 + EBUT 31 + EOCT 18 = 91 mg/L combined (≥ 85 mg/L threshold)
- Low off-note: diacetyl at 3 mg/L (≤ 5 mg/L threshold)
- 20L pilot run completed (B-RUN-FERM-033) at 14°C following B-PROT-001
- All QC checks passed (B-QC-REL-005 through 008), strain released
- Strain bank available: 42 cryovials at 96% viability (B-INV-STR-017)
- Bioreactor B-BR-R2 available 2026-04-28 to 2026-05-10: harvest by ~2026-05-02, QC by 2026-05-04
- **Timeline fits target_ready_by of 2026-05-15 with buffer**

**Secondary candidate:** B-STR-YE-021 (Yeast Citriflow 21) — bench validated with good ester output (EHEX 38, EBUT 27 mg/L) but no pilot run yet. On hold pending scale-up review.

**Not sufficient for this inquiry:** B-STR-YE-018 (Yeast BananaFlow 18) — produces isoamyl acetate (banana/pear ester profile), not the citrus ester profile requested.

## Usage

```bash
dataroot ingest ExampleData/CompanyB_Fermentation/raw
dataroot link
dataroot ask "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?"
```