import type { LayoutEdgePatch, LayoutNodePatch } from "../../../hooks/useLayoutPatch";
import { autoArrangeNodes } from "./elkLayout";
import { assignHandles } from "./handleAssignment";
import { placeEdgeLabels } from "./labelPlacement";
import { repairNodeOverlaps } from "./overlap";
import { routeEdges } from "./orthogonalRouter";
import type {
  LayoutGraph,
  LayoutNodeBox,
  LayoutOptimizationOptions,
  LayoutOptimizationResult,
} from "./types";

export async function optimizeDiagramLayout(
  input: LayoutGraph,
  options: LayoutOptimizationOptions,
): Promise<LayoutOptimizationResult> {
  const gridSize = options.gridSize ?? 24;
  const nodeGap = options.nodeGap ?? 64;
  const sized = normalizeMeasuredSizes(input.nodes);
  const placed = options.mode === "auto"
    ? await autoArrangeNodes(sized, input.edges, gridSize)
    : repairNodeOverlaps(sized, gridSize, nodeGap);
  const handled = assignHandles(placed, input.edges);
  const routed = routeEdges(placed, handled);
  const labeled = placeEdgeLabels(placed, routed);
  return { nodes: placed, edges: labeled };
}

export function toLayoutNodePatch(node: LayoutNodeBox): LayoutNodePatch {
  return {
    id: node.id,
    x: node.x,
    y: node.y,
    width: node.width,
    height: node.height,
  };
}

export function toLayoutEdgePatch(edge: LayoutOptimizationResult["edges"][number]): LayoutEdgePatch {
  return {
    id: edge.id,
    route: "orthogonal",
    source_handle: edge.sourceHandle,
    target_handle: edge.targetHandle,
    points: edge.points,
    label_t: edge.placedLabel?.t ?? edge.label_t ?? null,
    label_offset: edge.placedLabel?.offset ?? edge.label_offset ?? null,
  };
}

function normalizeMeasuredSizes(nodes: LayoutNodeBox[]): LayoutNodeBox[] {
  return nodes.map((node) => ({
    ...node,
    width: normalizeSize(node.width, fallbackWidth(node.kind)),
    height: normalizeSize(node.height, fallbackHeight(node.kind)),
  }));
}

function normalizeSize(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function fallbackWidth(kind: LayoutNodeBox["kind"]): number {
  return kind === "dfd_process" ? 260 : kind === "erd_entity" ? 280 : 230;
}

function fallbackHeight(kind: LayoutNodeBox["kind"]): number {
  return kind === "erd_entity" ? 180 : 92;
}
