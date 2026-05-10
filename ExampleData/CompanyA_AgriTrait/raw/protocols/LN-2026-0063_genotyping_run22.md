# Lab Notebook Entry — Marker Genotyping PCR
**Entry ID:** LN-2026-0063  
**Protocol:** A-PROT-003 v3.0  
**Experiment:** Genotyping Run 22 — DRT2 & PMR3 Markers, Spring F3 Panel  
**Researcher:** S. Nair  
**Date:** 2026-04-03  
**Location:** Molecular Lab, Bench 4  

---

## Objective
Genotype 96 F3 individuals for markers DRT2 (drought tolerance, 180 bp amplicon) and PMR3 (powdery mildew resistance, 240 bp amplicon) to support selection in the spring breeding cycle.

---

## DNA Extraction
Tissue harvested 2026-04-01 (leaf punch, 2nd true leaf, 50 mg each).  
Extraction: Qiagen DNeasy Plant Mini Kit, batch extraction 96-well format.  
Lot: 175-DEN-2026-02. Elution volume: 100 µL AE buffer.

**QC — NanoDrop (every 12th sample + flagged wells):**

| Sample | Conc (ng/µL) | A260/A280 | Pass? |
|--------|-------------|-----------|-------|
| F3-004 | 78.2 | 1.85 | PASS |
| F3-016 | 52.1 | 1.79 | PASS |
| F3-028 | 41.3 | 1.71 | PASS (borderline) |
| F3-040 | 88.6 | 1.92 | PASS |
| F3-052 | 29.4 | 1.62 | **FAIL** — re-extract |
| F3-064 | 63.0 | 1.88 | PASS |
| F3-076 | 71.1 | 1.83 | PASS |
| F3-088 | 55.4 | 1.80 | PASS |

F3-052 re-extracted same day. Second attempt: 61.2 ng/µL, A260/A280 1.81 — PASS. Used re-extract in PCR.

Working stocks diluted to 50 ng/µL in TE for PCR.

---

## PCR Setup

**Master Mix:** Applied Biosystems AmpliTaq Gold 2x, Lot: 00-ATG-2026-01  
**Primers:**
| Marker | Forward Primer | Reverse Primer | Expected Amplicon |
|--------|---------------|---------------|-------------------|
| DRT2 | DRT2-F (10 µM) | DRT2-R (10 µM) | 180 bp |
| PMR3 | PMR3-F (10 µM) | PMR3-R (10 µM) | 240 bp |

**Reaction volumes (per 25 µL rxn):**
| Component | Vol (µL) |
|-----------|---------|
| 2x AmpliTaq Gold MM | 12.5 |
| Forward primer (10 µM) | 2.0 |
| Reverse primer (10 µM) | 2.0 |
| DNA template (50 ng/µL) | 2.0 |
| dH₂O (nuclease-free) | 6.5 |
| **Total** | **25.0** |

Plates set up on ice. Two 96-well plates (DRT2, PMR3). No-template control (NTC) in wells H11–H12.

---

## Thermocycler Program
**Instrument:** BioRad C1000, block #3 (last cal 2026-01-15)  
**Program:** STD-PCR-58 (saved on instrument)

| Step | Temp | Time | Cycles |
|------|------|------|--------|
| Initial denaturation | 95 °C | 5 min | 1 |
| Denaturation | 95 °C | 30 s | 35 |
| Annealing | **58 °C** | 30 s | 35 |
| Extension | 72 °C | 45 s | 35 |
| Final extension | 72 °C | 7 min | 1 |
| Hold | 4 °C | ∞ | — |

Run start: 2026-04-03 0935h. Run complete: 2026-04-03 1248h.

---

## Gel Electrophoresis
**Gel:** 1.5% agarose in 1x TAE, EtBr stained (0.5 µg/mL final)  
**Voltage:** 100 V, 35 min  
**Ladder:** 100 bp DNA ladder (NEB N3231, lot 10189247)  
**Gel imager:** GelDoc XR+ (last cal 2026-03-01)

Gel images saved: `run22-DRT2-gel.tif`, `run22-PMR3-gel.tif`

**NTC wells H11–H12:** No band visible in either plate — PASS.

**Positive controls:**
| Control | Expected band | Observed |
|---------|-------------|---------|
| DRT2 pos ctrl (A-REF-001) | 180 bp | 180 bp ✓ |
| PMR3 pos ctrl (A-REF-002) | 240 bp | 240 bp ✓ |

---

## Allele Calls (DRT2)
Scored as: AA = homozygous resistant, Aa = heterozygous, aa = homozygous susceptible, ? = unclear

| Individual | Band pattern | Call |
|------------|-------------|------|
| F3-001 | Single ~180 bp | AA |
| F3-002 | Two bands (180, ~160) | Aa |
| F3-003 | Single ~160 bp | aa |
| F3-004 | Single ~180 bp | AA |
| F3-007 | Two bands | Aa |
| F3-009 | Faint, smear | ? — re-run flagged |
| … | … | *(full calls in run22-calls.xlsx)* |

**DRT2 summary (n=95, excluding F3-009):**
- AA: 24 (25.3%)
- Aa: 47 (49.5%)
- aa: 24 (25.3%)
- ?: 1 (F3-009, re-run scheduled)

Observed ratio 1:2:1 — consistent with expected F3 segregation (χ² = 0.04, p > 0.05).

## Allele Calls (PMR3)
*(see run22-calls.xlsx — all 96 called, 0 unclear)*

**PMR3 summary (n=96):**
- AA: 26 (27.1%)
- Aa: 45 (46.9%)
- aa: 25 (26.0%)

χ² test: χ² = 0.08, p > 0.05. Expected 1:2:1 confirmed.

---

## Actions / Follow-up
- [ ] Re-run F3-009 (DRT2) — schedule in Run 23
- [ ] Upload calls to LIMS (SeedTrack module) by 2026-04-07
- [ ] Notify breeding coordinator: 24 AA DRT2 individuals available for advancement

---

## Reagent Inventory Post-Run
| Reagent | Lot | Vol remaining | Expiry |
|---------|-----|--------------|--------|
| AmpliTaq Gold 2x | 00-ATG-2026-01 | ~4 mL | 2027-06-30 |
| DRT2-F primer | DR2F-26-01 | ~180 µL | 2027-12-01 |
| DRT2-R primer | DR2R-26-01 | ~180 µL | 2027-12-01 |
| PMR3-F primer | PM3F-26-01 | ~170 µL | 2027-12-01 |
| PMR3-R primer | PM3R-26-01 | ~175 µL | 2027-12-01 |

---

## Sign-off
| Role | Name | Date | Signature |
|------|------|------|-----------|
| Researcher | S. Nair | 2026-04-03 | *(signed)* |
| Reviewer | T. Salazar | 2026-04-07 | *(signed)* |
