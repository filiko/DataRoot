import type {
  DfdModel,
  DiagramLayout,
  DiagramScope,
  LayoutEdge,
  PenFile,
} from "../../../types/pen";
import type { LayoutEdgeRef, LayoutGraph, LayoutNodeBox, Point } from "./types";

type MeasuredFlowNode = {
  id: string;
  position?: Point;
  width?: number | null;
  height?: number | null;
  measured?: {
    width?: number | null;
    height?: number | null;
  };
};

export function buildDfdLayoutGraph(
  pen: PenFile,
  scope: DiagramScope,
  measuredNodes: MeasuredFlowNode[] = [],
): LayoutGraph {
  const dfd = dfdForScope(pen, scope);
  const layout = layoutForScope(pen, scope);
  const layoutMap = new Map(layout.nodes.map((node) => [node.id, node]));
  const measuredMap = new Map(measuredNodes.map((node) => [node.id, node]));
  const counters = { external: 0, process: 0, store: 0 };

  const nodes: LayoutNodeBox[] = [
    ...dfd.external_entities.map((node) => {
      const fallback = dfdFallback("dfd_external", counters.external++);
      return resolveNodeBox(node.id, "dfd_external", fallback, layoutMap.get(node.id), measuredMap.get(node.id));
    }),
    ...dfd.processes.map((node) => {
      const fallback = dfdFallback("dfd_process", counters.process++);
      return resolveNodeBox(node.id, "dfd_process", fallback, layoutMap.get(node.id), measuredMap.get(node.id));
    }),
    ...dfd.data_stores.map((node) => {
      const fallback = dfdFallback("dfd_store", counters.store++);
      return resolveNodeBox(node.id, "dfd_store", fallback, layoutMap.get(node.id), measuredMap.get(node.id));
    }),
  ];

  const edgeLayoutMap = new Map(layout.edges.map((edge) => [edge.id, edge]));
  const edges: LayoutEdgeRef[] = dfd.data_flows.map((flow) => {
    const edgeLayout = edgeLayoutMap.get(flow.id);
    return layoutEdgeRef(flow.id, flow.from, flow.to, flow.data_name, edgeLayout);
  });

  return { scope, nodes, edges };
}

export function buildErdLayoutGraph(
  pen: PenFile,
  measuredNodes: MeasuredFlowNode[] = [],
): LayoutGraph {
  const scope: DiagramScope = { diagram: "erd", level: "root" };
  const layout = pen.layout.erd;
  const layoutMap = new Map(layout.nodes.map((node) => [node.id, node]));
  const measuredMap = new Map(measuredNodes.map((node) => [node.id, node]));
  const visibleEntities = pen.erd.entities.filter((entity) => entity.review_status !== "rejected");

  const nodes = visibleEntities.map((entity, index) => {
    const fallback = {
      x: 60 + (index % 3) * 360,
      y: 60 + Math.floor(index / 3) * 260,
      width: 280,
      height: 80 + entity.attributes.filter((attr) => attr.review_status !== "rejected").length * 24,
    };
    return resolveNodeBox(entity.id, "erd_entity", fallback, layoutMap.get(entity.id), measuredMap.get(entity.id));
  });

  const edgeLayoutMap = new Map(layout.edges.map((edge) => [edge.id, edge]));
  const edges: LayoutEdgeRef[] = pen.erd.relationships
    .filter((rel) => rel.review_status !== "rejected")
    .map((rel) => {
      const edgeLayout = edgeLayoutMap.get(rel.id);
      return layoutEdgeRef(rel.id, rel.from.entity_id, rel.to.entity_id, rel.name, edgeLayout);
    });

  return { scope, nodes, edges };
}

export function dfdForScope(pen: PenFile, scope: DiagramScope): DfdModel {
  if (scope.diagram === "erd") return pen.dfd;
  if (scope.level === "process") {
    const process = pen.dfd.processes.find((item) => item.id === scope.process_id);
    return process?.level_1_diagram ?? pen.dfd;
  }
  return pen.dfd;
}

export function layoutForScope(pen: PenFile, scope: DiagramScope): DiagramLayout {
  if (scope.diagram === "erd") return pen.layout.erd;
  if (scope.level === "process") {
    return pen.layout.dfd_level_1[scope.process_id] ?? { nodes: [], edges: [] };
  }
  return pen.layout.dfd;
}

function layoutEdgeRef(
  id: string,
  source: string,
  target: string,
  label: string | undefined,
  edgeLayout: LayoutEdge | undefined,
): LayoutEdgeRef {
  return {
    id,
    source,
    target,
    label,
    sourceHandle: edgeLayout?.source_handle,
    targetHandle: edgeLayout?.target_handle,
    points: edgeLayout?.points,
    label_t: edgeLayout?.label_t,
    label_offset: edgeLayout?.label_offset,
  };
}

function resolveNodeBox(
  id: string,
  kind: LayoutNodeBox["kind"],
  fallback: Omit<LayoutNodeBox, "id" | "kind">,
  layoutNode: { x: number; y: number; width?: number; height?: number } | undefined,
  measuredNode: MeasuredFlowNode | undefined,
): LayoutNodeBox {
  return {
    id,
    kind,
    x: measuredNode?.position?.x ?? layoutNode?.x ?? fallback.x,
    y: measuredNode?.position?.y ?? layoutNode?.y ?? fallback.y,
    width: positive(measuredNode?.width) ?? positive(measuredNode?.measured?.width) ?? positive(layoutNode?.width) ?? fallback.width,
    height: positive(measuredNode?.height) ?? positive(measuredNode?.measured?.height) ?? positive(layoutNode?.height) ?? fallback.height,
  };
}

function positive(value: number | null | undefined): number | undefined {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value : undefined;
}

function dfdFallback(kind: LayoutNodeBox["kind"], index: number) {
  const base =
    kind === "dfd_external" ? { x: 40, y: 80, width: 230, height: 92 } :
    kind === "dfd_process" ? { x: 380, y: 80, width: 260, height: 92 } :
    { x: 760, y: 80, width: 230, height: 92 };
  return {
    ...base,
    y: base.y + index * 150,
  };
}
