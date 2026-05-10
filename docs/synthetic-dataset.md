---
purpose: Specs for the demo datasets.
prerequisites: CONTEXT.md, docs/architecture.md §8
read-when: Generating synthetic data, checking dataset consistency.
---

# Synthetic dataset — docs/synthetic-dataset.md

Column-level specs for the demo datasets. The dataset has to be just
real enough to make the demo land. Use any LLM to generate in ~1 hour.

← Back to [CONTEXT.md](../CONTEXT.md)

## Dataset overview

Three datasets:

1. **water_quality/** — EPA-style water quality CSV for smoke-test.
2. **CompanyA_AgriTrait/** — polished lab/research demo, agricultural trait data.
3. **CompanyB_Fermentation/** — same structure as CompanyA, fermentation domain.

CompanyA/CompanyB are not the core architecture. They are demo domain
packs. The water_quality dataset proves the generic profiler works.

## Demo spine (CompanyA invariant)

The following must hold for CompanyA_AgriTrait:

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

This is the demo spine. If it breaks, the demo fails. Write a
pytest invariant check for this.

## water_quality/ (smoke-test)

### water_quality.csv (~200 rows)

Columns: station_id, sample_date, nitrate_mg_l, lead_ppb, ph, dissolved_oxygen_mg_l, temperature_c, e_coli_mpn

- 12 stations (STATION_001 through STATION_012)
- Dates spanning 2023-2024
- Nitrate: 0.5–15 mg/L (some exceeding 10 mg/L limit)
- Lead: 0.1–15 ppb (some exceeding 15 ppb action level)
- STATION_001, STATION_003, STATION_007 have exceedances in 2024
- e_coli: 1–1000 MPN

### stations.csv (12 rows)

Columns: station_id, name, lat, lon, watershed, status

- STATION_001: Riverside Park, 40.7128, -74.0060, Hudson River, active
- STATION_002: Depot Creek, 40.7282, -73.7949, Long Island Sound, active
- ...etc

Cross-reference: station_id in water_quality.csv → station_id in stations.csv.

## CompanyA_AgriTrait/

### cultivars.xlsx (15 rows)

Columns: id, name, parent_id, target_compound_ids, flavor_descriptors, field_status, notes

- id examples: A-CUL-TOM-014, A-CUL-TOM-022, A-CUL-PEP-008
- Mix of citrus, floral, herbal, woody profiles
- ~5 planted, ~5 in seed inventory, ~5 in concept stage
- A-CUL-TOM-014: drought-tolerant, mildew-resistant, planted, field-ready
- A-CUL-TOM-022: similar markers, but has field validation hold / failure reason noted

### compounds.csv (~50 rows)

Columns: id, name, iupac, family (monoterpene/sesquiterpene), flavor_descriptors, produced_by_genes, boiling_point_c, cas_number

- Cover: limonene, linalool, citral, pinene, myrcene, geraniol, eugenol, etc.
- flavor_descriptors: citrus, floral, herbal, woody, minty, cooling, etc.
- produced_by_genes: TPS-LIM, TPS-CIT, TPS-LIN, etc.

### terpene_synthases.fasta (~20 entries)

Headers: `>{gene_id}|{cultivar_id}|{variant}|{produces_compound_id}`

Example:
```
>A-GEN-PMR3|A-CUL-TOM-014|A-TRT-PMR|variant=pmr_resistant|confidence=0.88
A-GEN-PMR3|A-CUL-TOM-014|A-TRT-PMR|variant=pmr_resistant|confidence=0.88
MASDRVPTNRPGSWQDRLXK...
```

Sequences: 200–400 random AA characters (never matched biologically).

### field_plantings_2025.csv (~8 rows)

Columns: id, cultivar_id, field, planted_date, area_m2, expected_first_harvest, notes

- A-CUL-TOM-014 planted in A-FLD-BLOCK-3, 2025-Sep, harvested 2025-Dec, ready for spring planting
- A-CUL-TOM-022 has hold/retest status because field validation failed

### harvest_logs/*.csv (5 files)

One file per harvested cultivar. Columns: harvest_date, cultivar_id, field, mass_kg, compound_id, titer_pct, notes

### protocols/*.md (3 files)

"Limonene assay protocol", "Cultivar genotyping protocol", "Field plot setup".
Each references cultivar/gene/compound IDs in prose for the linker.

### inquiries/*.json (3 files)

Sample inquiries:
1. "Looking for an essential oil with bright citrus notes, ideally high in limonene" ← DEMO QUESTION
2. "We need a soothing floral blend with linalool dominance"
3. "Menthol or cooling characteristics for a beverage application"

← Back to [CONTEXT.md](../CONTEXT.md)
