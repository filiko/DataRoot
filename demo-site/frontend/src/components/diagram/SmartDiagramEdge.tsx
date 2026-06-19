import { useMemo } from "react";
import {
  BaseEdge,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import { DraggableEdgeLabel } from "./DraggableEdgeLabel";
import { alignRoutedPoints, polylineToPath } from "./layout/geometry";
import type { Point } from "./layout/types";

export type RoutedEdgeData = {
  points?: Point[];
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
  data,
}: EdgeProps & { data?: RoutedEdgeData }) {
  const [fallbackPath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  // Stored orthogonal routes go stale when a connected node moves (live drag);
  // alignRoutedPoints rejects them so the edge degrades to smooth-step until
  // the route is recomputed on drop.
  const aligned = useMemo(
    () => alignRoutedPoints(data?.points, sourceX, sourceY, targetX, targetY),
    [data?.points, sourceX, sourceY, targetX, targetY],
  );
  const path = aligned ? polylineToPath(aligned) : fallbackPath;

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        style={{ ...style, cursor: "pointer" }}
        interactionWidth={28}
      />
      {label && (
        <DraggableEdgeLabel
          edgeId={id}
          points={aligned ?? []}
          fallbackX={labelX}
          fallbackY={labelY}
          labelT={data?.label_t}
          labelOffset={data?.label_offset}
          style={labelStyle}
        >
          {label}
        </DraggableEdgeLabel>
      )}
    </>
  );
}
