# Expected Answer — Inquiry A-INQ-001

**Question:** "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?"

---

## Best Candidate: A-CUL-TOM-014 / Solara-14

### Genetic Basis
- Has both **A-GEN-DRT2** (drought tolerance) and **A-GEN-PMR3** (powdery mildew resistance) markers confirmed via A-PROT-003 genotyping
- Both markers have high confidence scores: DRT2 = 0.91, PMR3 = 0.88

### Evidence Level
- **Greenhouse validation:** A-CUL-TOM-014 passed both drought drydown assay (A-PROT-001, trials A-TRL-GH-001/002) and powdery mildew pathogen challenge (A-PROT-002, trials A-TRL-GH-003/004)
  - Wilting scores: 1.4 and 1.6 (threshold ≤ 2.0)
  - Lesion scores: 1.1 and 1.3 (threshold ≤ 1.5)
- **Field validation:** Trial A-TRL-FD-002 in field block A-FLD-BLOCK-3 during 2025-Fall season passed with yield 42.6 kg/plot and disease score 1.1

### Operational Status
- **Seed inventory:** A-INV-SEED-02 (LOT-TOM-014-2026A) — 2,400 seed units available
- **Germination:** 94% (well above 85% threshold)
- **Release status:** released (confirmed via QC check 2026-04-04)
- **Available seed exceeds minimum requirement** of 1,500 units requested in inquiry

### Deployment Readiness
- **Field block:** A-FLD-BLOCK-3 in Texas Zone 8 is ready for spring planting
- **Planting window:** 2026-04-20 to 2026-05-18
- **Block characteristics:** Sandy loam, deficit irrigation compatible, 1,200 m² available
- Soil report SOIL-RPT-2026-033 confirms block suitability for drought package cultivars

### Summary
A-CUL-TOM-014 (Solara-14) meets all readiness criteria:
1. ✅ Both target traits (drought tolerance + powdery mildew resistance) genetically confirmed
2. ✅ Greenhouse validation passed for both traits
3. ✅ Field trial validation completed and passed
4. ✅ Released seed inventory sufficient for spring planting request (2,400 units available, ≥ 1,500 required)
5. ✅ Compatible field block available in required region and planting window

**Recommendation:** Deploy A-CUL-TOM-014 for spring planting in Texas Zone 8. Proceed with seed availability confirmation to requestor.

---

## Secondary Candidate: A-CUL-TOM-022 / DryShield-22

### Why It's Not Primary
- Has both target markers (A-GEN-DRT2, A-GEN-PMR3) confirmed
- Greenhouse validation passed for both traits (trials A-TRL-GH-005 through 008)
- However, field trial A-TRL-FD-008 showed unexpected PMR susceptibility in one test block (retest pending)
- Seed inventory A-INV-SEED-03 is on hold pending field validation completion
- **Status:** greenhouse_validated, not field_ready

### Timeline for Elevation
If retest of A-TRL-FD-008 confirms PMR resistance, this cultivar could be elevated to field_ready status within 1-2 growing seasons.

---

## Insufficient Candidate: A-CUL-TOM-031 / Arida-31

### Why It's Not Sufficient for This Inquiry
- Has drought tolerance marker A-GEN-DRT2 confirmed
- Field trial A-TRL-FD-019 confirmed drought performance
- **Lacks powdery mildew resistance marker (A-GEN-PMR3)** — genotype shows PMR3 absent
- Pathogen challenge (A-TRL-GH-010/011) showed high susceptibility (lesion scores 3.2-3.4)
- Only suitable for inquiries requesting drought tolerance alone

---

## References

All data cross-referenced from:
- Trait ontology: trait_ontology.csv (A-TRT-DRT, A-TRT-PMR)
- Marker catalog: marker_gene_catalog.csv (A-GEN-DRT2, A-GEN-PMR3)
- Cultivar registry: cultivar_registry.csv (A-CUL-TOM-014, A-CUL-TOM-022, A-CUL-TOM-031)
- Greenhouse trials: greenhouse_trials_2026_q1.csv (A-TRL-GH-001 through 008)
- Field trials: field_trials_2025.csv (A-TRL-FD-002, A-TRL-FD-008, A-TRL-FD-019)
- Seed inventory: seed_inventory.csv (A-INV-SEED-02, A-INV-SEED-03, A-INV-SEED-04)
- Field blocks: field_blocks.csv (A-FLD-BLOCK-3)
- Protocols: A-PROT-001, A-PROT-002, A-PROT-003, A-PROT-004