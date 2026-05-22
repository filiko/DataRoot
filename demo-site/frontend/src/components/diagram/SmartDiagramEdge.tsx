import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import { DraggableEdgeLabel } from "./DraggableEdgeLabel";

export type RoutedEdgeData = {
  points?: unknown[];
  label_t?: number | null;
  label_offset?: number | null;
};

export function SmartDiagramEdge({
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
}: EdgeProps & { data?: RoutedEdgeData }) {
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
        <DraggableEdgeLabel
          edgeId={id}
          fallbackX={labelX}
          fallbackY={labelY}
          style={labelStyle}
        >
          {label}
        </DraggableEdgeLabel>
      )}
    </>
  );
}
