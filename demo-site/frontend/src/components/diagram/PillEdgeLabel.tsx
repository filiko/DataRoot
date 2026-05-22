import React from "react";
import { EdgeLabelRenderer } from "@xyflow/react";
import { useDiagramTheme } from "../../context/DiagramThemeContext";

interface PillEdgeLabelProps {
  x: number;
  y: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
  interactive?: boolean;
  title?: string;
  onPointerDown?: React.PointerEventHandler<HTMLDivElement>;
  onPointerMove?: React.PointerEventHandler<HTMLDivElement>;
  onPointerUp?: React.PointerEventHandler<HTMLDivElement>;
  onPointerCancel?: React.PointerEventHandler<HTMLDivElement>;
}

export function PillEdgeLabel({
  x,
  y,
  children,
  style,
  interactive = false,
  title,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerCancel,
}: PillEdgeLabelProps) {
  const { theme } = useDiagramTheme();
  return (
    <EdgeLabelRenderer>
      <div
        className="nodrag nopan"
        title={title}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerCancel}
        style={{
          position: "absolute",
          transform: `translate(-50%, -50%) translate(${x}px, ${y}px)`,
          background: theme.dfd.edge.labelBg,
          border: `1px solid ${theme.dfd.edge.stroke}`,
          borderRadius: 999,
          padding: "2px 7px",
          color: theme.dfd.edge.labelText,
          fontSize: 11,
          fontWeight: 600,
          lineHeight: 1.3,
          pointerEvents: interactive ? "auto" : "none",
          cursor: interactive ? "grab" : "default",
          userSelect: "none",
          whiteSpace: "nowrap",
          maxWidth: 220,
          overflow: "hidden",
          textOverflow: "ellipsis",
          ...style,
        }}
      >
        {children}
      </div>
    </EdgeLabelRenderer>
  );
}
