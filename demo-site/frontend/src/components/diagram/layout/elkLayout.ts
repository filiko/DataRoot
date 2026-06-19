import ELK from "elkjs/lib/elk.bundled.js";
import { centerOf, overlapArea, snap } from "./geometry";
import type { LayoutEdgeRef, LayoutNodeBox } from "./types";

type ElkChild = {
  id: string;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
};

type ElkResult = {
  children?: ElkChild[];
};

type ElkDirection = "RIGHT" | "DOWN";

const elk = new ELK();

export async function autoArrangeNodes(
  nodes: LayoutNodeBox[],
  edges: LayoutEdgeRef[],
  gridSize: number,
): Promise<LayoutNodeBox[]> {
  if (nodes.length === 0) return nodes;

  const candidates: LayoutNodeBox[][] = [
    semanticBalancedArrange(nodes, edges, gridSize),
    fallbackArrange(nodes, edges, gridSize),
  ];

  try {
    const elkCandidates = await Promise.all([
      layoutWithElk(nodes, edges, gridSize, "RIGHT", 96, 170),
      layoutWithElk(nodes, edges, gridSize, "RIGHT", 120, 200),
      layoutWithElk(nodes, edges, gridSize, "DOWN", 96, 170),
    ]);
    candidates.push(...elkCandidates);
  } catch (error) {
    console.warn("ELK layout failed; falling back to deterministic layout.", error);
  }

  return chooseBestLayout(candidates, edges);
}

async function layoutWithElk(
  nodes: LayoutNodeBox[],
  edges: LayoutEdgeRef[],
  gridSize: number,
  direction: ElkDirection,
  nodeSpacing: number,
  layerSpacing: number,
): Promise<LayoutNodeBox[]> {
  const result = await elk.layout({
      id: "root",
      layoutOptions: {
        "elk.algorithm": "layered",
        "elk.direction": direction,
        "elk.spacing.nodeNode": String(nodeSpacing),
        "elk.layered.spacing.nodeNodeBetweenLayers": String(layerSpacing),
        "elk.spacing.edgeNode": "40",
        "elk.spacing.edgeEdge": "24",
        "elk.layered.spacing.edgeNodeBetweenLayers": "40",
        "elk.edgeRouting": "ORTHOGONAL",
        "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
      },
      children: orderedForModel(nodes).map((node) => ({
        id: node.id,
        width: node.width,
        height: node.height,
      })),
      edges: edges
        .filter((edge) => edge.source !== edge.target)
        .map((edge) => ({
          id: edge.id,
          sources: [edge.source],
          targets: [edge.target],
          labels: edge.label ? [{
            text: edge.label,
            width: Math.min(220, edge.label.length * 7 + 18),
            height: 22,
          }] : undefined,
        })),
    }) as ElkResult;

  const byId = new Map((result.children ?? []).map((child) => [child.id, child]));
  return nodes.map((node) => {
    const child = byId.get(node.id);
    return {
      ...node,
      x: snap((child?.x ?? node.x) + 80, gridSize),
      y: snap((child?.y ?? node.y) + 80, gridSize),
      width: child?.width ?? node.width,
      height: child?.height ?? node.height,
    };
  });
}

function orderedForModel(nodes: LayoutNodeBox[]): LayoutNodeBox[] {
  const rank = (node: LayoutNodeBox) =>
    node.kind === "dfd_external" ? 0 :
    node.kind === "dfd_process" ? 1 :
    node.kind === "dfd_store" ? 2 :
    1;
  return [...nodes].sort((a, b) => rank(a) - rank(b) || a.id.localeCompare(b.id));
}

function fallbackArrange(
  nodes: LayoutNodeBox[],
  edges: LayoutEdgeRef[],
  gridSize: number,
): LayoutNodeBox[] {
  const hasDfdKinds = nodes.some((node) => node.kind.startsWith("dfd_"));
  if (hasDfdKinds) return fallbackDfd(nodes, gridSize);
  return fallbackErd(nodes, edges, gridSize);
}

function fallbackDfd(nodes: LayoutNodeBox[], gridSize: number): LayoutNodeBox[] {
  const groups: LayoutNodeBox["kind"][] = ["dfd_external", "dfd_process", "dfd_store"];
  const columnX = new Map<LayoutNodeBox["kind"], number>([
    ["dfd_external", 80],
    ["dfd_process", 420],
    ["dfd_store", 780],
  ]);
  return groups.flatMap((kind) =>
    nodes
      .filter((node) => node.kind === kind)
      .sort((a, b) => a.id.localeCompare(b.id))
      .map((node, index) => ({
        ...node,
        x: snap(columnX.get(kind) ?? 80, gridSize),
        y: snap(80 + index * 160, gridSize),
      }))
  );
}

function fallbackErd(nodes: LayoutNodeBox[], edges: LayoutEdgeRef[], gridSize: number): LayoutNodeBox[] {
  const degree = new Map<string, number>();
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }
  const ordered = [...nodes].sort((a, b) =>
    (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.id.localeCompare(b.id)
  );
  const columns = Math.max(1, Math.ceil(Math.sqrt(ordered.length)));
  return packErdGrid(ordered, columns, gridSize);
}

