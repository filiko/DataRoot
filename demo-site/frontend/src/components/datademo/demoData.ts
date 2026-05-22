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
      "The open issue at 4502 Elm Ave is a structure-condition violation owned by " +
      "Austin Code Enforcement. It is assigned to inspector C. Edwards, with an " +
      "active enforcement task due before the permit can be issued.",
    confidence: "2 linked sources",
    sources: [
      {
        file: "code_complaints.csv",
        role: "starting record",
        detail:
          "Case 2024-0488-CC — case_type: Structure Condition, department: Code Enforcement.",
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
];
