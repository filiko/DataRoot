import React, { useEffect, useRef, useState } from "react";
import type { PenFile } from "../types/pen";
import { AskView } from "./datademo/AskView";
import { loadDemoProject } from "./datademo/loadDemo";
import { WaitlistSection } from "./WaitlistSection";

// DataRootPre root/plant palette
const C = {
  dark:  "#151c17",
  paper: "#f7f5ee",
  panel: "#fffdf6",
  root:  "#264334",
  root2: "#345f49",
  leaf:  "#91b88e",
  gold:  "#d7b46a",
  ink:   "#141512",
  muted: "#5f655a",
  line:  "rgba(38,67,52,0.18)",
  cream: "#f5f0df",
};

interface Props {
  onIngested: (projectId: string, pen: PenFile) => void;
  onStartBlank: (projectId: string, pen: PenFile) => void;
  onLoadExample: (projectId: string, pen: PenFile) => void;
  onLoadNexusExercise: (projectId: string, pen: PenFile) => void;
  onLoadClaudeEval: (projectId: string, pen: PenFile) => void;
  onLoadRepoAnalysis: (projectId: string, pen: PenFile) => void;
}

// Shared style helpers
const eyebrow: React.CSSProperties = {
  margin: 0, color: C.gold, fontSize: 12, fontWeight: 800,
  letterSpacing: "0.16em", textTransform: "uppercase",
};
const heroText: React.CSSProperties = {
  margin: 0, color: "rgba(245,240,223,0.68)", fontSize: 18, lineHeight: 1.55,
};
const muted: React.CSSProperties = { color: C.muted };
const lineStyle = `1px solid ${C.line}`;

