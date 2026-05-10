# Lab Notebook Entry — Field Readiness Review
**Entry ID:** LN-2026-0074  
**Protocol:** A-PROT-004 v1.8  
**Experiment:** Spring 2026 Field Release — DRT & PMR Panel  
**Researcher:** C. Vasquez (Operations Lead)  
**Review Date:** 2026-04-12  
**Location:** Conference Room / LIMS Review Session  

---

## Objective
Conduct pre-field readiness review for Spring 2026 release of DRT/PMR candidate lines. Verify all threshold criteria are met per A-PROT-004 before transferring to field nursery.

---

## Lines Under Review
28 candidate lines proposed for field advancement from Spring F3 panel.  
Source experiments: GH-B2 Run 1 (drydown), PMR Batch 4, Genotyping Run 22.

---

## Checklist

### 1. Greenhouse Trial Replication
**Requirement:** ≥ 2 GH replicates per trait

| Trait | Trials Completed | Status |
|-------|-----------------|--------|
| DRT (Drydown) | GH-B2 Run 1 (LN-2026-0041) | 1 complete, 1 in progress (GH-B2 Run 2, LN-2026-0048) |
| PMR (Pathogen Challenge) | Batch 3, Batch 4 | 2 complete ✓ |

> **NOTE:** DRT second replicate (GH-B2 Run 2) not yet complete as of review date. Decision: PMR-only lines may advance; DRT advancement deferred until Run 2 concludes (est. 2026-04-28). See decision log below.

---

### 2. Germination Rate
**Requirement:** ≥ 85% germination in most recent seed lot test

| Line | Germ% | Test Date | Pass? |
|------|-------|-----------|-------|
| A-F3-001 | 92 | 2026-03-05 | ✓ |
| A-F3-003 | 88 | 2026-03-05 | ✓ |
| A-F3-007 | 91 | 2026-03-05 | ✓ |
| A-F3-017 | 83 | 2026-03-05 | **✗** — below threshold |
| A-F3-028 | 87 | 2026-03-05 | ✓ |
| … | … | … | *(full list in field-readiness-spring26.xlsx)* |

Lines failing germ: **A-F3-017** — held from field, new seed lot requested from cold storage.

---

### 3. Seed Unit Count
**Requirement:** ≥ 500 seeds available (commercial threshold)

| Line | Seeds Available | Pass? |
|------|----------------|-------|
| A-F3-001 | 720 | ✓ |
| A-F3-007 | 510 | ✓ |
| A-F3-012 | 480 | **✗** |
| A-F3-017 | 630 | ✓ (held for germ, not seed count) |
| … | … | |

Lines failing seed count: **A-F3-012** — insufficient for field trial. Held pending seed increase round.

---

### 4. Marker Confidence Score
**Requirement:** ≥ 0.75 marker confidence score (composite DRT2 + PMR3)

Confidence scores calculated in LIMS (SeedTrack) from Run 22 allele calls.

| Line | DRT2 Call | PMR3 Call | Conf Score | Pass? |
|------|-----------|-----------|-----------|-------|
| A-F3-001 | AA | AA | 0.95 | ✓ |
| A-F3-003 | Aa | AA | 0.80 | ✓ |
| A-F3-007 | AA | Aa | 0.82 | ✓ |
| A-F3-009 | ? | AA | 0.65 | **✗** — pending re-run |
| A-F3-012 | aa | AA | 0.78 | ✓ (held on seed count) |
| A-F3-017 | AA | AA | 0.91 | ✓ (held on germ) |
| … | … | … | … | |

Lines failing marker conf: **A-F3-009** — pending Run 23 re-run of DRT2 (F3-009 unclear band, noted in LN-2026-0063).

---

### 5. LIMS Block Status
**Requirement:** LIMS block status = "ready"

Checked in SeedTrack 2026-04-12 1400h.

| Line | LIMS Status | Notes |
|------|------------|-------|
| A-F3-001 | ready | ✓ |
| A-F3-003 | ready | ✓ |
| A-F3-007 | ready | ✓ |
| A-F3-009 | pending | DRT2 re-run outstanding |
| A-F3-012 | hold | Seed count fail |
| A-F3-017 | hold | Germ fail |
| … | … | |

---

### 6. Field Trial Count
**Requirement:** ≥ 1 field trial completed per trait (prior season data acceptable)

| Trait | Field Trial | Season | Status |
|-------|------------|--------|--------|
| DRT | Field-2025-DRT-01 (Iowa site) | 2025 | Completed ✓ |
| PMR | Field-2025-PMR-01 (FL site) | 2025 | Completed ✓ |

Prior season data accepted per A-PROT-004 v1.8 §3.2.

---

## Summary of Hold / Advance Decisions

| Line | Advance? | Reason if Hold |
|------|---------|----------------|
| A-F3-001 | **ADVANCE** | All criteria met |
| A-F3-003 | **ADVANCE** | All criteria met |
| A-F3-007 | **ADVANCE** | All criteria met |
| A-F3-009 | **HOLD** | DRT2 marker unclear; re-run Run 23 |
| A-F3-012 | **HOLD** | Insufficient seed; increase round needed |
| A-F3-017 | **HOLD** | Germ below threshold; retest new lot |
| … | … | |

**Final count: 21 of 28 lines cleared for Spring 2026 field**

---

## Decision Log
- 2026-04-12: DRT-only replicate 2 not complete. Team decision (C. Vasquez, T. Salazar) to advance PMR-confirmed lines on existing DRT data + 2025 field trial. Documented per A-PROT-004 deviation process. Sign-off: T. Salazar.
- 2026-04-12: A-F3-017 germ retest approved. New cold storage lot (CS-F3-017-B) pulled; germ test initiated, results expected 2026-04-17.

---

## Sign-off
| Role | Name | Date | Signature |
|------|------|------|-----------|
| Operations Lead | C. Vasquez | 2026-04-12 | *(signed)* |
| Breeding Coordinator | T. Salazar | 2026-04-14 | *(signed)* |
| QA | R. Kim | 2026-04-14 | *(signed)* |
