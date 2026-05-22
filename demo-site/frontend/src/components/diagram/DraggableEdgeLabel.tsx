import { useState, type CSSProperties, type PointerEvent, type ReactNode } from "react";
import { useReactFlow } from "@xyflow/react";
import { pointAndNormalAtPolylineT, projectPointToPolyline } from "./layout/geometry";
import type { Point } from "./layout/types";
import { useEdgeLabelMove } from "./useEdgeLabelMove";
import { PillEdgeLabel } from "./PillEdgeLabel";

interface DraggableEdgeLabelProps {
  edgeId: string;
  points?: Point[];
  fallbackX: number;
  fallbackY: number;
  labelT?: number | null;
  labelOffset?: number | null;
  style?: CSSProperties;
  children: ReactNode;
}

export function DraggableEdgeLabel({
  edgeId,
  points = [],
  fallbackX,
  fallbackY,
  labelT,
  labelOffset,
  style,
  children,
}: DraggableEdgeLabelProps) {
  const reactFlow = useReactFlow();
  const onLabelMove = useEdgeLabelMove();
  const [draft, setDraft] = useState<{ t: number; offset: number } | null>(null);
  const canDrag = Boolean(onLabelMove && points.length >= 2);
  const active = draft ?? (points.length >= 2
    ? { t: labelT ?? 0.5, offset: labelOffset ?? -22 }
    : null);
  const position = active
    ? pointAndNormalAtPolylineT(points, active.t, active.offset).point
    : { x: fallbackX, y: fallbackY };

  const updateFromPointer = (event: PointerEvent<HTMLDivElement>) => {
    const flowPoint = reactFlow.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    const projected = projectPointToPolyline(flowPoint, points);
    setDraft({ t: projected.t, offset: projected.offset });
    return projected;
  };

  return (
    <PillEdgeLabel
      x={position.x}
      y={position.y}
      interactive={canDrag}
      title={canDrag ? "Drag along edge" : undefined}
      style={{
        ...style,
        cursor: canDrag ? (draft ? "grabbing" : "grab") : undefined,
      }}
      onPointerDown={canDrag ? (event) => {
        event.preventDefault();
        event.stopPropagation();
        event.currentTarget.setPointerCapture(event.pointerId);
        updateFromPointer(event);
      } : undefined}
      onPointerMove={canDrag && draft ? (event) => {
        event.preventDefault();
        event.stopPropagation();
        updateFromPointer(event);
      } : undefined}
      onPointerUp={canDrag ? (event) => {
        event.preventDefault();
        event.stopPropagation();
        const projected = updateFromPointer(event);
        event.currentTarget.releasePointerCapture(event.pointerId);
        setDraft(null);
        onLabelMove?.(edgeId, projected.t, projected.offset);
      } : undefined}
      onPointerCancel={canDrag ? (event) => {
        event.stopPropagation();
        setDraft(null);
      } : undefined}
    >
      {children}
    </PillEdgeLabel>
  );
}
