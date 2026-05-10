# Expected Answer — Inquiry B-INQ-001

**Question:** "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?"

---

## Best Candidate: B-STR-YE-017 / Yeast EsterMax 17

### Genetic Basis
- Has pathway genes **B-GEN-AAT1** (ester biosynthesis) and **B-GEN-EHT1** (medium-chain ester biosynthesis) confirmed via B-PROT-003 genotyping
- These genes encode the enzymes responsible for producing:
  - **B-MET-EHEX** (ethyl hexanoate) — bright fruit/apple/pineapple/citrus notes
  - **B-MET-EBUT** (ethyl butyrate) — pineapple/orange-like/sweet fruit notes
  - **B-MET-EOCT** (ethyl octanoate) — orange peel/waxy fruit/floral notes
- AAT1: high evidence level; EHT1: high evidence level

### Fermentation Evidence
- **Completed run:** B-RUN-FERM-033 — low-temperature pilot run (14°C, 96 hours, 20L scale)
- **Conditions:** Temperature 14°C (within 12-16°C optimal range), pH 5.2 → 4.4, standard duration
- **Protocol:** Followed B-PROT-001 low-temperature fermentation protocol
- **Media:** B-MEDIA-EST-04 (LowTemp Ester Media) — optimized for ester production at low temperature

### Assay Results
- **B-ASSAY-GCMS-018:** B-MET-EHEX = 42 mg/L (target ≥ 35 mg/L, threshold ≥ 30 mg/L) — **PASS**
- **B-ASSAY-GCMS-019:** B-MET-EBUT = 31 mg/L (target ≥ 25 mg/L, threshold ≥ 20 mg/L) — **PASS**
- **B-ASSAY-GCMS-020:** B-MET-EOCT = 18 mg/L (target ≥ 15 mg/L, threshold ≥ 10 mg/L) — **PASS**
- **Combined target metabolites:** 42 + 31 + 18 = **91 mg/L** (threshold ≥ 85 mg/L) — **PASS**
- **Off-note (B-MET-DIAC):** B-ASSAY-GCMS-021 = 3 mg/L (threshold ≤ 5 mg/L) — **PASS**, low diacetyl

### Quality Control
- **Contamination screen:** B-QC-REL-005 and B-QC-REL-007 — both negative, **PASS**
- **Identity check:** B-QC-REL-006 and B-QC-REL-008 — both match, **PASS**
- **Release status:** All QC passed, strain is **released**

### Inventory Status
- **B-INV-STR-017:** 42 cryovials available
- **Passage number:** 5 (within ≤ 6 limit for yeast)
- **Viability:** 96% (above 90% threshold)
- **Release status:** released
- **Storage:** Cryobank Rack C

### Scale-Up Timeline
- **Bioreactor:** B-BR-R2 (50L capacity) is available from 2026-04-28 through 2026-05-10
- **Booking:** Window open for reservation
- **Timeline calculation:**
  - Inoculate: 2026-04-28
  - Duration: 96 hours (~4 days)
  - Harvest: ~2026-05-02
  - QC release: 48-72 hours → 2026-05-04 to 2026-05-05
  - **Target ready by: 2026-05-15** — Achievable with buffer
- **Media:** B-MEDIA-EST-04 already validated with this strain

### Summary
B-STR-YE-017 (Yeast EsterMax 17) satisfies all criteria:
1. ✅ Fruit-forward citrus-like ester profile genetically confirmed (B-GEN-AAT1 + B-GEN-EHT1)
2. ✅ Target metabolites above acceptance thresholds (combined 91 mg/L ≥ 85 mg/L)
3. ✅ Off-note diacetyl well below threshold (3 mg/L ≤ 5 mg/L)
4. ✅ Completed pilot-scale run (B-RUN-FERM-033, 20L)
5. ✅ All QC checks passed, released for pilot use
6. ✅ Strain bank available with sufficient cryovials (42) and high viability (96%)
7. ✅ Compatible bioreactor (B-BR-R2) available within timeline
8. ✅ Can meet target_ready_by of 2026-05-15

**Recommendation:** Schedule B-STR-YE-017 for pilot scale-up in B-BR-R2 starting 2026-04-28 to meet B-INQ-001 delivery timeline.

---

## Secondary Candidate: B-STR-YE-021 / Yeast Citriflow 21

### Why It's Not Primary
- Has target pathway gene B-GEN-AAT1 confirmed
- **Bench-scale ester production:** B-ASSAY-GCMS-026 (EHEX: 38 mg/L) and B-ASSAY-GCMS-027 (EBUT: 27 mg/L) — good profile at bench scale
- **However:** No pilot-scale run completed yet
- **Scale-up status:** B-QC-REL-011 (scaleup_review) is pending — strain on hold pending pilot run
- **Inventory:** B-INV-STR-021 (18 cryovials, 93% viability) but status is hold_scaleup
- **Timeline:** Would need at least one pilot-scale run before recommendation, which cannot be completed and QC'd before B-INQ-001 target_ready_by

### Potential Path Forward
If timeline allowed, B-STR-YE-021 could be a secondary source. But for B-INQ-001's target_ready_by of 2026-05-15, B-STR-YE-017 is the only scale-ready option.

---

## Insufficient Candidate: B-STR-YE-018 / Yeast BananaFlow 18

### Why It's Not Sufficient for This Inquiry
- Produces isoamyl acetate (B-MET-IAA) — banana/pear ester profile
- Does not produce the citrus-target esters (EHEX, EBUT, EOCT) in sufficient quantities
- **Profile:** B-PROF-BANANA-04, not B-PROF-EST-01
- Not appropriate for B-INQ-001's citrus fruit-forward request

---

## References

All data cross-referenced from:
- Inquiry: product_profile_requests.json (B-INQ-001)
- Profile ontology: product_profile_ontology.csv (B-PROF-EST-01)
- Pathway genes: pathway_gene_catalog.csv (B-GEN-AAT1, B-GEN-EHT1)
- Metabolites: metabolite_catalog.csv (B-MET-EHEX, B-MET-EBUT, B-MET-EOCT)
- Strain registry: strain_registry.csv (B-STR-YE-017, B-STR-YE-021, B-STR-YE-018)
- Fermentation runs: fermentation_runs_2026_q1.csv (B-RUN-FERM-033)
- Assays: gcms_metabolite_assays_2026_q1.csv (B-ASSAY-GCMS-018 through 021)
- QC records: qc_release_status.csv (B-QC-REL-005 through 008)
- Strain inventory: strain_inventory.csv (B-INV-STR-017, B-INV-STR-021)
- Bioreactor schedule: bioreactor_schedule.csv (B-BR-R2)
- Media recipes: media_recipes.csv (B-MEDIA-EST-04)
- Protocols: B-PROT-001, B-PROT-002, B-PROT-003, B-PROT-004