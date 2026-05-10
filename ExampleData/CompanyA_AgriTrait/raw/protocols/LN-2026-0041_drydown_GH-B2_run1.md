# Lab Notebook Entry — Greenhouse Drydown Assay
**Entry ID:** LN-2026-0041  
**Protocol:** A-PROT-001 v2.1  
**Experiment:** GH-B2 Drought Tolerance Screen — Run 1  
**Researcher:** M. Okonkwo  
**Date Started:** 2026-03-10  
**Location:** GH Block B, Bench 2  

---

## Objective
Screen 48 F3:4 lines (DRT backcross panel) for wilting tolerance and recovery response under drydown stress. Positive check: A-CHECK-DRT-R (tolerant). Negative check: A-CHECK-DRT-S (susceptible).

---

## Materials
| Item | Lot / Source | Qty |
|------|-------------|-----|
| Metro-Mix 360 | MM-2025-11 | 2 bags |
| 1 L pots | Stock | 50 |
| Saucers | Stock | 50 |
| Fertilizer (20-20-20) | F-2026-01 | diluted 200ppm |
| Seed (F3:4 lines, 48 entries) | Seed vault, pulled 2026-03-08 | 5 seeds/pot |

---

## Environmental Conditions — Setup
| Parameter | Target | Recorded |
|-----------|--------|----------|
| Temperature | 25 °C | 24.8 °C |
| Humidity | 65% | 67% |
| Light period | 16L:8D | 16L:8D |
| Pot size | 1000 mL | 1000 mL |

*Greenhouse controller log attached: GH-B2-2026-03-10.pdf*

---

## Seeding — 2026-03-10
Sowed 5 seeds per pot, 1 pot per entry. Pots arranged in randomized complete block design (RCBD), 2 blocks. Layout map saved: `GH-B2-run1-layout.xlsx`.

Germination checked 2026-03-17 (day 7). Thinned to 1 plant/pot on 2026-03-18.

| Germination notes |
|---|
| Entry 22 (line A-F3-022): 0/5 germinated — excluded from trial, flagged to breeding |
| Entry 37 (line A-F3-037): 3/5 germinated — thinned normally |
| All other entries: ≥4/5 germinated |

---

## Watering to Field Capacity — 2026-03-10 to 2026-04-02
Plants watered daily to field capacity (FC) by weight (~950 g/pot). Growth stage at drydown initiation: V4 (4th leaf collar visible).

---

## Drydown Initiation — 2026-04-02 (Day 0)
Water withheld from all pots at 0800h. Starting pot weights recorded in `GH-B2-run1-weights.csv`.

---

## Wilting Observations

### Day 2 — 2026-04-04
| Entry | Block 1 Wilt Score | Block 2 Wilt Score | Notes |
|-------|-------------------|--------------------|-------|
| A-CHECK-DRT-S | 3.0 | 3.5 | Susceptible check responding as expected |
| A-CHECK-DRT-R | 0.5 | 0.5 | Tolerant check holding |
| A-F3-001 | 1.0 | 0.5 | |
| A-F3-003 | 2.5 | 2.0 | |
| A-F3-007 | 0.5 | 1.0 | |
| A-F3-012 | 3.0 | 2.5 | Early wilter |
| … | … | … | *(full dataset in GH-B2-run1-scores.xlsx)* |

### Day 4 — 2026-04-06 (Re-water day)
Pot weights at drydown end recorded. Re-water applied at 1000h to FC.

Peak wilting scores (max across both blocks):
- 6 entries scored ≤ 2.0 — passed wilt threshold per A-PROT-001
- 18 entries scored 2.1–3.0 — borderline, flagged for second run
- 24 entries scored > 3.0 — failed wilt threshold

---

## Recovery Observations

### 48hr Post Re-water — 2026-04-08
| Entry | Block 1 Recovery | Block 2 Recovery | Pass/Fail |
|-------|-----------------|-----------------|-----------|
| A-CHECK-DRT-R | 0.5 | 0.5 | PASS |
| A-CHECK-DRT-S | 2.5 | 3.0 | FAIL (expected) |
| A-F3-001 | 1.0 | 1.0 | PASS |
| A-F3-007 | 0.5 | 1.0 | PASS |
| A-F3-012 | 2.0 | 1.5 | PASS (marginal) |
| … | … | … | *(full dataset in GH-B2-run1-scores.xlsx)* |

---

## Biomass Harvest — 2026-04-15
Above-ground biomass harvested, bagged per pot, dried at 65 °C for 72 hr (oven ID: FO-GH-03, started 2026-04-15 1400h).

Dry weights recorded 2026-04-18. Data file: `GH-B2-run1-biomass.csv`.

---

## Deviations / Observations
- Entry A-F3-022 excluded (failed germination); notify breeding coordinator
- Temperature excursion 2026-03-28: recorded 27.2 °C for ~2 hr due to controller fault — logged in GH maintenance log, deemed acceptable per deviation threshold
- Oven FO-GH-03 calibration current (last cal 2026-02-14, due 2026-08-14)

---

## Sign-off
| Role | Name | Date | Signature |
|------|------|------|-----------|
| Researcher | M. Okonkwo | 2026-04-18 | *(signed)* |
| Reviewer | T. Salazar | 2026-04-20 | *(signed)* |
