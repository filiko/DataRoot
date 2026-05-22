import { useMemo, useState } from "react";
import { FileText, Sparkles } from "lucide-react";
import { DEMO_QUESTIONS } from "./demoData";

const ROOT = "#91b88e";
const ROOT_LIGHT = "rgba(239,232,213,0.07)";
const GOLD = "#d7b46a";
const INK = "#efe8d5";
const MUTED = "rgba(239,232,213,0.55)";
const LINE = "rgba(239,232,213,0.18)";
const PAPER = "#1d2b1d";
const PANEL = "#253325";

export function AskPanel() {
  const [active, setActive] = useState(0);
  const q = DEMO_QUESTIONS[active];
  const pathText = useMemo(() => q.sources.map((s) => s.file).join(" → "), [q]);

  return (
    <div style={{ height: "100%", overflowY: "auto", background: PANEL, display: "flex", flexDirection: "column" }}>
      {/* Question list */}
      <div style={{ borderBottom: `1px solid ${LINE}`, background: PAPER }}>
        {DEMO_QUESTIONS.map((item, i) => {
          const on = i === active;
          return (
            <button
              key={item.question}
              type="button"
              onClick={() => setActive(i)}
              style={{
                width: "100%",
                textAlign: "left",
                display: "grid",
                gridTemplateColumns: "28px 1fr",
                gap: 10,
                minHeight: 72,
                padding: "12px 14px",
                border: 0,
                borderBottom: `1px solid ${LINE}`,
                background: on ? ROOT : "transparent",
                color: on ? "#f5f0df" : MUTED,
                cursor: "pointer",
              }}
            >
              <span style={{
                fontFamily: "monospace",
                fontSize: 11,
                fontWeight: 900,
                color: GOLD,
                paddingTop: 1,
              }}>
                0{i + 1}
              </span>
              <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.45 }}>
                {item.question}
              </span>
            </button>
          );
        })}
      </div>

      {/* Answer area */}
      <div style={{ padding: "16px 14px", flex: 1 }}>
        {/* Confidence pill */}
        <span style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          background: "rgba(215,180,106,0.14)",
          color: GOLD,
          border: `1px solid rgba(215,180,106,0.4)`,
          borderRadius: 999,
          padding: "2px 10px",
          fontSize: 11,
          fontWeight: 700,
          fontFamily: "monospace",
          marginBottom: 10,
        }}>
          <Sparkles size={10} aria-hidden="true" />
          {q.confidence}
        </span>

        {/* Headline */}
        <p style={{ color: INK, fontSize: 13.5, fontWeight: 700, lineHeight: 1.4, margin: "0 0 10px" }}>
          {q.headline}
        </p>

        {/* Source trail */}
        <p style={{
          color: MUTED,
          fontSize: 10,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          fontFamily: "monospace",
          margin: "0 0 8px",
        }}>
          Source trail
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {q.sources.map((s, i) => {
            const last = i === q.sources.length - 1;
            return (
              <div key={s.file + i} style={{
                display: "flex",
                gap: 8,
                alignItems: "flex-start",
                border: `1px solid ${LINE}`,
                borderRadius: 6,
                padding: "8px 10px",
                background: last ? "rgba(215,180,106,0.06)" : ROOT_LIGHT,
              }}>
                <span style={{
                  width: 20,
                  height: 20,
                  flexShrink: 0,
                  borderRadius: "50%",
                  background: last ? GOLD : "rgba(145,184,142,0.2)",
                  color: last ? "#141512" : ROOT,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 11,
                  fontWeight: 900,
                  fontFamily: "monospace",
                }}>
                  {i + 1}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <span style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      color: ROOT, fontFamily: "monospace", fontSize: 11.5, fontWeight: 700,
                    }}>
                      <FileText size={11} aria-hidden="true" />
                      {s.file}
                    </span>
                    <span style={{
                      color: last ? GOLD : MUTED,
                      fontSize: 9.5,
                      textTransform: "uppercase",
                      letterSpacing: "0.1em",
                      fontFamily: "monospace",
                    }}>
                      {s.role}
                    </span>
                  </div>
                  <div style={{ color: MUTED, fontSize: 11.5, lineHeight: 1.5, marginTop: 2 }}>
                    {s.detail}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Path readout */}
        <div style={{
          marginTop: 10,
          color: MUTED,
          fontFamily: "monospace",
          fontSize: 10.5,
          lineHeight: 1.5,
          overflowWrap: "anywhere",
          borderTop: `1px solid ${LINE}`,
          paddingTop: 10,
        }}>
          {pathText}
        </div>
      </div>
    </div>
  );
}
