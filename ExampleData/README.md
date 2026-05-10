# ExampleData — Synthetic Demo Dataset for DataRoot

> **Purpose:** This folder contains fully synthetic research data for demonstrating DataRoot's multi-hop traversal, provenance tracking, and operational decision-making capabilities across two different research domains.

## Overview

DataRoot is a research-data agent that traverses heterogeneous research artifacts (spreadsheets, FASTA files, protocols, lab notebooks) to answer domain-level questions with file-level provenance. This dataset lets us prove that the same traversal mechanics work across:

1. **CompanyA** — Agricultural / Crop Trait Selection (tomato breeding)
2. **CompanyB** — Fermentation / Microbial Strain Selection (yeast and Lactobacillus)

## Quick Start

```bash
# Ingest CompanyA data
dataroot ingest ExampleData/CompanyA_AgriTrait/raw
dataroot link
dataroot ask "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"

# Ingest CompanyB data
dataroot ingest ExampleData/CompanyB_Fermentation/raw
dataroot link
dataroot ask "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?"
```

## Dataset Characteristics

Both companies feature:

- **Heterogeneous file types**: CSV, XLSX, FASTA, JSON, Markdown
- **Internally consistent cross-links**: IDs appear in 2–4 files each
- **Golden path candidates**: one strong candidate + one partial candidate per demo question
- **Realistic missingness**: gaps the agent must reason around
- **Messy-but-believable lab data**: genuine research artifacts that haven't been sanitized

## File Inventory

### CompanyA (Agricultural)

```
CompanyA_AgriTrait/
├── raw/
│   ├── inquiries/          # customer trait requests (JSON)
│   ├── registries/        # trait ontology, marker catalog, cultivar registry
│   ├── sequences/          # FASTA files with marker headers
│   ├── trials/             # greenhouse and field trial CSVs
│   ├── inventory/          # seed inventory
│   ├── field_ops/          # field block definitions
│   ├── protocols/          # assay and genotyping protocols (Markdown)
│   ├── lab_notes/          # messy researcher notes (Markdown)
│   └── reports/            # soil analysis reports (Markdown)
├── expected_answers/       # regression-test golden answers
└── provenance_targets/    # expected node/edge graph structure
```

### CompanyB (Fermentation)

```
CompanyB_Fermentation/
├── raw/
│   ├── inquiries/          # product profile requests (JSON)
│   ├── registries/        # profile ontology, metabolite catalog, pathway genes, strain registry, media recipes
│   ├── sequences/          # FASTA files with strain/pathway markers
│   ├── fermentation_runs/  # run-level logs (CSV)
│   ├── assays/             # GC-MS metabolite assay results (CSV)
│   ├── inventory/          # strain cryobank inventory (CSV)
│   ├── bioreactor_ops/      # bioreactor scheduling (CSV)
│   ├── protocols/          # fermentation, assay, QC, scale-up protocols (Markdown)
│   ├── lab_notes/          # messy researcher notes (Markdown)
│   └── reports/            # QC release records (CSV)
├── expected_answers/       # regression-test golden answers
└── provenance_targets/    # expected node/edge graph structure
```

## Demo Questions

### CompanyA Demo Question

> "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"

**Golden path:** Inquiry → Traits (DRT + PMR) → Markers (DRT2 + PMR3) → Cultivar (Solara-14) → Greenhouse trials → Field trial → Seed inventory → Field block readiness → Answer

**Primary candidate:** A-CUL-TOM-014 (Solara-14) — field_ready with both markers, passed greenhouse and field trials, released inventory
**Partial candidate:** A-CUL-TOM-022 (DryShield-22) — has both markers, greenhouse validated, but field trial incomplete
**Insufficient:** A-CUL-TOM-031 (Arida-31) — drought only, lacks PMR marker

### CompanyB Demo Question

> "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?"

**Golden path:** Inquiry → Profile → Metabolites (EHEX + EBUT + EOCT) → Pathway genes (AAT1 + EHT1) → Strain (EsterMax 17) → Fermentation run → Assay results → Strain inventory → Bioreactor availability → QC release → Answer

**Primary candidate:** B-STR-YE-017 (Yeast EsterMax 17) — pilot_ready with full ester profile at 91 mg/L combined, 20L pilot completed, released inventory, B-BR-R2 available
**Partial candidate:** B-STR-YE-021 (Yeast Citriflow 21) — bench validated with good ester output, but no pilot run yet
**Insufficient:** B-STR-YE-018 (Yeast BananaFlow 18) — banana ester profile (B-PROF-BANANA-04), wrong profile for this inquiry

## Expected Graph Shape

### CompanyA Provenance Graph

```
A-INQ-001
  → A-TRT-DRT + A-TRT-PMR
  → A-GEN-DRT2 + A-GEN-PMR3
  → A-CUL-TOM-014
  → A-TRL-GH-* + A-TRL-FD-011
  → A-INV-SEED-04
  → A-FLD-BLOCK-3
  → final answer
```

### CompanyB Provenance Graph

```
B-INQ-001
  → B-PROF-EST-01
  → B-MET-EHEX + B-MET-EBUT + B-MET-EOCT
  → B-GEN-AAT1 + B-GEN-EHT1
  → B-STR-YE-017
  → B-RUN-FERM-033
  → B-ASSAY-GCMS-019/020/021
  → B-INV-STR-017
  → B-BR-R2
  → B-QC-REL-007/008
  → final answer
```

## Intentionally Included Gaps

DataRoot must reason around these partial matches:

| Company | Gap | Impact |
|---------|-----|--------|
| A | A-CUL-TOM-022 has markers + GH validation but no clean field trial | Cannot fully recommend; on hold |
| A | A-CUL-TOM-031 has drought marker but no PMR marker | Only suitable for drought-only inquiries |
| A | Some field blocks have "planned" status not yet "ready" | Limits deployment options |
| B | B-STR-YE-021 has good ester output at bench but no pilot run | Cannot recommend for immediate scale-up |
| B | B-INV-STR-028 (vanilla strain) below viability threshold | Early-stage hold status |
| B | Banana ester profile (B-PROF-BANANA-04) has no full candidate | Inquiry B-INQ-004 has no sufficient answer |

## Data Conventions

- IDs follow the pattern `X-ENT-XXX` (e.g., `A-CUL-TOM-014`, `B-STR-YE-017`)
- FASTA headers are pipe-delimited and parseable: `>{gene_id}|{entity_id}|...|confidence={score}`
- Markdown files include YAML frontmatter with `protocol_id` or relevant metadata
- Lab notes contain messy prose but explicitly mention entity IDs for linking
- All CSV files use consistent column headers

## Files Generated

Total: 50+ files across both companies
- CSVs: 20+
- JSON: 2 (inquiries)
- FASTA: 2
- Markdown protocols: 8
- Markdown lab notes: 10
- Markdown reports: 1
- Expected answers: 2
- Provenance traces: 2

## Notes

- All data is **entirely synthetic** — no real company, person, strain, or cultivar names
- IDs are designed to be consistent across files for reliable cross-referencing
- The "correct" answer for each demo question is documented in `expected_answers/`
- The provenance trace structure is documented in `provenance_targets/`

## License

Synthetic demo data for DataRoot project — safe for hackathon use and public publication.