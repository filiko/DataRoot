import type { PenFile } from "../types/pen";
import { LandingChalkboard } from "./LandingChalkboard";
import { LandingMinimal } from "./LandingMinimal";
import { useAppTheme } from "../context/ThemeContext";

interface Props {
  onIngested: (projectId: string, pen: PenFile) => void;
  onStartBlank: (projectId: string, pen: PenFile) => void;
  onLoadExample: (projectId: string, pen: PenFile) => void;
  onLoadMorSat0Exercise: (projectId: string, pen: PenFile) => void;
  onLoadClaudeEval: (projectId: string, pen: PenFile) => void;
  onLoadRepoAnalysis: (projectId: string, pen: PenFile) => void;
}

export function LandingPage(props: Props) {
  const { theme, setTheme } = useAppTheme();
  const isDark = theme.id === "chalkboard";
  return (
    <div style={{ position: "relative" }}>
      {theme.id === "chalkboard"
        ? <LandingChalkboard {...props} />
        : <LandingMinimal {...props} />}
      <div
        style={{
          position: "fixed",
          bottom: 24,
          right: 24,
          zIndex: 40,
          display: "flex",
          borderRadius: 4,
          overflow: "hidden",
          background: isDark ? "#1d2b1d" : "#ffffff",
          border: isDark ? "2px dashed rgba(239,232,213,0.30)" : "1px solid #d1d5db",
        }}
      >
        {([["chalkboard", "✦ Chalkboard"], ["minimal", "○ Technical Minimal"]] as const).map(([id, label], i) => (
          <button
            key={id}
            onClick={() => setTheme(id)}
            style={{
              padding: "9px 16px",
              fontSize: 12,
              fontFamily: "monospace",
              border: "none",
              borderRight: i < 1 ? (isDark ? "1px dashed rgba(239,232,213,0.30)" : "1px solid #d1d5db") : "none",
              cursor: "pointer",
              background: theme.id === id
                ? (isDark ? "#efe8d5" : "#18181b")
                : "transparent",
              color: theme.id === id
                ? (isDark ? "#253325" : "#ffffff")
                : (isDark ? "rgba(239,232,213,0.55)" : "#6b7280"),
              fontWeight: theme.id === id ? 700 : 400,
              transition: "background-color .15s, color .15s",
            }}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
