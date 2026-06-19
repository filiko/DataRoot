import type { PenFile, BusinessRule, RuleCategory } from "../types/pen";

interface Props {
  pen: PenFile;
}

const CATEGORY_LABEL: Record<RuleCategory, string> = {
  invariant: "Invariants",
  state_machine: "State machines",
  gate: "Gates",
  validation: "Validation",
  lifecycle: "Lifecycle",
};

const CATEGORY_ORDER: RuleCategory[] = ["gate", "state_machine", "invariant", "lifecycle", "validation"];

function Pill({ text, tone }: { text: string; tone: "blue" | "amber" | "green" | "red" | "gray" }) {
  const c = {
    blue: { bg: "#dbeafe", fg: "#1e40af", bd: "#bfdbfe" },
    amber: { bg: "#fef9c3", fg: "#854d0e", bd: "#fde047" },
    green: { bg: "#dcfce7", fg: "#166534", bd: "#bbf7d0" },
    red: { bg: "#fee2e2", fg: "#991b1b", bd: "#fecaca" },
    gray: { bg: "#f3f4f6", fg: "#374151", bd: "#e5e7eb" },
  }[tone];
  return (
    <span style={{ fontSize: 10, fontWeight: 700, background: c.bg, color: c.fg, border: `1px solid ${c.bd}`, borderRadius: 999, padding: "1px 8px", textTransform: "capitalize" }}>
      {text}
    </span>
  );
}

function statusTone(status: BusinessRule["status"]): "green" | "amber" | "gray" {
  return status === "enforced" ? "green" : status === "gap" ? "amber" : "gray";
}

function RuleCard({ rule }: { rule: BusinessRule }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-sm font-semibold text-gray-900">{rule.title}</h4>
        <div className="flex flex-shrink-0 items-center gap-1.5">
          <Pill text={rule.severity.replace("_", " ")} tone={rule.severity === "constraint" ? "blue" : "gray"} />
          <Pill text={rule.status} tone={statusTone(rule.status)} />
        </div>
      </div>
      <p className="mt-1.5 text-sm text-gray-700">{rule.statement}</p>
      {rule.condition && (
        <pre className="mt-2 overflow-auto rounded bg-gray-50 px-2 py-1 text-xs text-gray-700" style={{ fontFamily: "ui-monospace, monospace" }}>{rule.condition}</pre>
      )}
      <div className="mt-2 flex flex-col gap-1 text-xs text-gray-500">
        {rule.enforced_at.length > 0 && (
          <div>
            <span className="font-semibold text-gray-600">Enforced at: </span>
            {rule.enforced_at.map((p, i) => (
              <code key={i} className="mr-1.5 rounded bg-gray-100 px-1 py-0.5" style={{ fontFamily: "ui-monospace, monospace" }}>{p}</code>
            ))}
          </div>
        )}
        {rule.spec_source && <div><span className="font-semibold text-gray-600">Spec: </span>{rule.spec_source}</div>}
        {rule.verified_by && <div><span className="font-semibold text-gray-600">Verified by: </span>{rule.verified_by}</div>}
      </div>
    </div>
  );
}

export function BusinessRulesPanel({ pen }: Props) {
  const rules = pen.dfd?.business_rules ?? [];

  if (rules.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-gray-500">
        No business rules captured for this context yet.
        <div className="mt-1 text-xs text-gray-400">Business rules are the behavioral counterpart to the ERD — invariants, lifecycle gates, and state machines, traceable to the code that enforces them.</div>
      </div>
    );
  }

  const byCategory = CATEGORY_ORDER
    .map((cat) => ({ cat, items: rules.filter((r) => r.category === cat) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Business Rules</h3>
        <p className="text-sm text-gray-500">{rules.length} rule{rules.length === 1 ? "" : "s"} governing this context — the behavioral layer beneath the ERD.</p>
      </header>
      {byCategory.map(({ cat, items }) => (
        <section key={cat} className="mb-6">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-400">{CATEGORY_LABEL[cat]} ({items.length})</h4>
          <div className="flex flex-col gap-2.5">
            {items.map((r) => <RuleCard key={r.id} rule={r} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
