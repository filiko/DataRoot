import { useRef } from "react";
import { ChevronLeft, ChevronRight, Link2 } from "lucide-react";
import type { DemoProject } from "./datademo/loadDemo";
import { SEAM_ACCENT } from "../styles/diagramThemes";

interface Props {
  activeDemoId: string;
  demos: DemoProject[];
  onSwitch: (demo: DemoProject) => void;
  loading?: boolean;
}

// Palette matched to DemoSwitcher (dark chalkboard) for visual consistency.
const BG = "#1d2b1d";
const CHALK = "#efe8d5";
const GOLD = "#d7b46a";
const DIM = "rgba(239,232,213,0.55)";
const EDGE = "rgba(239,232,213,0.22)";

/**
 * NexusCarousel — the Nexus Agriscience diagram navigator.
 *
 * A *contained* horizontal carousel pinned inside the canvas: a sticky "Nexus Ag"
 * label, ‹ / › arrows that page a horizontally-scrollable strip of all diagrams,
 * plus a seam legend. Unlike the old bolt-on bar it never runs off-screen — it's
 * bounded to the canvas width and the overflow scrolls within the strip.
 */
export function NexusCarousel({ activeDemoId, demos, onSwitch, loading }: Props) {
  const stripRef = useRef<HTMLDivElement>(null);

  const page = (dir: number) => {
    const el = stripRef.current;
    if (!el) return;
    el.scrollBy({ left: dir * Math.max(240, el.clientWidth * 0.7), behavior: "smooth" });
  };

  const arrow = (dir: number, Icon: typeof ChevronLeft, aria: string) => (
    <button
      onClick={() => page(dir)}
      aria-label={aria}
      style={{
        flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        width: 32, height: 34,
        background: "transparent", color: DIM,
        border: "none", cursor: "pointer",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.color = CHALK)}
      onMouseLeave={(e) => (e.currentTarget.style.color = DIM)}
    >
      <Icon className="w-4 h-4" />
    </button>
  );

  return (
    <>
      {/* Seam legend — top-right of the canvas */}
      <div
        style={{
          position: "absolute", top: 12, right: 12, zIndex: 20,
          display: "flex", alignItems: "center", gap: 7,
          padding: "5px 10px",
          background: BG, border: `1px solid ${EDGE}`, borderRadius: 8,
          fontSize: 11, fontFamily: "monospace", color: DIM,
          boxShadow: "0 2px 12px rgba(0,0,0,0.25)",
          whiteSpace: "nowrap",
        }}
      >
        <span
          style={{
            width: 12, height: 12, borderRadius: 3,
            background: SEAM_ACCENT.header,
            border: `1.5px solid ${SEAM_ACCENT.border}`,
          }}
        />
        <Link2 className="w-3.5 h-3.5" /> connection point (seam)
      </div>

      {/* Carousel navigator — bottom, contained within the canvas */}
      <div
        style={{
          position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 20,
          display: "flex", alignItems: "center",
          background: BG, border: `1px solid ${EDGE}`, borderRadius: 10,
          boxShadow: "0 4px 24px rgba(0,0,0,0.35)",
          opacity: loading ? 0.7 : 1,
          pointerEvents: loading ? "none" : "auto",
          overflow: "hidden",
        }}
      >
        <span
          style={{
            flexShrink: 0,
            padding: "9px 12px",
            fontSize: 10, fontFamily: "monospace", fontWeight: 700,
            letterSpacing: "0.14em", textTransform: "uppercase",
            color: GOLD, borderRight: `1px solid ${EDGE}`, whiteSpace: "nowrap",
          }}
        >
          Nexus Ag
        </span>

        {arrow(-1, ChevronLeft, "Scroll left")}

        <div
          ref={stripRef}
          style={{
            display: "flex", alignItems: "center",
            flex: 1, minWidth: 0,
            overflowX: "auto", scrollBehavior: "smooth",
          }}
        >
          {demos.map((demo, i) => {
            const active = demo.id === activeDemoId;
            return (
              <button
                key={demo.id}
                onClick={() => !active && onSwitch(demo)}
                style={{
                  flexShrink: 0,
                  padding: "9px 16px",
                  fontSize: 12, fontFamily: "monospace",
                  fontWeight: active ? 700 : 500,
                  background: active ? "rgba(215,180,106,0.18)" : "transparent",
                  color: active ? GOLD : DIM,
                  border: "none",
                  borderRight: i < demos.length - 1 ? `1px solid ${EDGE}` : "none",
                  cursor: active ? "default" : "pointer",
                  transition: "background .15s, color .15s",
                  whiteSpace: "nowrap",
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.color = CHALK; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.color = DIM; }}
              >
                {demo.label}
              </button>
            );
          })}
        </div>

        {arrow(1, ChevronRight, "Scroll right")}
      </div>
    </>
  );
}
