import { anchorForHandle, parseHandleId, sideVector } from "./handleAssignment";
import {
  dedupePolyline,
  inflateRect,
  pointDistance,
  polylineLength,
  segmentIntersectsRect,
  segmentIntersectsSegment,
} from "./geometry";
import type { LayoutNodeBox, Point, Rect, RoutedEdge } from "./types";

const EDGE_NODE_GAP = 28;
const EXIT_LENGTH = 42;

export function routeEdges(
  nodes: LayoutNodeBox[],
  edges: RoutedEdge[],
  options: { reuseExistingPoints?: boolean } = {},
): RoutedEdge[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const previousRoutes: Point[][] = [];

  return edges.map((edge) => {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) return edge;

    // Keep an already-routed edge as-is, but treat its polyline as an obstacle
    // so newly routed edges still avoid crossing it.
    if (options.reuseExistingPoints && edge.points.length >= 2) {
      previousRoutes.push(edge.points);
      return edge;
    }

    const points = source.id === target.id
      ? routeSelfLoop(source, edge)
      : routeBetweenNodes(source, target, edge, nodes, previousRoutes);
    previousRoutes.push(points);
    return { ...edge, points };
  });
}

function routeSelfLoop(node: LayoutNodeBox, edge: RoutedEdge): Point[] {
  const source = anchorForHandle(node, edge.sourceHandle, "source");
  const target = anchorForHandle(node, edge.targetHandle, "target");
  const x = node.x + node.width + 70;
  const y = node.y + node.height + 55;
  return dedupePolyline([
    source,
    { x, y: source.y },
    { x, y },
    { x: target.x, y },
    target,
  ]);
}

function routeBetweenNodes(
  source: LayoutNodeBox,
  target: LayoutNodeBox,
  edge: RoutedEdge,
  nodes: LayoutNodeBox[],
  previousRoutes: Point[][],
): Point[] {
  const sourceAnchor = anchorForHandle(source, edge.sourceHandle, "source");
  const targetAnchor = anchorForHandle(target, edge.targetHandle, "target");
  const sourceSide = parseHandleId(edge.sourceHandle)?.side ?? "right";
  const targetSide = parseHandleId(edge.targetHandle)?.side ?? "left";
  const sourceOut = add(sourceAnchor, multiply(sideVector(sourceSide), EXIT_LENGTH));
  const targetOut = add(targetAnchor, multiply(sideVector(targetSide), EXIT_LENGTH));
  const midX = (sourceOut.x + targetOut.x) / 2;
  const midY = (sourceOut.y + targetOut.y) / 2;

  const candidates = [
    [sourceAnchor, sourceOut, { x: targetOut.x, y: sourceOut.y }, targetOut, targetAnchor],
    [sourceAnchor, sourceOut, { x: sourceOut.x, y: targetOut.y }, targetOut, targetAnchor],
    [sourceAnchor, sourceOut, { x: midX, y: sourceOut.y }, { x: midX, y: targetOut.y }, targetOut, targetAnchor],
    [sourceAnchor, sourceOut, { x: sourceOut.x, y: midY }, { x: targetOut.x, y: midY }, targetOut, targetAnchor],
  ].map(dedupePolyline);

  const obstacles = nodes
    .filter((node) => node.id !== source.id && node.id !== target.id)
    .map((node) => inflateRect(node, EDGE_NODE_GAP));

  let best = candidates[0];
  let bestScore = Number.POSITIVE_INFINITY;
  for (const candidate of candidates) {
    const score = routeScore(candidate, obstacles, previousRoutes);
    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  }
  return best;
}

function routeScore(points: Point[], obstacles: Rect[], previousRoutes: Point[][]): number {
  let bends = 0;
  let obstacleHits = 0;
  let crossings = 0;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    if (i > 1) {
      const prev = points[i - 2];
      if ((prev.x !== a.x || a.x !== b.x) && (prev.y !== a.y || a.y !== b.y)) {
        bends += 1;
      }
    }
    obstacleHits += obstacles.filter((rect) => segmentIntersectsRect(a, b, rect)).length;
    crossings += countRouteCrossings(a, b, previousRoutes);
  }

  return polylineLength(points)
    + bends * 24
    + obstacleHits * 100000
    + crossings * 240;
}

function countRouteCrossings(a: Point, b: Point, previousRoutes: Point[][]): number {
  let crossings = 0;
  for (const route of previousRoutes) {
    for (let i = 1; i < route.length; i++) {
      const c = route[i - 1];
      const d = route[i];
      if (sharesEndpoint(a, b, c, d)) continue;
      if (segmentIntersectsSegment(a, b, c, d)) crossings += 1;
    }
  }
  return crossings;
}

function sharesEndpoint(a: Point, b: Point, c: Point, d: Point): boolean {
  return samePoint(a, c) || samePoint(a, d) || samePoint(b, c) || samePoint(b, d);
}

function samePoint(a: Point, b: Point): boolean {
  return a.x === b.x && a.y === b.y;
}

function add(a: Point, b: Point): Point {
  return { x: a.x + b.x, y: a.y + b.y };
}

function multiply(point: Point, amount: number): Point {
  return { x: point.x * amount, y: point.y * amount };
}

export function edgePathLength(points: Point[]): number {
  return points.length < 2 ? 0 : pointDistance(points[0], points[points.length - 1]);
}
