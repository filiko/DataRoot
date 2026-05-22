import { useMemo, useState, type CSSProperties } from "react";
import { FileText, Sparkles, Search, Loader2 } from "lucide-react";
import { DEMO_QUESTIONS, type DemoQuestion } from "./demoData";
import { API } from "../../config/api";

const ROOT = "#91b88e";
const ROOT_LIGHT = "rgba(239,232,213,0.07)";
const GOLD = "#d7b46a";
const INK = "#efe8d5";
const MUTED = "rgba(239,232,213,0.55)";
const LINE = "rgba(239,232,213,0.18)";
const PAPER = "#1d2b1d";
const PANEL = "#253325";
const ERR = "#e08a8a";

const LABEL: CSSProperties = {
  color: MUTED,
  fontSize: 10,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  fontFamily: "monospace",
};

export function AskPanel() {
  const [active, setActive] = useState(0);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // When set, a user-typed question is shown instead of a preset.
  const [freeAnswer, setFreeAnswer] = useState<DemoQuestion | null>(null);

  const q = freeAnswer ?? DEMO_QUESTIONS[active];
  const pathText = useMemo(() => q.sources.map((s) => s.file).join(" → "), [q]);

  async function submitQuery() {
    const text = query.trim();
    if (!text || loading) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(API.ask(), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: text }),
      });
      if (!res.ok) throw new Error(await res.text().catch(() => "Request failed"));
      const data = (await res.json()) as Omit<DemoQuestion, "question">;
      setFreeAnswer({ question: text, ...data });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Could not get an answer");
    } finally {
      setLoading(false);
    }
  }

  function selectPreset(i: number) {
    setActive(i);
    setFreeAnswer(null);
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", background: PANEL, display: "flex", flexDirection: "column" }}>
      {/* Free-form Ask */}
      <div style={{ padding: "12px 14px", borderBottom: `1px solid ${LINE}`, background: PAPER }}>
        <p style={{ ...LABEL, margin: "0 0 7px" }}>Ask your own question</p>
        <div style={{ display: "flex", gap: 6 }}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submitQuery()}
            placeholder="Ask about the permit data…"
            disabled={loading}
            style={{
              flex: 1,
              minWidth: 0,
              background: ROOT_LIGHT,
              color: INK,
              border: `1px solid ${LINE}`,
              borderRadius: 5,
              padding: "7px 9px",
              fontSize: 12,
              outline: "none",
            }}
          />
          <button
            type="button"
            onClick={submitQuery}
            disabled={loading || !query.trim()}
            style={{
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 34,
              background: ROOT,
              color: "#141512",
              border: "none",
              borderRadius: 5,
              cursor: loading || !query.trim() ? "default" : "pointer",
              opacity: loading || !query.trim() ? 0.5 : 1,
            }}
            aria-label="Ask"
          >
            {loading ? <Loader2 size={14} className="animate-spin" /> : <Search size={14} />}
          </button>
        </div>
        {error && (
          <p style={{ color: ERR, fontSize: 11, margin: "7px 0 0", lineHeight: 1.4 }}>{error}</p>
        )}
      </div>

      {/* Preset question list */}
      <div style={{ borderBottom: `1px solid ${LINE}`, background: PAPER }}>
        <p style={{ ...LABEL, margin: "10px 14px 4px" }}>Demo questions</p>
        {DEMO_QUESTIONS.map((item, i) => {
          const on = !freeAnswer && i === active;
          return (
            <button
              key={item.question}
              type="button"
              onClick={() => selectPreset(i)}
              style={{
                width: "100%",
                textAlign: "left",
                display: "grid",
                gridTemplateColumns: "28px 1fr",
                gap: 10,
                minHeight: 64,
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
        {/* Question being answered */}
        <div style={{
          display: "flex", alignItems: "flex-start", gap: 7,
          color: INK, border: `1px solid ${LINE}`, borderRadius: 6,
          padding: "8px 10px", background: ROOT_LIGHT, marginBottom: 12,
        }}>
          <Search size={13} style={{ opacity: 0.6, flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
          <span style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.45 }}>{q.question}</span>
        </div>

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
        <p style={{ color: INK, fontSize: 13.5, fontWeight: 700, lineHeight: 1.4, margin: "0 0 8px" }}>
          {q.headline}
        </p>

        {/* Answer */}
        <p style={{ color: MUTED, fontSize: 12, lineHeight: 1.6, margin: "0 0 14px" }}>
          {q.answer}
        </p>

        {/* Source trail — only when the answer actually cites data */}
        {q.sources.length > 0 && (
          <>
            <p style={{ ...LABEL, margin: "0 0 8px" }}>Source trail</p>
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
          </>
        )}
      </div>
    </div>
  );
}
