import React, { useEffect, useRef, useState } from "react";
import type { PenFile } from "../types/pen";
import { loadDemoProject } from "./datademo/loadDemo";
import { WaitlistSection } from "./WaitlistSection";

const GRIDLY_QUESTIONS = [
  {
    question: "Why is this client's permit review still delayed?",
    answer: "DataRoot links the permit, plan review, code complaint, and task owner into one cited source trail.",
    sources: ["permits.csv", "plan_reviews.csv", "code_complaints.csv", "code_tasks.csv"],
  },
  {
    question: "Which department owns the open issue blocking this address?",
    answer: "The graph follows the shared address into the complaint record and returns the owning department with evidence.",
    sources: ["address match", "code_complaints.csv", "department field"],
  },
  {
    question: "What stage is the plan review for this project at?",
    answer: "The answer is traced from the project record through the permit ID into the current review status.",
    sources: ["project_id", "permits.csv", "plan_reviews.csv"],
  },
];

const CANOPY_NODES = [
  { label: "Ask", type: "Question", x: 8, y: 34 },
  { label: "Permits", type: "CSV", x: 28, y: 18 },
  { label: "Reviews", type: "JSON", x: 47, y: 48 },
  { label: "Complaints", type: "Docs", x: 66, y: 23 },
  { label: "Cited answer", type: "Output", x: 82, y: 56 },
];
const FEATURES = [
  { sym: "⬡", title: "Reads any files",             body: "Point DataRoot at spreadsheets, exports, JSON, markdown, or a whole repo. No schema or config needed." },
  { sym: "⊡", title: "Finds the links",             body: "Repeated IDs, foreign keys, and shared addresses become connections — scattered files turn into one graph." },
  { sym: "⌖", title: "Answers with a source trail", body: "Every answer cites the exact files and rows it came from. Proof, not guesses." },
  { sym: "⇥", title: "Built for agents + humans",   body: "The same knowledge base serves your AI agents and your team — context that never has to be re-explained." },
  { sym: "⊛", title: "Canopy view",                 body: "See the whole project as a live map of tables and connections — explore it, edit it, keep it in sync." },
  { sym: "◈", title: "One source of truth",         body: "When the FAQ falls short, the answer is already linked and waiting — no day-long hunt across departments." },
];
const DEFAULT_DEMO_VIDEO = "/demo-media/dataroot-codebase-dfd-compressed.mp4";
const DEFAULT_DEMO_VIDEO_NAME = "Video Project 2.mp4";
const DEMO_SCREENSHOTS = [
  { src: "/demo-media/dataroot-dfd-created-2-small.png", label: "Repo parsing 01" },
  { src: "/demo-media/dataroot-dfd-created-1-small.png", label: "Repo parsing 02" },
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

function FeatureCarousel() {
  const [activeSlide, setActiveSlide] = useState(0);
  const [videoUrl, setVideoUrl] = useState(DEFAULT_DEMO_VIDEO);
  const [videoName, setVideoName] = useState(DEFAULT_DEMO_VIDEO_NAME);
  const [isUploadedVideo, setIsUploadedVideo] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const slides = ["What it does", "Ask speed", "Repo parsing"];
  const previousLabel = activeSlide === 0 ? "Repo parsing" : slides[(activeSlide + slides.length - 1) % slides.length];
  const nextLabel = activeSlide === 0 ? "Ask speed" : slides[(activeSlide + 1) % slides.length];

  const go = (direction: -1 | 1) => {
    setActiveSlide((current) => (current + direction + slides.length) % slides.length);
  };

  const handleVideo = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (isUploadedVideo) URL.revokeObjectURL(videoUrl);
    setVideoUrl(URL.createObjectURL(file));
    setVideoName(file.name);
    setIsUploadedVideo(true);
  };

  useEffect(() => {
    return () => {
      if (isUploadedVideo) URL.revokeObjectURL(videoUrl);
    };
  }, [isUploadedVideo, videoUrl]);

  return (
    <section style={{ padding: "12px 24px 42px", maxWidth: 960, margin: "0 auto" }}>
      <p style={dim({ fontSize: 12, letterSpacing: "0.16em", textTransform: "uppercase", fontFamily: "monospace", margin: "0 0 18px", textAlign: "center" })}>
        {slides[activeSlide]}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "112px minmax(0, 1fr) 112px", gap: 12, alignItems: "center" }}>
        <button type="button" onClick={() => go(-1)} aria-label={`Previous slide: ${previousLabel}`} style={{ ...btnDash, minHeight: 82, padding: "10px 8px", fontFamily: "monospace", fontSize: 12, display: "grid", placeItems: "center", gap: 4 }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>‹</span>
          <span>{previousLabel}</span>
        </button>

        <div style={{ ...card, padding: 18, minHeight: 400 }}>
          {activeSlide === 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 14 }}>
              {FEATURES.map((f) => (
                <div key={f.title} style={{ ...card, padding: "20px 18px", minHeight: 166 }}>
                  <div style={{ fontFamily: "monospace", fontSize: 23, color: CHALK, opacity: 0.48, marginBottom: 12 }}>{f.sym}</div>
                  <div style={tx({ fontWeight: 800, fontSize: 15, marginBottom: 9 })}>{f.title}</div>
                  <div style={dim({ fontSize: 13, lineHeight: 1.55 })}>{f.body}</div>
                </div>
              ))}
            </div>
          )}

          {activeSlide === 1 && (
            <div style={{ display: "grid", gap: 14 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <div>
                  <div style={tx({ fontWeight: 800, fontSize: 16, marginBottom: 4 })}>Speed of asking a question</div>
                </div>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  title="Upload codebase DFD recording"
                  style={{
                    width: 48,
                    height: 48,
                    flexShrink: 0,
                    borderRadius: "50%",
                    border: `2px dashed ${CHALK_EDGE}`,
                    background: "rgba(239,232,213,0.08)",
                    color: CHALK,
                    cursor: "pointer",
                    display: "grid",
                    placeItems: "center",
                    fontFamily: "monospace",
                    fontWeight: 900,
                    fontSize: 18,
                  }}
                >
                  +
                </button>
                <input ref={fileInputRef} type="file" accept="video/*" onChange={handleVideo} style={{ display: "none" }} />
              </div>
              <video src={videoUrl} controls style={{ width: "100%", maxHeight: 430, aspectRatio: "16 / 9", objectFit: "contain", background: "#111", borderRadius: 6, border: `1px dashed ${CHALK_EDGE}` }} />
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, minHeight: 24 }}>
                <span style={dim({ fontSize: 12, fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" })}>
                  {videoName}
                </span>
                {isUploadedVideo && (
                  <button
                    type="button"
                    onClick={() => {
                      URL.revokeObjectURL(videoUrl);
                      setVideoUrl(DEFAULT_DEMO_VIDEO);
                      setVideoName(DEFAULT_DEMO_VIDEO_NAME);
                      setIsUploadedVideo(false);
                      if (fileInputRef.current) fileInputRef.current.value = "";
                    }}
                    style={{ ...btnDash, padding: "5px 9px", fontSize: 12 }}
                  >
                    Reset
                  </button>
                )}
              </div>
            </div>
          )}

          {activeSlide === 2 && (
            <div style={{ display: "grid", gap: 14 }}>
              <div>
                <div style={tx({ fontWeight: 800, fontSize: 16, marginBottom: 4 })}>Repo parsing output</div>
                <div style={dim({ fontSize: 13, lineHeight: 1.45 })}>Screenshots from parsing a repo into a generated DFD.</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 14 }}>
                {DEMO_SCREENSHOTS.map((shot) => (
                  <a key={shot.src} href={shot.src} target="_blank" rel="noreferrer" style={{ display: "block", color: CHALK, textDecoration: "none" }}>
                    <img src={shot.src} alt={shot.label} style={{ width: "100%", aspectRatio: "16 / 9", objectFit: "cover", borderRadius: 6, border: `1px dashed ${CHALK_EDGE}`, display: "block" }} />
                    <span style={dim({ display: "block", marginTop: 6, fontSize: 12, fontFamily: "monospace" })}>{shot.label}</span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>

        <button type="button" onClick={() => go(1)} aria-label={`Next slide: ${nextLabel}`} style={{ ...btnDash, minHeight: 82, padding: "10px 8px", fontFamily: "monospace", fontSize: 12, display: "grid", placeItems: "center", gap: 4 }}>
          <span style={{ fontSize: 20, lineHeight: 1 }}>›</span>
          <span>{nextLabel}</span>
        </button>
      </div>

      <div style={{ display: "flex", justifyContent: "center", gap: 7, marginTop: 16 }}>
        {slides.map((label, index) => (
          <button
            key={label}
            type="button"
            onClick={() => setActiveSlide(index)}
            aria-label={`Show ${label}`}
            style={{
              width: index === activeSlide ? 24 : 8,
              height: 8,
              borderRadius: 999,
              border: `1px solid ${CHALK_EDGE}`,
              background: index === activeSlide ? CHALK : "transparent",
              cursor: "pointer",
              transition: "width .16s, background .16s",
            }}
          />
        ))}
      </div>
    </section>
  );
}
function GridlyProcessPreview() {
  return (
    <section style={{
      background: "#f7f5ee",
      color: "#141512",
      borderTop: `1px solid rgba(239,232,213,0.18)`,
      borderBottom: `1px solid rgba(38,67,52,0.18)`,
    }}>
      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "74px 24px 34px" }}>
        <div style={{ border: "1px solid rgba(38,67,52,0.18)", borderRadius: 8, overflow: "hidden", background: "#fffdf6", boxShadow: "0 24px 80px rgba(0,0,0,0.13)" }}>
          <div style={{ minHeight: 58, display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderBottom: "1px solid rgba(38,67,52,0.18)", background: "#fbf8ef" }}>
            {["Graph", "Sources", "Search", "Stores"].map((label) => (
              <span key={label} style={{ border: "1px solid rgba(38,67,52,0.18)", borderRadius: 8, background: "white", color: "#264334", padding: "9px 12px", fontSize: 12, fontWeight: 800 }}>
                {label}
              </span>
            ))}
          </div>
          <div style={{ position: "relative", height: 330, background: "radial-gradient(circle at 20% 30%, rgba(215,180,106,0.2), transparent 26%), linear-gradient(90deg, rgba(38,67,52,0.05) 1px, transparent 1px), linear-gradient(0deg, rgba(38,67,52,0.05) 1px, transparent 1px), #fffdf6", backgroundSize: "auto, 36px 36px, 36px 36px" }}>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}>
              <path d="M14 44 C 26 24, 34 29, 47 58 S 61 21, 72 34 S 80 69, 88 66" fill="none" stroke="rgba(38,67,52,0.36)" strokeWidth="0.55" vectorEffect="non-scaling-stroke" />
              <path d="M14 44 C 31 68, 45 60, 47 58 S 62 59, 72 34 S 82 38, 88 66" fill="none" stroke="rgba(215,180,106,0.55)" strokeWidth="0.45" vectorEffect="non-scaling-stroke" />
            </svg>
            {CANOPY_NODES.map((node, i) => (
              <div key={node.label} style={{
                position: "absolute", left: `${node.x}%`, top: `${node.y}%`, transform: "translate(-50%, -50%)",
                width: 132, minHeight: 66, display: "flex", flexDirection: "column", justifyContent: "center", gap: 6,
                border: "1px solid rgba(38,67,52,0.26)", borderRadius: 8,
                background: i === CANOPY_NODES.length - 1 ? "#264334" : "rgba(255,253,246,0.95)",
                padding: "11px 12px", boxShadow: "0 10px 30px rgba(38,67,52,0.13)",
              }}>
                <span style={{ color: "#d7b46a", fontSize: 11, fontWeight: 900, letterSpacing: "0.12em", textTransform: "uppercase" }}>{node.type}</span>
                <strong style={{ color: i === CANOPY_NODES.length - 1 ? "white" : "#264334", fontSize: 14, lineHeight: 1.14 }}>{node.label}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1180, margin: "0 auto", padding: "34px 24px 82px", display: "grid", gridTemplateColumns: "0.8fr 1.2fr", gap: 38, alignItems: "start" }}>
        <div>
          <p style={{ margin: 0, color: "#d7b46a", fontSize: 12, fontWeight: 800, letterSpacing: "0.16em", textTransform: "uppercase", fontFamily: "monospace" }}>
            source trail preview
          </p>
          <h2 style={{ margin: "10px 0 12px", color: "#141512", fontSize: "clamp(32px, 4.5vw, 58px)", lineHeight: 1 }}>
            From scattered context to a confident answer.
          </h2>
          <p style={{ margin: 0, color: "#5f655a", fontSize: 17, lineHeight: 1.58 }}>
            The key move is not just answering. It is showing the route through the files that produced the answer.
          </p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.1fr", border: "1px solid rgba(38,67,52,0.18)", borderRadius: 8, overflow: "hidden", background: "#fffdf6", boxShadow: "0 24px 80px rgba(0,0,0,0.13)" }}>
          <div style={{ display: "grid", alignContent: "start", borderRight: "1px solid rgba(38,67,52,0.18)", background: "#fbf8ef" }}>
            {GRIDLY_QUESTIONS.map((item, index) => (
              <div key={item.question} style={{ display: "grid", gridTemplateColumns: "34px 1fr", gap: 12, minHeight: 86, padding: 16, borderBottom: "1px solid rgba(38,67,52,0.18)", background: index === 0 ? "#264334" : "transparent", color: index === 0 ? "white" : "#5f655a" }}>
                <span style={{ color: "#d7b46a", fontFamily: "monospace", fontSize: 12, fontWeight: 900 }}>0{index + 1}</span>
                <strong style={{ fontSize: 14, lineHeight: 1.35 }}>{item.question}</strong>
              </div>
            ))}
          </div>
          <div style={{ padding: 22 }}>
            <span style={{ display: "inline-flex", border: "1px solid rgba(52,95,73,0.22)", borderRadius: 999, background: "rgba(145,184,142,0.16)", color: "#264334", padding: "7px 11px", fontSize: 12, fontWeight: 800 }}>
              4 linked sources
            </span>
            <h3 style={{ margin: "20px 0", color: "#141512", fontSize: "clamp(23px, 3vw, 34px)", lineHeight: 1.12 }}>
              {GRIDLY_QUESTIONS[0].answer}
            </h3>
            <div style={{ display: "grid", gap: 10 }}>
              {GRIDLY_QUESTIONS[0].sources.map((source, index) => (
                <div key={source} style={{ display: "flex", alignItems: "center", gap: 12, border: "1px solid rgba(38,67,52,0.18)", borderRadius: 8, padding: "11px 12px" }}>
                  <span style={{ width: 26, height: 26, display: "grid", placeItems: "center", borderRadius: 999, background: "rgba(145,184,142,0.2)", color: "#264334", fontSize: 12, fontWeight: 900 }}>{index + 1}</span>
                  <strong style={{ flex: 1, color: "#264334", fontSize: 14 }}>{source}</strong>
                  <small style={{ color: "#5f655a", fontSize: 12 }}>{index === GRIDLY_QUESTIONS[0].sources.length - 1 ? "final proof" : "linked context"}</small>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
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
      <section className="relative overflow-hidden" style={{ padding: "34px 24px 24px" }}>
        <ChalkSymbols />
        <div style={{ position: "absolute", top: 22, right: 24, zIndex: 3, display: "flex", gap: 14, alignItems: "center", fontFamily: "monospace", fontSize: 13, fontWeight: 700 }}>
          <button onClick={runDemo} disabled={loading} style={{ background: "transparent", border: "none", color: CHALK, cursor: "pointer", opacity: loading ? 0.55 : 1, padding: 0 }}>Demo</button>
          <a href="/docs" style={{ color: CHALK, textDecoration: "none" }}>Docs</a>
        </div>
        <div style={{ maxWidth: 700, margin: "0 auto", position: "relative", textAlign: "center" }}>
          <div style={{ borderTop: `1px dashed ${CHALK_EDGE}`, marginBottom: 24 }} />
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
          <div style={{ borderBottom: `1px dashed ${CHALK_EDGE}`, marginTop: 24 }} />
        </div>
      </section>
      {/* ── Features ── */}
      <FeatureCarousel />

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

      <GridlyProcessPreview />

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
