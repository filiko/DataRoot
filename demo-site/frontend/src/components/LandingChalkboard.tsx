import React, { useEffect, useRef, useState } from "react";
import type { PenFile } from "../types/pen";
import { loadDemoProject } from "./datademo/loadDemo";
import { WaitlistSection } from "./WaitlistSection";

const FEATURES = [
  { sym: "⬡", title: "Reads any files",             body: "Point DataRoot at spreadsheets, exports, JSON, markdown, or a whole repo. No schema or config needed." },
  { sym: "⊡", title: "Finds the links",             body: "Repeated IDs, foreign keys, and shared addresses become connections — scattered files turn into one graph." },
  { sym: "⌖", title: "Answers with a source trail", body: "Every answer cites the exact files and rows it came from. Proof, not guesses." },
  { sym: "⇥", title: "Built for agents + humans",   body: "The same knowledge base serves your AI agents and your team — context that never has to be re-explained." },
  { sym: "⊛", title: "Canopy view",                 body: "See the whole project as a live map of tables and connections — explore it, edit it, keep it in sync." },
  { sym: "◈", title: "One source of truth",         body: "When the FAQ falls short, the answer is already linked and waiting — no day-long hunt across departments." },
];

interface Props {
  onIngested: (projectId: string, pen: PenFile) => void;
  onStartBlank: (projectId: string, pen: PenFile) => void;
  onLoadExample: (projectId: string, pen: PenFile) => void;
  onLoadNexusExercise: (projectId: string, pen: PenFile) => void;
  onLoadClaudeEval: (projectId: string, pen: PenFile) => void;
  onLoadRepoAnalysis: (projectId: string, pen: PenFile) => void;
}

const BG          = "#253325";
const CARD        = "#1d2b1d";
const CHALK       = "#efe8d5";
const CHALK_DIM   = "rgba(239,232,213,0.55)";
const CHALK_EDGE  = "rgba(239,232,213,0.30)";

const tx  = (extra?: React.CSSProperties): React.CSSProperties => ({ color: CHALK,     ...extra });
const dim = (extra?: React.CSSProperties): React.CSSProperties => ({ color: CHALK_DIM, ...extra });

const card: React.CSSProperties = { backgroundColor: CARD, border: `2px dashed ${CHALK_EDGE}`, borderRadius: 4 };
const btnSolid: React.CSSProperties = { backgroundColor: CHALK, color: BG, border: "none", borderRadius: 4, fontWeight: 700, cursor: "pointer", fontSize: 15 };
const btnDash: React.CSSProperties  = { backgroundColor: "transparent", color: CHALK, border: `2px dashed ${CHALK_EDGE}`, borderRadius: 4, cursor: "pointer", fontSize: 14 };

function ChalkSymbols() {
  return (
    <div className="absolute inset-0 pointer-events-none select-none overflow-hidden">
      {([
        ["✦", "8%",  "4%",  20, 0.09, -12],
        ["◇", "16%", "91%", 24, 0.07,   8],
        ["○", "42%", "2%",  18, 0.08,   0],
        ["✧", "63%", "95%", 16, 0.09,  15],
        ["△", "78%", "6%",  22, 0.07,  -6],
        ["∷", "87%", "88%", 18, 0.08,   0],
        ["—", "30%", "96%", 20, 0.07, -45],
        ["◎", "54%", "3%",  16, 0.07,   0],
        ["✕", "72%", "93%", 14, 0.08,  20],
      ] as const).map(([s, top, left, size, op, rot], i) => (
        <span key={i} style={{ position: "absolute", top, left, fontSize: size, opacity: op, color: CHALK, transform: `rotate(${rot}deg)`, fontFamily: "serif" }}>{s}</span>
      ))}
    </div>
  );
}

