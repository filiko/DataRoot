import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import { PillEdgeLabel } from "./PillEdgeLabel";

export function DiagramEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerEnd,
  label,
  labelStyle,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{ ...style, cursor: "pointer" }}
        interactionWidth={28}
      />
      {label && (
        <PillEdgeLabel x={labelX} y={labelY} style={labelStyle}>
          {label}
        </PillEdgeLabel>
      )}
    </>
  );
}
