import { memo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp } from "lucide-react";
import type { PenFile, WarningEntry } from "../types/pen";

type Props = {
  pen: PenFile;
};

const SEVERITY_STYLES: Record<WarningEntry["severity"], { bg: string; border: string; text: string }> = {
  warning: { bg: "bg-yellow-50", border: "border-yellow-300", text: "text-yellow-800" },
  blocking: { bg: "bg-red-50", border: "border-red-300", text: "text-red-800" },
};

function WarningsBannerInner({ pen }: Props) {
  const [expanded, setExpanded] = useState(false);
  const warnings = pen.review.warnings;
  if (!warnings || warnings.length === 0) return null;

  const blocking = warnings.filter((w) => w.severity === "blocking").length;
  const summary = blocking > 0
    ? `${blocking} blocking, ${warnings.length - blocking} warning`
    : `${warnings.length} ${warnings.length === 1 ? "issue" : "issues"}`;

  const topSeverity: WarningEntry["severity"] = blocking > 0 ? "blocking" : "warning";
  const styles = SEVERITY_STYLES[topSeverity];

  return (
    <div className={`flex-shrink-0 border-b ${styles.bg} ${styles.border} ${styles.text}`}>
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium hover:bg-black/5"
      >
        <span className="flex items-center gap-2">
          <AlertTriangle className="w-3.5 h-3.5" />
          {summary} — diagram quality
        </span>
        {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
      </button>
      {expanded && (
        <ul className="px-4 pb-3 space-y-1 max-h-48 overflow-y-auto">
          {warnings.map((w, i) => (
            <li key={i} className="text-xs flex items-start gap-2">
              <span className="font-mono text-[10px] bg-white/60 rounded px-1 py-0.5 mt-0.5 flex-shrink-0">
                {w.rule_id}
              </span>
              <span>
                {w.node_name && <span className="font-semibold">{w.node_name}: </span>}
                {w.message}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Re-render only when the warnings list itself changes (compare by reference,
// then by length, then by rule ids). Polling refreshes return new pen objects
// every 2.5s — without this guard the banner re-renders constantly even when
// nothing about the warnings has actually changed.
function warningsEqual(a: Props, b: Props) {
  const wa = a.pen.review.warnings;
  const wb = b.pen.review.warnings;
  if (wa === wb) return true;
  if (wa.length !== wb.length) return false;
  for (let i = 0; i < wa.length; i++) {
    if (wa[i].rule_id !== wb[i].rule_id || wa[i].node_id !== wb[i].node_id) {
      return false;
    }
  }
  return true;
}

export const WarningsBanner = memo(WarningsBannerInner, warningsEqual);
