import {
  ATTACHMENT_SIDES,
  HANDLE_LANES,
  handleId,
  type AttachmentSide,
} from "../attachmentHandleUtils";
import { centerOf } from "./geometry";
import type { LayoutEdgeRef, LayoutNodeBox, ParsedHandle, Point, RoutedEdge } from "./types";

const LANE_POSITIONS = [0.26, 0.5, 0.74] as const;

export function parseHandleId(id: string | undefined): ParsedHandle | null {
  if (!id) return null;
  const [kind, side, lane] = id.split("-");
  if ((kind !== "source" && kind !== "target")
    || !ATTACHMENT_SIDES.includes(side as AttachmentSide)) {
    return null;
  }
  const parsedLane = Number(lane);
  if (!Number.isInteger(parsedLane) || !HANDLE_LANES.includes(parsedLane as 0 | 1 | 2)) {
    return null;
  }
  return { kind, side: side as AttachmentSide, lane: parsedLane };
}

export function sideVector(side: AttachmentSide): Point {
  switch (side) {
    case "left":
      return { x: -1, y: 0 };
    case "right":
      return { x: 1, y: 0 };
    case "top":
      return { x: 0, y: -1 };
    case "bottom":
      return { x: 0, y: 1 };
  }
}

export function anchorForHandle(node: LayoutNodeBox, handle: string | undefined, fallbackKind: "source" | "target"): Point {
  const parsed = parseHandleId(handle);
  const side = parsed?.side ?? (fallbackKind === "source" ? "right" : "left");
  const lane = parsed?.lane ?? 1;
  // Rendered handles shift source/target lanes by ∓4% (see handleStyle in
  // ERDCanvas/AttachmentHandles); mirror it so routed endpoints land on them.
  const laneShift = (parsed?.kind ?? fallbackKind) === "source" ? -0.04 : 0.04;
  const lanePosition = (LANE_POSITIONS[lane] ?? 0.5) + laneShift;

  if (side === "left") return { x: node.x, y: node.y + node.height * lanePosition };
  if (side === "right") return { x: node.x + node.width, y: node.y + node.height * lanePosition };
  if (side === "top") return { x: node.x + node.width * lanePosition, y: node.y };
  return { x: node.x + node.width * lanePosition, y: node.y + node.height };
}

export function assignHandles(nodes: LayoutNodeBox[], edges: LayoutEdgeRef[]): RoutedEdge[] {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const handleUseCounts = new Map<string, number>();
  const ordered = [...edges].sort((a, b) => edgePriority(b, nodeMap, edges) - edgePriority(a, nodeMap, edges));

  const routedById = new Map<string, RoutedEdge>();
  for (const edge of ordered) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;

    const best = chooseHandlePair(source, target, edge, handleUseCounts);
    handleUseCounts.set(`${source.id}:${best.sourceHandle}`, (handleUseCounts.get(`${source.id}:${best.sourceHandle}`) ?? 0) + 1);
    handleUseCounts.set(`${target.id}:${best.targetHandle}`, (handleUseCounts.get(`${target.id}:${best.targetHandle}`) ?? 0) + 1);

    routedById.set(edge.id, {
      ...edge,
      sourceHandle: best.sourceHandle,
      targetHandle: best.targetHandle,
      points: edge.points ?? [],
    });
  }

  return edges
    .map((edge) => routedById.get(edge.id))
    .filter((edge): edge is RoutedEdge => Boolean(edge));
}

function edgePriority(edge: LayoutEdgeRef, nodeMap: Map<string, LayoutNodeBox>, edges: LayoutEdgeRef[]): number {
  const degree = edges.filter((item) =>
    item.source === edge.source
    || item.target === edge.source
    || item.source === edge.target
    || item.target === edge.target
  ).length;
  const source = nodeMap.get(edge.source);
  const target = nodeMap.get(edge.target);
  if (!source || !target) return degree;
  const distance = Math.hypot(centerOf(source).x - centerOf(target).x, centerOf(source).y - centerOf(target).y);
  return degree * 10000 - distance;
}

function chooseHandlePair(
  source: LayoutNodeBox,
  target: LayoutNodeBox,
  edge: LayoutEdgeRef,
  handleUseCounts: Map<string, number>,
): { sourceHandle: string; targetHandle: string } {
  if (source.id === target.id) {
    return {
      sourceHandle: edge.sourceHandle ?? handleId("source", "right", 0),
      targetHandle: edge.targetHandle ?? handleId("target", "bottom", 2),
    };
  }

  let best = {
    sourceHandle: edge.sourceHandle ?? handleId("source", "right", 1),
    targetHandle: edge.targetHandle ?? handleId("target", "left", 1),
    score: Number.POSITIVE_INFINITY,
  };

  for (const sourceSide of ATTACHMENT_SIDES) {
    for (const targetSide of ATTACHMENT_SIDES) {
      for (const sourceLane of HANDLE_LANES) {
        for (const targetLane of HANDLE_LANES) {
          const sourceHandle = handleId("source", sourceSide, sourceLane);
          const targetHandle = handleId("target", targetSide, targetLane);
          const score = scoreCandidate(source, target, sourceSide, targetSide, sourceHandle, targetHandle, handleUseCounts);
          if (score < best.score) {
            best = { sourceHandle, targetHandle, score };
          }
        }
      }
    }
  }

  return best;
}

function scoreCandidate(
  source: LayoutNodeBox,
  target: LayoutNodeBox,
  sourceSide: AttachmentSide,
  targetSide: AttachmentSide,
  sourceHandle: string,
  targetHandle: string,
  handleUseCounts: Map<string, number>,
): number {
  const sourceCenter = centerOf(source);
  const targetCenter = centerOf(target);
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  const distance = Math.hypot(dx, dy) || 1;
  const desired = { x: dx / distance, y: dy / distance };
  const sourceVector = sideVector(sourceSide);
  const targetVector = sideVector(targetSide);
  const directionPenalty =
    (1 - dot(sourceVector, desired)) * 120
    + (1 + dot(targetVector, desired)) * 120;
  const sourceUse = handleUseCounts.get(`${source.id}:${sourceHandle}`) ?? 0;
  const targetUse = handleUseCounts.get(`${target.id}:${targetHandle}`) ?? 0;
  const congestionPenalty = (sourceUse + targetUse) * 220;
  const lengthPenalty = distance * 0.02;
  return directionPenalty + congestionPenalty + lengthPenalty;
}

function dot(a: Point, b: Point): number {
  return a.x * b.x + a.y * b.y;
}
