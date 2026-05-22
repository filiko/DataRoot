import {
  labelSize,
  pointAndNormalAtPolylineT,
  pointDistance,
  polylineLength,
  rectCenteredAt,
  totalOverlapArea,
} from "./geometry";
import type { LayoutNodeBox, PlacedLabel, RoutedEdge } from "./types";

export function placeEdgeLabels(nodes: LayoutNodeBox[], edges: RoutedEdge[]): RoutedEdge[] {
  const placedLabels: PlacedLabel[] = [];
  const nodeRects = nodes.map((node) => ({ ...node }));

  return edges.map((edge) => {
    if (!edge.label || edge.points.length < 2) return edge;

    const size = labelSize(edge.label);
    const preferred = edge.label_t !== undefined && edge.label_t !== null
      ? buildLabel(edge, edge.label_t, edge.label_offset ?? 0, size.width, size.height)
      : undefined;

    const placed = preferred ?? chooseBestLabel(edge, size.width, size.height, nodeRects, placedLabels);
    placedLabels.push(placed);
    return {
      ...edge,
      label_t: placed.t,
      label_offset: placed.offset,
      placedLabel: placed,
    };
  });
}

function chooseBestLabel(
  edge: RoutedEdge,
  width: number,
  height: number,
  nodeRects: LayoutNodeBox[],
  placedLabels: PlacedLabel[],
): PlacedLabel {
  const candidates = labelCandidates(edge, width, height);
  let best = candidates[0];
  let bestScore = Number.POSITIVE_INFINITY;

  for (const candidate of candidates) {
    const center = {
      x: candidate.x + candidate.width / 2,
      y: candidate.y + candidate.height / 2,
    };
    const anchorDistance = pointDistance(center, candidate.anchor);
    const score =
      totalOverlapArea(candidate, nodeRects) * 100000
      + totalOverlapArea(candidate, placedLabels) * 50000
      + Math.abs(candidate.offset) * 3
      + Math.abs(candidate.t - 0.5) * 120
      + anchorDistance * 4;

    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  }

  return best;
}

function labelCandidates(edge: RoutedEdge, width: number, height: number): PlacedLabel[] {
  const total = polylineLength(edge.points) || 1;
  const candidates: PlacedLabel[] = [];
  let lengthBefore = 0;

  for (let i = 1; i < edge.points.length; i++) {
    const start = edge.points[i - 1];
    const end = edge.points[i];
    const segmentLength = pointDistance(start, end);
    if (segmentLength < 12) continue;

    for (const ratio of [0.33, 0.5, 0.67]) {
      const t = (lengthBefore + segmentLength * ratio) / total;
      for (const offset of [-32, -18, 18, 32]) {
        candidates.push(buildLabel(edge, t, offset, width, height));
      }
    }
    lengthBefore += segmentLength;
  }

  if (candidates.length === 0) {
    candidates.push(buildLabel(edge, 0.5, -22, width, height));
  }
  return candidates;
}

function buildLabel(
  edge: RoutedEdge,
  t: number,
  offset: number,
  width: number,
  height: number,
): PlacedLabel {
  const { point, normal } = pointAndNormalAtPolylineT(edge.points, t, offset);
  const anchor = pointAndNormalAtPolylineT(edge.points, t, 0).point;
  return {
    ...rectCenteredAt(`${edge.id}:label`, point, width, height),
    edgeId: edge.id,
    anchor,
    t,
    offset: normal.x === 0 && normal.y === 0 ? 0 : offset,
  };
}
