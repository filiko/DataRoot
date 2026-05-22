import { useMemo, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  Network,
  Search,
  Sparkles,
} from "lucide-react";
import { DEMO_QUESTIONS } from "./demoData";

// Chalkboard palette — matches the DataRoot landing + workspace strip.
const BG = "#253325";
const CARD = "#1d2b1d";
const CHALK = "#efe8d5";
const DIM = "rgba(239,232,213,0.55)";
const FAINT_TXT = "rgba(239,232,213,0.40)";
const EDGE = "rgba(239,232,213,0.30)";
const FAINT_BG = "rgba(239,232,213,0.06)";
const GOLD = "#d7b46a";

interface Props {
  onOpenWorkspace: () => void;
}

export function AskView({ onOpenWorkspace }: Props) {
  const [active, setActive] = useState(0);
  const q = DEMO_QUESTIONS[active];
  const pathText = useMemo(
    () => q.sources.map((s) => s.file).join("  ->  "),
    [q],
  );

  return (
    <div style={{ flex: 1, overflowY: "auto", background: BG }}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "36px 28px 56px" }}>
        {/* Header */}
        <p
          style={{
            color: DIM,
            fontSize: 12,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            fontFamily: "monospace",
            margin: 0,
          }}
        >
          DataRoot · Live Ask
        </p>
        <h1
          style={{
            color: CHALK,
            fontSize: 30,
            fontWeight: 800,
            letterSpacing: "-0.01em",
            margin: "10px 0 8px",
          }}
        >
          Ask a question. Get a cited answer.
        </h1>
        <p style={{ color: DIM, fontSize: 15, lineHeight: 1.6, margin: 0, maxWidth: 620 }}>
          Every answer is traced back through the linked source files — no
          guessing, no rebuilding context. Pick a question to see the trail.
        </p>

        {/* Two-column workspace */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "340px 1fr",
            gap: 20,
            marginTop: 28,
          }}
        >
          {/* Question list */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <p
              style={{
                color: FAINT_TXT,
                fontSize: 11,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                fontFamily: "monospace",
                margin: "0 0 2px",
              }}
            >
              Demo questions
            </p>
            {DEMO_QUESTIONS.map((item, i) => {
              const on = i === active;
              return (
                <button
                  key={item.question}
                  type="button"
                  onClick={() => setActive(i)}
                  style={{
                    textAlign: "left",
                    cursor: "pointer",
                    background: on ? CHALK : CARD,
                    color: on ? BG : CHALK,
                    border: `2px ${on ? "solid" : "dashed"} ${on ? CHALK : EDGE}`,
                    borderRadius: 6,
                    padding: "14px 16px",
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    transition: "background .12s, color .12s",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 13,
                      fontWeight: 700,
                      opacity: on ? 0.7 : 0.45,
                    }}
                  >
                    0{i + 1}
                  </span>
                  <span style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.45 }}>
                    {item.question}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Answer panel */}
          <div
            style={{
              background: CARD,
              border: `2px dashed ${EDGE}`,
              borderRadius: 8,
              padding: "22px 24px",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Query line */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                color: CHALK,
                border: `1px solid ${EDGE}`,
                borderRadius: 6,
                padding: "10px 14px",
                background: FAINT_BG,
              }}
            >
              <Search size={16} style={{ opacity: 0.6, flexShrink: 0 }} aria-hidden="true" />
              <span style={{ fontSize: 14, fontWeight: 600 }}>{q.question}</span>
            </div>

            {/* Confidence pill */}
            <div style={{ marginTop: 16 }}>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  background: "rgba(215,180,106,0.14)",
                  color: GOLD,
                  border: `1px solid rgba(215,180,106,0.4)`,
                  borderRadius: 999,
                  padding: "3px 12px",
                  fontSize: 12,
                  fontWeight: 700,
                  fontFamily: "monospace",
                }}
              >
                <Sparkles size={12} aria-hidden="true" />
                {q.confidence}
              </span>
            </div>

            {/* Answer */}
            <h2
              style={{
                color: CHALK,
                fontSize: 19,
                fontWeight: 800,
                lineHeight: 1.4,
                margin: "14px 0 8px",
              }}
            >
              {q.headline}
            </h2>
            <p style={{ color: DIM, fontSize: 14.5, lineHeight: 1.7, margin: 0 }}>
              {q.answer}
            </p>

            {/* Source trail */}
            <p
              style={{
                color: FAINT_TXT,
                fontSize: 11,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                fontFamily: "monospace",
                margin: "22px 0 10px",
              }}
            >
              Source trail
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {q.sources.map((s, i) => {
                const last = i === q.sources.length - 1;
                return (
                  <div
                    key={s.file + i}
                    style={{
                      display: "flex",
                      gap: 12,
                      alignItems: "flex-start",
                      border: `1px solid ${EDGE}`,
                      borderRadius: 6,
                      padding: "11px 14px",
                      background: FAINT_BG,
                    }}
                  >
                    <span
                      style={{
                        width: 22,
                        height: 22,
                        flexShrink: 0,
                        borderRadius: "50%",
                        background: last ? GOLD : "transparent",
                        color: last ? BG : CHALK,
                        border: `1px solid ${last ? GOLD : EDGE}`,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        fontWeight: 700,
                        fontFamily: "monospace",
                      }}
                    >
                      {i + 1}
                    </span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                        }}
                      >
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            color: CHALK,
                            fontFamily: "monospace",
                            fontSize: 13,
                            fontWeight: 700,
                          }}
                        >
                          <FileText size={13} aria-hidden="true" />
                          {s.file}
                        </span>
                        <span
                          style={{
                            color: last ? GOLD : FAINT_TXT,
                            fontSize: 10,
                            textTransform: "uppercase",
                            letterSpacing: "0.1em",
                            fontFamily: "monospace",
                          }}
                        >
                          {s.role}
                        </span>
                      </div>
                      <div
                        style={{
                          color: DIM,
                          fontSize: 13,
                          lineHeight: 1.55,
                          marginTop: 3,
                        }}
                      >
                        {s.detail}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Path readout */}
            <div
              style={{
                marginTop: 12,
                color: FAINT_TXT,
                fontFamily: "monospace",
                fontSize: 11.5,
                letterSpacing: "0.02em",
                overflowWrap: "anywhere",
              }}
            >
              {pathText}
            </div>

            {/* Open DataCanopy */}
            <button
              type="button"
              onClick={onOpenWorkspace}
              style={{
                marginTop: 20,
                alignSelf: "flex-start",
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: CHALK,
                color: BG,
                border: "none",
                borderRadius: 6,
                padding: "10px 18px",
                fontSize: 13,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              <Network size={15} aria-hidden="true" />
              Open DataCanopy
              <ArrowRight size={15} aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Footnote */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginTop: 22,
            color: FAINT_TXT,
            fontSize: 12.5,
          }}
        >
          <CheckCircle2 size={14} aria-hidden="true" />
          Linked from real City of Austin permit, plan-review, and code-enforcement data.
        </div>
      </div>
    </div>
  );
}
