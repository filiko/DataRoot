/**
 * Reference / Verify — a public, read-only gallery that places each textbook
 * ERD exercise's INDEPENDENT reference (citation + verbatim rules + the
 * textbook's published answer key + our verification verdicts) on the left,
 * beside the LIVE DataRoot ERD we render on the right. Lets a reviewer confirm
 * by eye that DataRoot diagrams each exercise correctly.
 *
 * The diagram is rendered with the real product engine (penToFlow + the actual
 * TableNode / crow's-foot CardinalityEdge) in a non-interactive ReactFlow, so
 * the thing under inspection is the genuine renderer.
 */
import { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { penToFlow, nodeTypes, edgeTypes } from "./ERDCanvas";
import { DiagramThemeProvider } from "../context/ThemeContext";
import { EdgeLabelDragProvider } from "./diagram/EdgeLabelDragProvider";
import { API } from "../config/api";
import type { PenFile } from "../types/pen";

interface RefRule {
  statement: string;
  status: "enforced" | "gap" | "deferred" | string;
  verified_by: string | null;
}
interface RefViolation {
  rule_id: string;
  message: string;
  node_name: string | null;
}
interface RefExercise {
  key: string;
  title: string;
  source: string;
  paragraph: string;
  reference_answer_key: string[];
  pen: PenFile;
  rules: RefRule[];
  violations: RefViolation[];
}

const STATUS_STYLE: Record<string, string> = {
  enforced: "bg-green-100 text-green-800 border-green-300",
  gap: "bg-red-100 text-red-700 border-red-300",
  deferred: "bg-gray-100 text-gray-600 border-gray-300",
};

function ReadOnlyErd({ pen }: { pen: PenFile }) {
  const flow = useMemo(() => penToFlow(pen, "technical"), [pen]);
  return (
    <DiagramThemeProvider themeId="technical">
      <EdgeLabelDragProvider onLabelMove={() => {}}>
        <ReactFlowProvider>
          <div className="reference-erd" style={{ width: "100%", height: "100%" }}>
            <style>{`
              .reference-erd .react-flow__node button { display: none !important; }
              .reference-erd .react-flow__handle { opacity: 0 !important; pointer-events: none !important; }
            `}</style>
            <ReactFlow
              nodes={flow.nodes}
              edges={flow.edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              nodesFocusable={false}
              edgesFocusable={false}
              fitView
              minZoom={0.15}
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </ReactFlowProvider>
      </EdgeLabelDragProvider>
    </DiagramThemeProvider>
  );
}

export function ReferencePage() {
  const [exercises, setExercises] = useState<RefExercise[]>([]);
  const [activeKey, setActiveKey] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetch(API.referenceExercises())
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: RefExercise[]) => {
        if (cancelled) return;
        setExercises(data);
        setActiveKey(data[0]?.key ?? "");
      })
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const active = exercises.find((e) => e.key === activeKey) ?? null;

  return (
    <div className="h-screen flex flex-col bg-white">
      {/* Header */}
      <header className="border-b border-gray-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Reference / Verify</h1>
          <p className="text-xs text-gray-500 font-mono">
            Textbook answer key (left) vs. the ERD DataRoot renders (right)
          </p>
        </div>
        <a href="/" className="text-sm text-gray-500 hover:text-gray-900 font-mono">← back</a>
      </header>

      {/* Exercise selector */}
      <div className="border-b border-gray-200 px-6 py-2 flex gap-2 flex-shrink-0">
        {exercises.map((ex) => (
          <button
            key={ex.key}
            onClick={() => setActiveKey(ex.key)}
            className={`text-sm px-3 py-1.5 border font-mono transition-colors ${
              ex.key === activeKey
                ? "border-gray-900 text-gray-900"
                : "border-gray-200 text-gray-500 hover:border-gray-400"
            }`}
          >
            {ex.title}
          </button>
        ))}
      </div>

      {loading && <div className="p-6 text-sm text-gray-500">Loading reference exercises…</div>}
      {error && (
        <div className="m-6 border border-red-200 bg-red-50 px-4 py-3 text-red-600 text-sm">
          Could not load /reference/exercises: {error}
        </div>
      )}

      {active && (
        <div className="flex flex-1 overflow-hidden">
          {/* LEFT — textbook reference (independent ground truth) */}
          <aside className="w-[44%] border-r border-gray-200 overflow-auto p-6 space-y-6">
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">Source</h2>
              <p className="text-xs text-gray-600 font-mono">{active.source}</p>
            </section>

            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Business rules (verbatim)
              </h2>
              <p className="text-sm text-gray-800 leading-relaxed">{active.paragraph}</p>
            </section>

            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-1">
                Textbook answer key
              </h2>
              <pre className="text-xs text-gray-800 bg-gray-50 border border-gray-200 rounded p-3 overflow-auto whitespace-pre-wrap">
                {active.reference_answer_key.join("\n")}
              </pre>
            </section>

            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">
                Verification verdicts
              </h2>
              <div className="space-y-2">
                {active.rules.map((r, i) => (
                  <div key={i} className="text-sm">
                    <span
                      className={`inline-block text-[10px] font-mono px-1.5 py-0.5 border rounded mr-2 align-middle ${
                        STATUS_STYLE[r.status] ?? STATUS_STYLE.deferred
                      }`}
                    >
                      {r.status}
                    </span>
                    <span className="text-gray-800">{r.statement}</span>
                    {r.verified_by && (
                      <div className="text-xs text-gray-400 font-mono ml-[3.2rem]">{r.verified_by}</div>
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-3 text-sm">
                {active.violations.length === 0 ? (
                  <span className="text-green-700">Structural integrity: clean ✓</span>
                ) : (
                  <div className="text-red-700">
                    {active.violations.map((v, i) => (
                      <div key={i} className="text-xs">
                        <span className="font-mono">{v.rule_id}</span>: {v.message}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </section>
          </aside>

          {/* RIGHT — the live DataRoot ERD */}
          <main className="flex-1 relative bg-gray-50">
            <ReadOnlyErd key={active.key} pen={active.pen} />
          </main>
        </div>
      )}
    </div>
  );
}
