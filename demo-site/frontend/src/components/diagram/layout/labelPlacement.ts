import {
  labelSize,
  pointAndNormalAtPolylineT,
  pointDistance,
  polylineLength,
  rectCenteredAt,
  segmentIntersectsRect,
  totalOverlapArea,
} from "./geometry";
import type { LayoutNodeBox, PlacedLabel, Point, Rect, RoutedEdge } from "./types";

type EdgeRoute = { id: string; points: Point[] };

export function placeEdgeLabels(nodes: LayoutNodeBox[], edges: RoutedEdge[]): RoutedEdge[] {
  const placedLabels: PlacedLabel[] = [];
  const nodeRects = nodes.map((node) => ({ ...node }));
  const routes: EdgeRoute[] = edges
    .filter((edge) => edge.points.length >= 2)
    .map((edge) => ({ id: edge.id, points: edge.points }));

  const placeOne = (edge: RoutedEdge): RoutedEdge => {
    const size = labelSize(edge.label);
    let preferred = edge.label_t !== undefined && edge.label_t !== null
      ? buildLabel(edge, edge.label_t, edge.label_offset ?? 0, size.width, size.height)
      : undefined;

    // Never honor a stored position that hides the label behind a table —
    // no one intends that. Re-place it with the collision-avoiding scorer.
    if (preferred && totalOverlapArea(preferred, nodeRects) > 4) {
      preferred = undefined;
    }

    const placed = preferred
      ?? chooseBestLabel(edge, size.width, size.height, nodeRects, placedLabels, routes);
    placedLabels.push(placed);
    return {
      ...edge,
      label_t: placed.t,
      label_offset: placed.offset,
      placedLabel: placed,
    };
  };

  // Manual (stored) labels first so they act as immovable obstacles, then the
  // rest most-constrained first — short edges have the least slack.
  const placeable = (edge: RoutedEdge) => Boolean(edge.label) && edge.points.length >= 2;
  const isManual = (edge: RoutedEdge) => edge.label_t !== undefined && edge.label_t !== null;
  const manual = edges.filter((edge) => placeable(edge) && isManual(edge));
  const auto = edges
    .filter((edge) => placeable(edge) && !isManual(edge))
    .sort((a, b) => polylineLength(a.points) - polylineLength(b.points));

  const results = new Map<string, RoutedEdge>();
  for (const edge of manual) results.set(edge.id, placeOne(edge));
  for (const edge of auto) results.set(edge.id, placeOne(edge));
  return edges.map((edge) => results.get(edge.id) ?? edge);
}

function chooseBestLabel(
  edge: RoutedEdge,
  width: number,
  height: number,
  nodeRects: LayoutNodeBox[],
  placedLabels: PlacedLabel[],
  routes: EdgeRoute[],
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
      + edgeCrossingCount(candidate, edge.id, routes) * 2500
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

function edgeCrossingCount(rect: Rect, ownEdgeId: string, routes: EdgeRoute[]): number {
  let hits = 0;
  for (const route of routes) {
    if (route.id === ownEdgeId) continue;
    for (let i = 1; i < route.points.length; i++) {
      if (segmentIntersectsRect(route.points[i - 1], route.points[i], rect)) hits += 1;
    }
  }
  return hits;
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

    for (const ratio of [0.2, 0.33, 0.5, 0.67, 0.8]) {
      const t = (lengthBefore + segmentLength * ratio) / total;
      for (const offset of [-44, -32, -18, 18, 32, 44]) {
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
