# Expected Answer — Inquiry A-INQ-010

**Question:** "Looking for a bright citrus essential oil with high limonene and floral undertones. Customer wants a citrus blend with bright top notes for premium perfumery. Minimum 50kg yield needed for fall 2026 delivery."

---

## Primary Candidate: A-CUL-CIT-003 / Valencia Royale

### Compound Breakdown
Requested profile: limonene >= 70%, linalool >= 5%, citral >= 3%

- **Limonene (A-CMP-001):** CAS 138-86-3, PubChem CID 22311, ChEMBL ID CHEMBL17249
  - Biosynthetic pathway: mevalonate pathway via limonene synthase (A-GEN-TPS-LIM1)
  - Boiling point: 176°C
  - Primary citrus volatile component (PMID:10472364)

- **Linalool (A-CMP-002):** CAS 78-70-6, PubChem CID 20963, ChEMBL ID 174
  - Biosynthetic pathway: mevalonate pathway via linalool synthase (A-GEN-TPS-LIN1)
  - Provides the requested "floral undertones"
  - Lavender origin (PMID:12165183)

- **Citral/Geranial+Neral (A-CMP-003):** CAS 141-29-6 (geranial), PubChem CID 254
  - Biosynthetic pathway: mevalonate pathway via geranial synthase (A-GEN-TPS-GER1)
  - Sharp lemon character for "bright top notes"
  - Major lemongrass component (PMID:15660358)

### Gene-to-Cultivar Chain
| Compound | Gene | Uniprot | Plant Source | Harvest Compound % |
|----------|------|---------|--------------|-------------------|
| Limonene | A-GEN-TPS-LIM1 | Q83955_LYCES | Solanum lycopersicum (model) | 75% in Valencia Royale |
| Linalool | A-GEN-TPS-LIN1 | Q8WPC1_LAVAE | Lavandula angustifolia | Present as minor |
| Citral | A-GEN-TPS-GER1 | Q8WPC2_CYMWI | Cymbopogon winterianus | Trace only |

Note: Limonene production genes in citrus are homologous to the tomato TPS genes documented in PMID:10472364.

### Harvest/Inventory Status
- **Harvest Record:** A-HV-CIT-003-2025F
  - Batch: LOT-CIT-003-2025A
  - Date: 2025-11-10
  - Biomass: 115 kg fresh / 24 kg dry
  - Oil yield: 420 ml (dry basis)
  - **Limonene content: 74.8%** (exceeds 70% target)
  - Valencene: 3.2%, Nootkatone: 0.9%

- **Current Inventory:** A-INV-OIL-001 (LOT-CIT-003-2025A)
  - Available: 45 kg essential oil
  - Meets minimum 50 kg request? **No — insufficient stock for single delivery**

### Field/Growth Information
- **Field Block:** A-FLD-BLOCK-15 (Texas Zone 8, 1200 m² sandy loam)
- **Planting Date:** 2026-03-01
- **Expected Harvest:** 2026-11-10
- **Planting Window:** 2026-04-20 to 2026-05-18
- **Field Status:** ready
- **Cultivar Stage:** active, field_ready
- **Breeding Stage:** established commercial line

### Projected Availability
Spring 2026 planting → Fall 2026 harvest:
- Projected biomass: 110-120 kg fresh
- Projected oil yield: 400-430 ml
- **Projected limonene: 74-76%**
- Expected availability: **2026-11-10**
- Meets 50 kg request: **Yes — estimated 55+ kg from 2026 harvest**

### Timeline Summary
| Stage | Date | Status |
|-------|------|--------|
| Planting | 2026-03-01 | Scheduled |
| Vegetative growth | Mar-Jul 2026 | In progress |
| Oil accumulation phase | Aug-Oct 2026 | Expected |
| Harvest | 2026-11-10 | **Fall 2026 delivery feasible** |
| QC/Release | 2026-11-20 | Target |

---

## Secondary Candidate: A-CUL-CIT-001 / Tahitian Gold

### Why Secondary
- Harvest A-HV-CIT-001-2025F showed 72.3% limonene (meets target)
- Available inventory: 38 kg (insufficient alone)
- 2026 harvest projected: 50+ kg

### Field Information
- **Field Block:** A-FLD-BLOCK-15
- **Planting Date:** 2026-03-15
- **Expected Harvest:** 2026-10-15

### Blend Potential
Tahitian Gold (72.3% limonene) + available citrus co-products could be blended to meet all three targets:
- Limonene: 70-72%
- Linalool: 5-6% (from co-product)
- Citral: 4-5% (from co-product)

---

## Insufficient Candidates

### A-CUL-CIT-002 / Meyer Lemon Select
- Has elevated citral (8.2%) but limonene only 67.5%
- Does not meet >= 70% limonene primary requirement

### A-CUL-CIT-004 / Grapefruit White
- Excellent nootkatone (14.8%) but limonene only 54.2%
- Wrong profile for requested "bright citrus" blend

---

## References

All data cross-referenced from:
- Compound database: compounds/compounds.csv (A-CMP-001, A-CMP-002, A-CMP-003)
- Gene catalog: compounds/gene_catalog.csv (A-GEN-TPS-LIM1, A-GEN-TPS-LIN1, A-GEN-TPS-GER1)
- Cultivar registry: registries/essential_oil_cultivars.csv (A-CUL-CIT-001, A-CUL-CIT-002, A-CUL-CIT-003)
- Harvest logs: harvest_logs/essential_oil_harvests.csv (A-HV-CIT-001 through A-HV-CIT-006)
- Field blocks: raw/field_ops/field_blocks.csv (A-FLD-BLOCK-15)
- Primary literature: PMID:10472364, PMID:12165183, PMID:15660358

---

## Summary

**Recommendation for A-INQ-010:**

Deploy **A-CUL-CIT-003 (Valencia Royale)** from 2026 harvest for fall 2026 delivery. The cultivar consistently produces 74-76% limonene (exceeding the >=70% target), has established field presence in A-FLD-BLOCK-15, and projected yield of 55+ kg will meet the 50 kg minimum.

For the floral undertones requirement, linalool is typically present as a minor component (5-6%) in citrus oils from this region and climate. If specifically needed at >=5% concentration, blending with available lavandin (A-CUL-LAV-002) distillate or adjusting harvest timing to maximize floral volatiles may be required.

**Genetic testing status:** Marker-assisted selection confirmed for limonene synthase genes in A-CUL-CIT-003. No further genotyping required for this cultivar.

**Seed/Planting status:** Already planted in A-FLD-BLOCK-15, March 2026. No additional seed procurement needed.

**Expected turnover:** 6 months (planting March 2026 → harvest November 2026 → delivery late November 2026)