function semanticBalancedArrange(
  nodes: LayoutNodeBox[],
  edges: LayoutEdgeRef[],
  gridSize: number,
): LayoutNodeBox[] {
  const hasDfdKinds = nodes.some((node) => node.kind.startsWith("dfd_"));
  if (!hasDfdKinds) return balancedErdGrid(nodes, edges, gridSize);

  const externals = nodes.filter((node) => node.kind === "dfd_external").sort(byId);
  const processes = nodes.filter((node) => node.kind === "dfd_process").sort(byDegree(edges));
  const stores = nodes.filter((node) => node.kind === "dfd_store").sort(byId);
  const processColumns = Math.max(1, Math.ceil(Math.sqrt(processes.length || 1)));
  const processRows = Math.max(1, Math.ceil((processes.length || 1) / processColumns));
  const cellX = 330;
  const cellY = 150;
  const startY = 90;
  const processStartX = 390;
  const storeX = processStartX + processColumns * cellX + 110;
  const sideRows = Math.max(processRows, externals.length, stores.length, 1);
  const sideStep = Math.max(130, processRows * cellY / sideRows);

  return [
    ...externals.map((node, index) => ({
      ...node,
      x: snap(80, gridSize),
      y: snap(startY + index * sideStep, gridSize),
    })),
    ...processes.map((node, index) => ({
      ...node,
      x: snap(processStartX + (index % processColumns) * cellX, gridSize),
      y: snap(startY + Math.floor(index / processColumns) * cellY, gridSize),
    })),
    ...stores.map((node, index) => ({
      ...node,
      x: snap(storeX, gridSize),
      y: snap(startY + index * sideStep, gridSize),
    })),
  ];
}

function balancedErdGrid(nodes: LayoutNodeBox[], edges: LayoutEdgeRef[], gridSize: number): LayoutNodeBox[] {
  const ordered = [...nodes].sort(byDegree(edges));
  const columns = Math.max(1, Math.ceil(Math.sqrt(ordered.length * 1.35)));
  return packErdGrid(ordered, columns, gridSize);
}

export function packErdGrid(nodes: LayoutNodeBox[], columns: number, gridSize: number): LayoutNodeBox[] {
  const colWidth = Math.max(400, Math.max(...nodes.map((node) => node.width)) + 120);
  const rowGap = 110;
  const rowHeights: number[] = [];
  for (let start = 0; start < nodes.length; start += columns) {
    rowHeights.push(Math.max(...nodes.slice(start, start + columns).map((node) => node.height)));
  }

  const rowYs: number[] = [];
  let y = 80;
  for (const rowHeight of rowHeights) {
    rowYs.push(y);
    y += rowHeight + rowGap;
  }

  return nodes.map((node, index) => ({
    ...node,
    x: snap(80 + (index % columns) * colWidth, gridSize),
    y: snap(rowYs[Math.floor(index / columns)] ?? 80, gridSize),
  }));
}

function chooseBestLayout(candidates: LayoutNodeBox[][], edges: LayoutEdgeRef[]): LayoutNodeBox[] {
  let best = candidates[0];
  let bestScore = Number.POSITIVE_INFINITY;
  for (const candidate of candidates) {
    const score = scoreLayout(candidate, edges);
    if (score < bestScore) {
      best = candidate;
      bestScore = score;
    }
  }
  return best;
}

function scoreLayout(nodes: LayoutNodeBox[], edges: LayoutEdgeRef[]): number {
  const box = bounds(nodes);
  const width = Math.max(1, box.width);
  const height = Math.max(1, box.height);
  const aspect = width / height;
  const tallStackPenalty = height > width * 1.25 ? (height - width * 1.25) * 12 : 0;
  const wideRunawayPenalty = width > height * 4 ? (width - height * 4) * 2 : 0;
  // Accept any reasonably balanced shape (wide band); only nudge back extreme
  // aspect ratios, at a low weight, so spread-out layouts aren't forced compact.
  const ASPECT_LOW = 0.7;
  const ASPECT_HIGH = 2.6;
  const aspectPenalty =
    aspect < ASPECT_LOW ? Math.log(ASPECT_LOW / aspect) * 250 :
    aspect > ASPECT_HIGH ? Math.log(aspect / ASPECT_HIGH) * 250 :
    0;
  const edgeLengthPenalty = totalEdgeLength(nodes, edges) * 0.035;
  const overlapPenalty = totalOverlap(nodes) * 100000;
  // Light area penalty — enough to break ties toward compactness, not so much
  // that it crushes the diagram into a block.
  const areaPenalty = (width * height) * 0.00002;
  return tallStackPenalty + wideRunawayPenalty + aspectPenalty + edgeLengthPenalty + overlapPenalty + areaPenalty;
}

function bounds(nodes: LayoutNodeBox[]) {
  const minX = Math.min(...nodes.map((node) => node.x));
  const minY = Math.min(...nodes.map((node) => node.y));
  const maxX = Math.max(...nodes.map((node) => node.x + node.width));
  const maxY = Math.max(...nodes.map((node) => node.y + node.height));
  return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
}

function totalEdgeLength(nodes: LayoutNodeBox[], edges: LayoutEdgeRef[]): number {
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  return edges.reduce((sum, edge) => {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) return sum;
    const a = centerOf(source);
    const b = centerOf(target);
    return sum + Math.hypot(a.x - b.x, a.y - b.y);
  }, 0);
}

function totalOverlap(nodes: LayoutNodeBox[]): number {
  let total = 0;
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      total += overlapArea(nodes[i], nodes[j]);
    }
  }
  return total;
}

function byId(a: LayoutNodeBox, b: LayoutNodeBox) {
  return a.id.localeCompare(b.id);
}

function byDegree(edges: LayoutEdgeRef[]) {
  const degree = new Map<string, number>();
  for (const edge of edges) {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  }
  return (a: LayoutNodeBox, b: LayoutNodeBox) =>
    (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0) || a.id.localeCompare(b.id);
}
