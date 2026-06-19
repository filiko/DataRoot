import type { DemoProject } from "./datademo/loadDemo";

interface Props {
  activeDemoId: string;
  demos: DemoProject[];
  onSwitch: (demo: DemoProject) => void;
  loading?: boolean;
  label?: string;   // bar label (default "Demo")
  bottom?: number;  // distance from bottom (default 20) — lets bars stack
}

const BG    = "#1d2b1d";
const CHALK = "#efe8d5";
const GOLD  = "#d7b46a";
const DIM   = "rgba(239,232,213,0.45)";
const EDGE  = "rgba(239,232,213,0.22)";

export function DemoSwitcher({ activeDemoId, demos, onSwitch, loading, label = "Demo", bottom = 20 }: Props) {
  return (
    <div style={{
      position: "absolute",
      bottom,
      left: "50%",
      transform: "translateX(-50%)",
      zIndex: 20,
      display: "flex",
      alignItems: "center",
      gap: 0,
      maxWidth: "92vw",
      overflowX: "auto",
      background: BG,
      border: `1px solid ${EDGE}`,
      borderRadius: 8,
      boxShadow: "0 4px 24px rgba(0,0,0,0.35)",
      opacity: loading ? 0.7 : 1,
      pointerEvents: loading ? "none" : "auto",
    }}>
      <span style={{
        padding: "7px 10px 7px 12px",
        fontSize: 10,
        fontFamily: "monospace",
        fontWeight: 700,
        letterSpacing: "0.12em",
        textTransform: "uppercase",
        color: DIM,
        borderRight: `1px solid ${EDGE}`,
        whiteSpace: "nowrap",
        position: "sticky",
        left: 0,
        background: BG,
      }}>
        {label}
      </span>
      {demos.map((demo, i) => {
        const active = demo.id === activeDemoId;
        return (
          <button
            key={demo.id}
            onClick={() => !active && onSwitch(demo)}
            style={{
              padding: "7px 14px",
              fontSize: 12,
              fontFamily: "monospace",
              fontWeight: active ? 700 : 500,
              background: active ? "rgba(215,180,106,0.18)" : "transparent",
              color: active ? GOLD : DIM,
              border: "none",
              borderRight: i < demos.length - 1 ? `1px solid ${EDGE}` : "none",
              cursor: active ? "default" : "pointer",
              transition: "background .15s, color .15s",
              whiteSpace: "nowrap",
            }}
            onMouseEnter={e => { if (!active) e.currentTarget.style.color = CHALK; }}
            onMouseLeave={e => { if (!active) e.currentTarget.style.color = DIM; }}
          >
            {demo.label}
          </button>
        );
      })}
    </div>
  );
}
