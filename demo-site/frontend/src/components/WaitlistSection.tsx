import React, { forwardRef, useState } from "react";

interface Props {
  dark?: boolean;
}

export const WaitlistSection = forwardRef<HTMLDivElement, Props>(function WaitlistSection(
  { dark = false },
  ref,
) {
  const [name, setName]       = useState("");
  const [email, setEmail]     = useState("");
  const [url, setUrl]         = useState("");
  const [msg, setMsg]         = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone]       = useState(false);
  const [error, setError]     = useState<string | null>(null);

  // Palette variants
  const bg      = dark ? "transparent"               : "transparent";
  const label   = dark ? "rgba(239,232,213,0.55)"    : "#5f655a";
  const ink     = dark ? "#efe8d5"                   : "#141512";
  const border  = dark ? "rgba(239,232,213,0.30)"    : "rgba(38,67,52,0.18)";
  const inputBg = dark ? "rgba(0,0,0,0.18)"          : "#fffdf6";
  const btnBg   = dark ? "#efe8d5"                   : "#264334";
  const btnFg   = dark ? "#253325"                   : "#f5f0df";
  const errClr  = dark ? "#e07070"                   : "#c0392b";
  const head    = dark ? "#efe8d5"                   : "#141512";
  const sub     = dark ? "rgba(239,232,213,0.55)"    : "#5f655a";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !email.trim()) return;
    setLoading(true); setError(null);
    try {
      const res = await fetch("/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), email: email.trim(), project_url: url.trim(), message: msg.trim() }),
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => "Request failed");
        throw new Error(txt);
      }
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle: React.CSSProperties = {
    width: "100%", boxSizing: "border-box",
    border: `1px solid ${border}`, borderRadius: 6,
    background: inputBg, color: ink,
    padding: "10px 12px", fontSize: 14,
    fontFamily: "inherit", outline: "none",
  };
  const labelStyle: React.CSSProperties = {
    display: "block", marginBottom: 6,
    fontSize: 12, fontWeight: 700,
    letterSpacing: "0.1em", textTransform: "uppercase",
    fontFamily: "monospace", color: label,
  };

  return (
    <section
      ref={ref}
      style={{ padding: "72px 24px", maxWidth: 520, margin: "0 auto", background: bg }}
    >
      <p style={{
        margin: "0 0 6px", textAlign: "center",
        fontSize: 12, fontWeight: 800, letterSpacing: "0.16em",
        textTransform: "uppercase", fontFamily: "monospace", color: label,
      }}>
        Early access
      </p>
      <h2 style={{ margin: "0 0 8px", textAlign: "center", fontSize: "clamp(28px,4vw,40px)", color: head, lineHeight: 1.1 }}>
        Join the waitlist
      </h2>
      <p style={{ margin: "0 0 36px", textAlign: "center", fontSize: 15, color: sub, lineHeight: 1.55 }}>
        We're onboarding teams selectively. Drop your info and we'll reach out when there's a spot.
      </p>

      {done ? (
        <div style={{
          border: `1px solid ${border}`, borderRadius: 8,
          padding: "28px 24px", textAlign: "center",
          background: dark ? "rgba(239,232,213,0.06)" : "rgba(38,67,52,0.05)",
        }}>
          <div style={{ fontSize: 28, marginBottom: 10 }}>✓</div>
          <p style={{ margin: 0, fontSize: 16, fontWeight: 700, color: ink }}>You're on the list.</p>
          <p style={{ margin: "8px 0 0", fontSize: 14, color: label }}>We'll be in touch soon.</p>
        </div>
      ) : (
        <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Name *</label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ada Lovelace"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={labelStyle}>Email *</label>
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ada@example.com"
                style={inputStyle}
              />
            </div>
          </div>

          <div>
            <label style={labelStyle}>Project / org URL</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="github.com/your/repo"
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>What are you building?</label>
            <textarea
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              rows={3}
              placeholder="A few sentences about your use case…"
              style={{ ...inputStyle, resize: "vertical", minHeight: 72 }}
            />
          </div>

          {error && (
            <div style={{ border: `1px solid ${errClr}`, borderRadius: 6, padding: "10px 14px", color: errClr, fontSize: 13 }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !name.trim() || !email.trim()}
            style={{
              padding: "13px 28px", borderRadius: 7, border: "none",
              background: btnBg, color: btnFg,
              fontSize: 15, fontWeight: 700, cursor: "pointer",
              opacity: loading || !name.trim() || !email.trim() ? 0.55 : 1,
              transition: "opacity .15s",
            }}
          >
            {loading ? "Sending…" : "Request access →"}
          </button>
        </form>
      )}
    </section>
  );
});