export function LandingGridly({
  onIngested: _onIngested, onStartBlank: _onStartBlank, onLoadExample, onLoadNexusExercise: _onNexus, onLoadClaudeEval: _onClaude, onLoadRepoAnalysis: _onRepo,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const demoRef     = useRef<HTMLDivElement>(null);
  const waitlistRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&display=swap";
    document.head.appendChild(link);
    return () => { document.head.removeChild(link); };
  }, []);

  async function runDemo() {
    setLoading(true); setError(null);
    try {
      const { projectId, pen } = await loadDemoProject();
      onLoadExample(projectId, pen);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not load demo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh", overflowX: "hidden",
      background: `
        linear-gradient(90deg, ${C.line} 1px, transparent 1px),
        linear-gradient(0deg, ${C.line} 1px, transparent 1px),
        ${C.paper}
      `,
      backgroundSize: "42px 42px, 42px 42px, auto",
    }}>

      {/* ── Topbar ── */}
      <div style={{
        height: 66, display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 32px", background: C.dark, borderBottom: "1px solid rgba(255,255,255,0.09)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 800 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8, background: C.leaf,
            display: "grid", placeItems: "center", color: C.dark, fontSize: 16, fontWeight: 900,
          }}>
            ⌖
          </div>
          <span style={{ color: C.cream, fontSize: 16 }}>DataRoot</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24, color: "rgba(245,240,223,0.62)", fontSize: 14 }}>
          <button
            onClick={() => waitlistRef.current?.scrollIntoView({ behavior: "smooth" })}
            style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", font: "inherit" }}
          >
            Join Waitlist
          </button>
          <button
            onClick={runDemo}
            disabled={loading}
            style={{
              minHeight: 36, display: "inline-flex", alignItems: "center", gap: 8,
              borderRadius: 6, padding: "0 14px", fontWeight: 700, fontSize: 13,
              background: C.cream, color: C.dark, border: "none", cursor: "pointer",
              opacity: loading ? 0.6 : 1,
            }}
          >
            Run the demo →
          </button>
        </div>
      </div>

      {/* ── Hero ── */}
      <section style={{
        minHeight: "88vh", display: "flex", flexDirection: "column",
        background: C.dark, color: C.cream, borderBottom: `1px solid rgba(255,255,255,0.08)`,
      }}>
        <div style={{
          flex: 1, width: "min(1180px, calc(100% - 48px))", margin: "0 auto",
          display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(420px,0.8fr)",
          gap: 54, alignItems: "center", padding: "64px 0 78px",
        }}>
          {/* Left: copy */}
          <div>
            <p style={eyebrow}>Context infrastructure</p>
            <h1 style={{
              margin: "24px 0 26px", fontFamily: "'Caveat', cursive",
              fontSize: "clamp(58px, 8vw, 100px)", lineHeight: 0.96, letterSpacing: 0, color: C.cream,
            }}>
              Give every answer a source trail.
            </h1>
            <p style={{ ...heroText, maxWidth: 560 }}>
              Point DataRoot at your files. It links them into a traversable knowledge base — so agents and teams find the right context instead of rebuilding it every time.
            </p>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 34 }}>
              <button
                onClick={runDemo}
                disabled={loading}
                style={{
                  minHeight: 46, display: "inline-flex", alignItems: "center", gap: 10,
                  borderRadius: 8, padding: "0 22px", fontWeight: 750, fontSize: 15,
                  background: C.cream, color: C.dark, border: "none", cursor: "pointer",
                  opacity: loading ? 0.6 : 1,
                }}
              >
                Run the demo →
              </button>
              <button
                onClick={() => demoRef.current?.scrollIntoView({ behavior: "smooth" })}
                style={{
                  minHeight: 46, display: "inline-flex", alignItems: "center", gap: 10,
                  borderRadius: 8, padding: "0 22px", fontWeight: 750, fontSize: 15,
                  color: C.cream, border: "1px solid rgba(245,240,223,0.22)",
                  background: "transparent", cursor: "pointer",
                }}
              >
                See how it works
              </button>
            </div>
            {error && (
              <div style={{ marginTop: 14, border: "1px solid rgba(192,57,43,0.4)", borderRadius: 6, padding: "10px 16px", color: "#c0392b", fontSize: 13, background: "rgba(192,57,43,0.05)" }}>
                {error}
              </div>
            )}
          </div>

          {/* Right: static ask-panel preview */}
          <div style={{
            border: `1px solid rgba(20,21,18,0.12)`, borderRadius: 10,
            background: C.panel, boxShadow: "0 24px 80px rgba(0,0,0,0.3)",
            padding: 22, color: C.ink,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 18 }}>
              <div>
                <p style={{ ...eyebrow, color: C.muted, marginBottom: 6 }}>Live Ask</p>
                <p style={{ margin: 0, fontWeight: 700, fontSize: 16, color: C.ink }}>Why is this permit review delayed?</p>
              </div>
              <span style={{
                display: "flex", alignItems: "center", gap: 6,
                border: `1px solid rgba(52,95,73,0.22)`, borderRadius: 999,
                background: "rgba(145,184,142,0.16)", color: C.root,
                padding: "6px 11px", fontSize: 12, fontWeight: 800, whiteSpace: "nowrap",
              }}>
                ◉ 4 sources
              </span>
            </div>
            <div style={{
              padding: "12px 14px", border: lineStyle, borderRadius: 8, background: "#f1ead7",
              fontSize: 14, lineHeight: 1.55, color: "#32372f", marginBottom: 14,
            }}>
              An open code complaint at the same address is blocking permit issuance.
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[
                { n: 1, file: "permits.csv",         role: "starting record" },
                { n: 2, file: "plan_reviews.csv",    role: "linked context" },
                { n: 3, file: "code_complaints.csv", role: "linked context" },
                { n: 4, file: "code_tasks.csv",      role: "final proof", gold: true },
              ].map((s) => (
                <div key={s.n} style={{
                  display: "flex", gap: 10, alignItems: "center",
                  border: lineStyle, borderRadius: 6, padding: "8px 10px",
                }}>
                  <span style={{
                    width: 22, height: 22, flexShrink: 0, borderRadius: "50%",
                    background: s.gold ? C.gold : "rgba(145,184,142,0.2)",
                    color: s.gold ? C.ink : C.root,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 11, fontWeight: 900, fontFamily: "monospace",
                  }}>{s.n}</span>
                  <span style={{ fontFamily: "monospace", fontSize: 12, fontWeight: 700, color: C.root, flex: 1 }}>{s.file}</span>
                  <span style={{ fontSize: 10, color: s.gold ? C.gold : C.muted, textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "monospace" }}>{s.role}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Problem band ── */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr auto",
        gap: 28, alignItems: "center",
        padding: "28px max(24px, calc((100vw - 1180px) / 2))",
        background: C.panel, borderBottom: lineStyle,
      }}>
        <div>
          <span style={{ display: "block", color: C.muted, fontSize: 12, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase" }}>The context problem</span>
          <strong style={{ display: "block", maxWidth: 820, marginTop: 7, fontSize: "clamp(18px, 2.5vw, 28px)", lineHeight: 1.18, color: C.ink }}>
            Agents forget rules. Teams rebuild context in every chat. Answers get guessed, not sourced.
          </strong>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {[
            { label: "Answer time", value: "Seconds, not hours" },
            { label: "Source proof", value: "Every answer cited" },
          ].map((m) => (
            <div key={m.label} style={{ minWidth: 126, borderLeft: lineStyle, paddingLeft: 14 }}>
              <span style={{ display: "block", color: C.muted, fontSize: 11, fontWeight: 800, letterSpacing: "0.14em", textTransform: "uppercase" }}>{m.label}</span>
              <strong style={{ display: "block", marginTop: 6, color: C.root, fontSize: 14 }}>{m.value}</strong>
            </div>
          ))}
        </div>
      </div>

      {/* ── Interactive Ask Demo ── */}
      <section ref={demoRef} style={{
        width: "min(1180px, calc(100% - 48px))", margin: "0 auto", padding: "80px 0",
      }}>
        <div style={{ maxWidth: 620, marginBottom: 36 }}>
          <p style={eyebrow}>DataRoot · Live Ask</p>
          <h2 style={{ margin: "10px 0 12px", color: C.ink, fontSize: "clamp(32px, 4.5vw, 56px)", lineHeight: 1 }}>
            Ask a question.<br />Get a cited answer.
          </h2>
          <p style={{ margin: 0, ...muted, fontSize: 17, lineHeight: 1.55 }}>
            Every answer is traced back through the linked source files — no guessing, no rebuilding context. Pick a question below to see the trail.
          </p>
        </div>

        {/* AskView embedded as demo console */}
        <div style={{ borderRadius: 10, overflow: "hidden", boxShadow: "0 24px 80px rgba(0,0,0,0.14)" }}>
          <AskView onOpenWorkspace={runDemo} />
        </div>
      </section>

      {/* ── Flow section ── */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
        gap: 1, background: C.line, borderTop: lineStyle,
      }}>
        {[
          { n: "01", title: "Ingest",  body: "Drop in files — spreadsheets, exports, a whole repo. DataRoot reads them all without a schema." },
          { n: "02", title: "Link",    body: "Repeated IDs, foreign keys, and shared addresses become connections. Scattered files turn into one graph." },
          { n: "03", title: "Ask",     body: "Agents and teams ask questions and get answers with a full cited source trail. Context that doesn't have to be rebuilt." },
        ].map((s) => (
          <div key={s.n} style={{
            minHeight: 260, background: C.dark, color: C.cream, padding: 34,
            display: "flex", flexDirection: "column",
          }}>
            <span style={{
              display: "block", color: "rgba(145,184,142,0.8)", fontSize: 11, fontWeight: 800,
              letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: "auto",
            }}>
              {s.n}
            </span>
            <strong style={{ display: "block", marginTop: 42, fontSize: 26, color: C.cream }}>{s.title}</strong>
            <p style={{ maxWidth: 320, margin: "10px 0 0", color: "rgba(245,240,223,0.62)", lineHeight: 1.55, fontSize: 15 }}>{s.body}</p>
          </div>
        ))}
      </div>

      {/* ── Waitlist ── */}
      <WaitlistSection ref={waitlistRef} />

      {/* ── Footer ── */}
      <footer style={{ borderTop: lineStyle, padding: "28px 24px", textAlign: "center" }}>
        <span style={{ fontSize: 12, fontFamily: "monospace", letterSpacing: "0.1em", ...muted }}>
          DataRoot · Context infrastructure for humans + agents
        </span>
      </footer>
    </div>
  );
}