export function LandingChalkboard({
  onIngested: _onIngested, onStartBlank: _onStartBlank, onLoadExample, onLoadNexusExercise: _onNexus, onLoadClaudeEval: _onClaude, onLoadRepoAnalysis: _onRepo,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);
  const waitlistRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Caveat:wght@600;700&display=swap";
    document.head.appendChild(link);
    return () => { document.head.removeChild(link); };
  }, []);

  return (
    <div style={{ backgroundColor: BG, minHeight: "100%", overflowY: "auto" }}>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden" style={{ padding: "80px 24px 64px" }}>
        <ChalkSymbols />
        <a href="/docs" style={{
          position: "absolute", top: 22, right: 24, zIndex: 2,
          color: CHALK, textDecoration: "none", fontSize: 13, fontWeight: 700,
          border: `1px dashed ${CHALK_EDGE}`, borderRadius: 4, padding: "8px 14px",
          background: "rgba(29,43,29,0.72)",
        }}>
          Read the docs
        </a>
        <div style={{ maxWidth: 700, margin: "0 auto", position: "relative", textAlign: "center" }}>
          <div style={{ borderTop: `1px dashed ${CHALK_EDGE}`, marginBottom: 32 }} />
          <p style={dim({ fontSize: 12, letterSpacing: "0.18em", textTransform: "uppercase", marginBottom: 28, fontFamily: "monospace" })}>
            context infrastructure for humans + agents
          </p>
          <h1 style={{ fontFamily: "'Caveat', cursive", fontSize: "clamp(54px, 8vw, 90px)", fontWeight: 700, color: CHALK, lineHeight: 1.05, marginBottom: 24, letterSpacing: "-0.01em" }}>
            Give every answer<br />a source trail.
          </h1>
          <p style={dim({ fontSize: 18, lineHeight: 1.7, maxWidth: 500, margin: "0 auto 40px" })}>
            Point DataRoot at your files. It links them into a traversable knowledge base — so agents and teams find the right context instead of rebuilding it in every chat.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <button onClick={runDemo} disabled={loading} style={{ ...btnSolid, padding: "12px 28px" }}>
              {loading ? "Loading…" : "Run the demo →"}
            </button>
            <button onClick={() => waitlistRef.current?.scrollIntoView({ behavior: "smooth" })} style={{ ...btnDash, padding: "12px 28px" }}>
              Join Waitlist
            </button>
          </div>
          {error && (
            <div style={{ marginTop: 16, border: "1px dashed #c0392b", borderRadius: 4, padding: "10px 16px", color: "#e07070", fontSize: 13 }}>
              {error}
            </div>
          )}
          <div style={{ borderBottom: `1px dashed ${CHALK_EDGE}`, marginTop: 56 }} />
        </div>
      </section>

      {/* ── Features ── */}
      <section style={{ padding: "56px 24px", maxWidth: 900, margin: "0 auto" }}>
        <p style={dim({ fontSize: 12, letterSpacing: "0.16em", textTransform: "uppercase", fontFamily: "monospace", textAlign: "center", marginBottom: 40 })}>
          what it does
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 20 }}>
          {FEATURES.map((f) => (
            <div key={f.title} style={{ ...card, padding: "26px 22px" }}>
              <div style={{ fontFamily: "monospace", fontSize: 24, color: CHALK, opacity: 0.45, marginBottom: 14 }}>{f.sym}</div>
              <div style={tx({ fontWeight: 700, fontSize: 15, marginBottom: 10 })}>{f.title}</div>
              <div style={dim({ fontSize: 14, lineHeight: 1.65 })}>{f.body}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Steps ── */}
      <section style={{ backgroundColor: CARD, padding: "56px 24px", borderTop: `1px dashed ${CHALK_EDGE}`, borderBottom: `1px dashed ${CHALK_EDGE}` }}>
        <div style={{ maxWidth: 700, margin: "0 auto" }}>
          <p style={dim({ fontSize: 12, letterSpacing: "0.16em", textTransform: "uppercase", fontFamily: "monospace", textAlign: "center", marginBottom: 40 })}>
            how it works
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 36 }}>
            {[
              { n: "01", title: "Ingest", body: "Drop in files — spreadsheets, exports, a whole repo. DataRoot reads them all." },
              { n: "02", title: "Link",   body: "Repeated IDs and shared addresses become connections — files turn into a graph." },
              { n: "03", title: "Ask",    body: "Agents and teams ask questions and get answers with a full cited source trail." },
            ].map((s) => (
              <div key={s.n} style={{ textAlign: "center" }}>
                <div style={{ fontFamily: "'Caveat', cursive", fontSize: 48, fontWeight: 700, color: CHALK, opacity: 0.15, lineHeight: 1, marginBottom: 10 }}>{s.n}</div>
                <div style={tx({ fontWeight: 700, fontSize: 16, marginBottom: 8 })}>{s.title}</div>
                <div style={dim({ fontSize: 14, lineHeight: 1.65 })}>{s.body}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Waitlist ── */}
      <WaitlistSection dark ref={waitlistRef} />

      {/* ── Footer ── */}
      <footer style={{ borderTop: `1px dashed ${CHALK_EDGE}`, padding: "28px 24px", textAlign: "center" }}>
        <span style={dim({ fontSize: 12, fontFamily: "monospace", letterSpacing: "0.1em" })}>
          DataRoot · Context infrastructure for humans + agents
        </span>
      </footer>
    </div>
  );
}
