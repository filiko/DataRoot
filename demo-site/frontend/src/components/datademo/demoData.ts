// Scripted demo content for the DataRoot "Ask" view.
// Pure data — no backend, no LLM call. Authored around the Austin permits
// schema (permits, plan_reviews, code_complaints, code_tasks) so the Ask
// answers and the Edit/ERD canvas tell one coherent story.

export interface DemoSource {
  /** Source file the evidence came from. */
  file: string;
  /** Short role label, e.g. "linked context" / "final proof". */
  role: string;
  /** One-line description of what this source contributed. */
  detail: string;
}

export interface DemoQuestion {
  /** The customer-style question. */
  question: string;
  /** Short headline answer. */
  headline: string;
  /** Full cited answer. */
  answer: string;
  /** Confidence / source-count pill text. */
  confidence: string;
  /** Ordered cited source trail. */
  sources: DemoSource[];
}

export const DEMO_QUESTIONS: DemoQuestion[] = [
  {
    question: "Why is this client's permit review still delayed?",
    headline: "An open code complaint at the same address is blocking issuance.",
    answer:
      "Permit BP-2024-014823 (4502 Elm Ave) is still in review because an open " +
      "code complaint at the same address must clear before plan review can be " +
      "approved. The complaint has an enforcement task that is assigned but not " +
      "yet closed — so the permit cannot be issued until that task completes.",
    confidence: "4 linked sources",
    sources: [
      {
        file: "permits.csv",
        role: "starting record",
        detail: "BP-2024-014823 — status: in_review, issued_date: empty.",
      },
      {
        file: "plan_reviews.csv",
        role: "linked context",
        detail:
          "Review R-2024-0915 references permit_id BP-2024-014823 — status: pending_revisions.",
      },
      {
        file: "code_complaints.csv",
        role: "linked context",
        detail:
          "Case 2024-0488-CC at 4502 Elm Ave — status: open (linked by address).",
      },
      {
        file: "code_tasks.csv",
        role: "final proof",
        detail:
          "Task 2024-0731-UR tracks case 2024-0488-CC — status: open, due 2024-10-30.",
      },
    ],
  },
  {
    question: "Which department owns the open issue blocking this address?",
    headline: "Code Enforcement owns it — assigned, with an active task.",
    answer:
      "The open issue at 4502 Elm Ave is a noise violation owned by " +
      "Austin Code Enforcement. It is assigned to inspector C. Edwards, with an " +
      "active enforcement task due before the permit can be issued.",
    confidence: "2 linked sources",
    sources: [
      {
        file: "code_complaints.csv",
        role: "starting record",
        detail:
          "Case 2024-0488-CC — case_type: Noise Violation, department: Code Enforcement.",
      },
      {
        file: "code_tasks.csv",
        role: "final proof",
        detail:
          "Task 2024-0731-UR — assignee: C. Edwards, status: open, due 2024-10-30.",
      },
    ],
  },
  {
    question: "What stage is the plan review for this project at?",
    headline: "Pending revisions — the resubmittal is logged, permit not yet issued.",
    answer:
      "Plan review R-2024-0915 for project \"Elm Ave Addition\" is at " +
      "'pending_revisions'. The applicant's resubmittal is logged against permit " +
      "BP-2024-014823, which is still in review with no issued_date — so the " +
      "project has not cleared review yet.",
    confidence: "2 linked sources",
    sources: [
      {
        file: "plan_reviews.csv",
        role: "starting record",
        detail:
          "Review R-2024-0915 — project_name: Elm Ave Addition, status: pending_revisions.",
      },
      {
        file: "permits.csv",
        role: "final proof",
        detail: "Permit BP-2024-014823 — status: in_review, issued_date: empty.",
      },
    ],
  },
  {
    question: "Which strain had the highest citrus ester yield in the Q1 2026 assays?",
    headline: "B-STR-YE-017 (EsterMax 17) peaked at 42 mg/L ethyl hexanoate in run B-RUN-FERM-033.",
    answer:
      "Across the Q1 2026 GC-MS assay batch, strain B-STR-YE-017 (Yeast EsterMax 17) " +
      "produced the highest recorded ethyl hexanoate (B-MET-EHEX) at 42 mg/L in run " +
      "B-RUN-FERM-033 — above target for a bright fruit note. The next closest was " +
      "B-STR-YE-021 (Citriflow 21) at 38 mg/L. EsterMax 17 carries both B-GEN-AAT1 and " +
      "B-GEN-EHT1 pathway genes and is at pilot_ready stage.",
    confidence: "3 linked sources",
    sources: [
      {
        file: "fermentation/assays.csv",
        role: "starting record",
        detail: "B-ASSAY-GCMS-018 — strain B-STR-YE-017, run B-RUN-FERM-033, B-MET-EHEX: 42 mg/L, pass.",
      },
      {
        file: "fermentation/strains.csv",
        role: "linked context",
        detail: "B-STR-YE-017 Yeast EsterMax 17 — status: active, stage: pilot_ready, target: B-PROF-EST-01.",
      },
      {
        file: "fermentation/metabolites.csv",
        role: "final proof",
        detail: "B-MET-EHEX ethyl hexanoate — sensory: apple/pineapple/citrus-like/bright fruit/waxy.",
      },
    ],
  },
  {
    question: "Is strain B-STR-YE-021 available for a new fermentation run?",
    headline: "No — Citriflow 21 is on HOLD-SCALEUP with no vials available.",
    answer:
      "Strain B-STR-YE-021 (Yeast Citriflow 21) currently has a HOLD-SCALEUP status in " +
      "the Q1 2026 strain bank with no vials available for dispensing. The hold is pending " +
      "completion of a scale-up pilot run. The strain is bench-validated with strong ester " +
      "output (38 mg/L EHEX in B-RUN-FERM-036) but cannot be allocated until the pilot run completes.",
    confidence: "2 linked sources",
    sources: [
      {
        file: "fermentation/inventory.csv",
        role: "starting record",
        detail: "B-INV-STR-021-001 — strain B-STR-YE-021, status: HOLD-SCALEUP, Available_Vials: No.",
      },
      {
        file: "fermentation/strains.csv",
        role: "final proof",
        detail: "B-STR-YE-021 Yeast Citriflow 21 — development_stage: bench_validated, scale-up run incomplete.",
      },
    ],
  },
];
