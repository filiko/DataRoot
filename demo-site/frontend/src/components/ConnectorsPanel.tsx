import type { PenFile, Connector, ConnectorKind } from "../types/pen";

interface Props {
  pen: PenFile;
}

const KIND_LABEL: Record<ConnectorKind, string> = {
  seam: "Cross-service seams",
  webhook: "Webhooks",
  fan_out: "Fan-outs",
  middleware: "Middleware",
  shared_service: "Shared services",
  auth: "Auth",
};

const KIND_ORDER: ConnectorKind[] = ["seam", "fan_out", "webhook", "auth", "middleware", "shared_service"];

function Pill({ text, tone }: { text: string; tone: "blue" | "green" | "gray" | "violet" }) {
  const c = {
    blue: { bg: "#dbeafe", fg: "#1e40af", bd: "#bfdbfe" },
    green: { bg: "#dcfce7", fg: "#166534", bd: "#bbf7d0" },
    gray: { bg: "#f3f4f6", fg: "#374151", bd: "#e5e7eb" },
    violet: { bg: "#ede9fe", fg: "#5b21b6", bd: "#ddd6fe" },
  }[tone];
  return (
    <span style={{ fontSize: 10, fontWeight: 700, background: c.bg, color: c.fg, border: `1px solid ${c.bd}`, borderRadius: 999, padding: "1px 8px", textTransform: "capitalize" }}>
      {text}
    </span>
  );
}

function Chip({ text }: { text: string }) {
  return (
    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700" style={{ fontFamily: "ui-monospace, monospace" }}>{text}</code>
  );
}

function ConnectorCard({ conn }: { conn: Connector }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <h4 className="text-sm font-semibold text-gray-900">{conn.name}</h4>
        <div className="flex flex-shrink-0 items-center gap-1.5">
          <Pill text={conn.kind.replace("_", " ")} tone="violet" />
          <Pill text={conn.status} tone={conn.status === "wired" ? "green" : "gray"} />
        </div>
      </div>

      {(conn.trigger || conn.effect) && (
        <p className="mt-1.5 text-sm text-gray-700">
          {conn.trigger && <span><span className="font-medium text-gray-500">on</span> {conn.trigger}</span>}
          {conn.trigger && conn.effect && <span className="mx-1.5 text-gray-400">→</span>}
          {conn.effect && <span>{conn.effect}</span>}
        </p>
      )}

      {(conn.from_context || conn.to_contexts.length > 0) && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
          {conn.from_context && <Chip text={conn.from_context} />}
          {conn.to_contexts.length > 0 && <span className="text-gray-400">→</span>}
          {conn.to_contexts.map((c) => <Chip key={c} text={c} />)}
        </div>
      )}

      <div className="mt-2 flex flex-col gap-1 text-xs text-gray-500">
        {conn.contract && <div><span className="font-semibold text-gray-600">Contract: </span><code style={{ fontFamily: "ui-monospace, monospace" }}>{conn.contract}</code></div>}
        {conn.enforced_at.length > 0 && (
          <div>
            <span className="font-semibold text-gray-600">Wired at: </span>
            {conn.enforced_at.map((p, i) => (
              <code key={i} className="mr-1.5 rounded bg-gray-100 px-1 py-0.5" style={{ fontFamily: "ui-monospace, monospace" }}>{p}</code>
            ))}
          </div>
        )}
        {conn.spec_source && <div><span className="font-semibold text-gray-600">Spec: </span>{conn.spec_source}</div>}
      </div>
    </div>
  );
}

export function ConnectorsPanel({ pen }: Props) {
  const connectors = pen.dfd?.connectors ?? [];

  if (connectors.length === 0) {
    return (
      <div className="p-8 text-center text-sm text-gray-500">
        No connectors / middleware captured for this context yet.
        <div className="mt-1 text-xs text-gray-400">Connectors are the cross-service seams, webhooks, fan-outs, and shared middleware that wire the interconnected contexts together.</div>
      </div>
    );
  }

  const byKind = KIND_ORDER
    .map((kind) => ({ kind, items: connectors.filter((c) => c.kind === kind) }))
    .filter((g) => g.items.length > 0);

  return (
    <div className="mx-auto max-w-4xl p-6">
      <header className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Connectors &amp; Middleware</h3>
        <p className="text-sm text-gray-500">{connectors.length} connector{connectors.length === 1 ? "" : "s"} — how the interconnected contexts talk (seams, webhooks, fan-outs, shared middleware).</p>
      </header>
      {byKind.map(({ kind, items }) => (
        <section key={kind} className="mb-6">
          <h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-gray-400">{KIND_LABEL[kind]} ({items.length})</h4>
          <div className="flex flex-col gap-2.5">
            {items.map((c) => <ConnectorCard key={c.id} conn={c} />)}
          </div>
        </section>
      ))}
    </div>
  );
}
