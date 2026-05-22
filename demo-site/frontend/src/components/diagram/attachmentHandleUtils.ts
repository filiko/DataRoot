import React from "react";
import { Position } from "@xyflow/react";

export type AttachmentSide = "left" | "right" | "top" | "bottom";
export type HandleKind = "source" | "target";

export const ATTACHMENT_SIDES: AttachmentSide[] = ["left", "right", "top", "bottom"];
export const HANDLE_LANES = [0, 1, 2] as const;

const HANDLE_LANE_POSITIONS = [26, 50, 74] as const;

export const HANDLE_POSITION: Record<AttachmentSide, Position> = {
  left: Position.Left,
  right: Position.Right,
  top: Position.Top,
  bottom: Position.Bottom,
};

export function handleId(type: HandleKind, side: AttachmentSide, lane: number) {
  return `${type}-${side}-${lane}`;
}

export function handleStyle(
  side: AttachmentSide,
  lane: number,
  type: HandleKind,
  visible: boolean,
  color = type === "source" ? "#6366f1" : "#fff",
  border = type === "source" ? "#fff" : "#6366f1",
): React.CSSProperties {
  const isHorizontalSide = side === "top" || side === "bottom";
  const size = 9;
  const offset = -5;
  const lanePosition = `${HANDLE_LANE_POSITIONS[lane] + (type === "source" ? -4 : 4)}%`;
  const style: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: 999,
    border: `2px solid ${border}`,
    background: color,
    opacity: visible ? 0.92 : 0,
    boxShadow: visible ? "0 1px 4px rgba(79,70,229,0.30)" : "none",
    transition: "opacity 120ms ease, box-shadow 120ms ease",
    pointerEvents: visible ? "auto" : "none",
    cursor: visible ? "crosshair" : "default",
    zIndex: 3,
  };

  if (isHorizontalSide) {
    style.left = lanePosition;
    style.top = side === "top" ? offset : undefined;
    style.bottom = side === "bottom" ? offset : undefined;
  } else {
    style.top = lanePosition;
    style.left = side === "left" ? offset : undefined;
    style.right = side === "right" ? offset : undefined;
  }

  return style;
}
