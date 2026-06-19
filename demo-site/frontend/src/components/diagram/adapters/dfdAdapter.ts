import { MarkerType, type Edge, type Node } from "@xyflow/react";
import type {
  DataStore,
  DfdModel,
  DiagramLayout,
  DiagramScope,
  ExternalEntity,
  PenFile,
  Process,
} from "../../../types/pen";
import {
  HANDLE_LANES,
  handleId,
  type AttachmentSide,
} from "../attachmentHandleUtils";
import { getDiagramTheme, type DiagramThemeId } from "../../../styles/diagramThemes";
import { computeDisplayEdgeLayout } from "../layout/displayRouting";
import type { LayoutEdgeRef, LayoutNodeBox } from "../layout/types";

const DFD_KIND: Record<DfdNodeKind, LayoutNodeBox["kind"]> = {
  external: "dfd_external",
  process: "dfd_process",
  store: "dfd_store",
};

export type DfdNodeKind = "external" | "process" | "store";

export interface DfdNodeData extends Record<string, unknown> {
  kind: DfdNodeKind;
  label: string;
  number?: string;
  description?: string;
  hasLevel1?: boolean;
  isConnecting: boolean;
}

function layoutForScope(pen: PenFile, scope: DiagramScope): DiagramLayout {
  if (scope.diagram === "erd") return pen.layout.erd;
  if (scope.level === "process") {
    return pen.layout.dfd_level_1[scope.process_id] ?? { nodes: [], edges: [] };
  }
  return pen.layout.dfd;
}

function fallbackPosition(kind: DfdNodeKind, index: number) {
  const base =
    kind === "external" ? { x: 40, y: 60 } :
    kind === "process" ? { x: 360, y: 60 } :
    { x: 720, y: 60 };
  return {
    x: base.x,
    y: base.y + index * 140,
    width: kind === "process" ? 260 : 230,
    height: 92,
  };
}

function pickSides(source: Node<DfdNodeData>, target: Node<DfdNodeData>): {
  sourceSide: AttachmentSide;
  targetSide: AttachmentSide;
} {
  const sourceWidth = source.width ?? 230;
  const sourceHeight = source.height ?? 92;
  const targetWidth = target.width ?? 230;
  const targetHeight = target.height ?? 92;
  const sourceCenter = {
    x: source.position.x + sourceWidth / 2,
    y: source.position.y + sourceHeight / 2,
  };
  const targetCenter = {
    x: target.position.x + targetWidth / 2,
    y: target.position.y + targetHeight / 2,
  };
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;

  if (Math.abs(dx) >= Math.abs(dy)) {
    return dx >= 0
      ? { sourceSide: "right", targetSide: "left" }
      : { sourceSide: "left", targetSide: "right" };
  }

  return dy >= 0
    ? { sourceSide: "bottom", targetSide: "top" }
    : { sourceSide: "top", targetSide: "bottom" };
}

export function dfdToNodes(
  dfd: DfdModel,
  pen: PenFile,
  scope: DiagramScope,
  isConnecting: boolean,
): Node<DfdNodeData>[] {
  const layout = layoutForScope(pen, scope);
  const layoutMap = new Map(layout.nodes.map((node) => [node.id, node]));
  const counters: Record<DfdNodeKind, number> = { external: 0, process: 0, store: 0 };

  const mapNode = (
    id: string,
    kind: DfdNodeKind,
    label: string,
    number?: string,
    description?: string,
    hasLevel1?: boolean,
  ): Node<DfdNodeData> => {
    const fallback = fallbackPosition(kind, counters[kind]++);
    const position = layoutMap.get(id) ?? fallback;
    return {
      id,
      type: "dfdNode",
      position: { x: position.x, y: position.y },
      width: position.width,
      height: position.height,
      data: { kind, label, number, description, hasLevel1, isConnecting },
      draggable: true,
      selectable: true,
    };
  };

  return [
    ...dfd.external_entities.map((node: ExternalEntity) =>
      mapNode(node.id, "external", node.name, undefined, node.description),
    ),
    ...dfd.processes.map((node: Process) =>
      mapNode(node.id, "process", node.name, node.number, node.description, Boolean(node.level_1_diagram)),
    ),
    ...dfd.data_stores.map((node: DataStore) =>
      mapNode(node.id, "store", node.name, undefined, node.description),
    ),
  ];
}

export function dfdToEdges(
  dfd: DfdModel,
  pen: PenFile,
  scope: DiagramScope,
  nodes: Node<DfdNodeData>[],
  themeId: DiagramThemeId = "technical",
): Edge[] {
  const layout = layoutForScope(pen, scope);
  const edgeLayoutMap = new Map(layout.edges.map((edge) => [edge.id, edge]));
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const handleUseCounts = new Map<string, number>();
  const nextLane = (nodeId: string, side: AttachmentSide, type: "source" | "target") => {
    const key = `${nodeId}:${side}:${type}`;
    const count = handleUseCounts.get(key) ?? 0;
    handleUseCounts.set(key, count + 1);
    return HANDLE_LANES[count % HANDLE_LANES.length];
  };
  const theme = getDiagramTheme(themeId);

  // Compute orthogonal routes + collision-avoiding label positions for display
  // (nothing persisted) so flows whose layout was never saved don't fall back
  // to smooth-step midpoint labels sitting on top of / behind the nodes.
  const nodeBoxes: LayoutNodeBox[] = nodes.map((node) => ({
    id: node.id,
    kind: DFD_KIND[(node.data as DfdNodeData).kind],
    x: node.position.x,
    y: node.position.y,
    width: node.width ?? 230,
    height: node.height ?? 92,
  }));
  const edgeRefs: LayoutEdgeRef[] = dfd.data_flows.map((flow) => {
    const edgeLayout = edgeLayoutMap.get(flow.id);
    return {
      id: flow.id,
      source: flow.from,
      target: flow.to,
      label: flow.data_name,
      sourceHandle: edgeLayout?.source_handle,
      targetHandle: edgeLayout?.target_handle,
      points: edgeLayout?.points,
      label_t: edgeLayout?.label_t ?? undefined,
      label_offset: edgeLayout?.label_offset ?? undefined,
    };
  });
  const displayEdges = new Map(
    computeDisplayEdgeLayout(nodeBoxes, edgeRefs).map((edge) => [edge.id, edge]),
  );

  return dfd.data_flows.map((flow) => {
    const display = displayEdges.get(flow.id);
    const edgeLayout = edgeLayoutMap.get(flow.id);

    let sourceHandle = display?.sourceHandle ?? edgeLayout?.source_handle;
    let targetHandle = display?.targetHandle ?? edgeLayout?.target_handle;
    if (!sourceHandle || !targetHandle) {
      const sourceNode = nodeMap.get(flow.from);
      const targetNode = nodeMap.get(flow.to);
      const sides = sourceNode && targetNode
        ? pickSides(sourceNode, targetNode)
        : { sourceSide: "right" as AttachmentSide, targetSide: "left" as AttachmentSide };
      const sourceLane = nextLane(flow.from, sides.sourceSide, "source");
      const targetLane = nextLane(flow.to, sides.targetSide, "target");
      sourceHandle = sourceHandle ?? handleId("source", sides.sourceSide, sourceLane);
      targetHandle = targetHandle ?? handleId("target", sides.targetSide, targetLane);
    }

    return {
      id: flow.id,
      source: flow.from,
      target: flow.to,
      sourceHandle,
      targetHandle,
      label: flow.data_name,
      type: "dfdFlow",
      markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: theme.dfd.edge.stroke },
      style: {
        stroke: theme.dfd.edge.stroke,
        strokeWidth: 1.5,
        strokeDasharray: themeId === "chalkboard" ? "8 4" : undefined,
      },
      labelStyle: { color: theme.dfd.edge.labelText, fontSize: 11, fontWeight: 600 },
      data: {
        points: display?.points ?? edgeLayout?.points,
        label_t: display?.label_t ?? edgeLayout?.label_t,
        label_offset: display?.label_offset ?? edgeLayout?.label_offset,
      },
      reconnectable: true,
    };
  });
}

export function dfdToFlow(
  dfd: DfdModel,
  pen: PenFile,
  scope: DiagramScope,
  isConnecting: boolean,
  themeId: DiagramThemeId = "technical",
) {
  const nodes = dfdToNodes(dfd, pen, scope, isConnecting);
  return { nodes, edges: dfdToEdges(dfd, pen, scope, nodes, themeId) };
}

export function dfdNodeColor(node: Node, themeId: DiagramThemeId = "technical") {
  const kind = (node.data as DfdNodeData).kind;
  const theme = getDiagramTheme(themeId);
  if (kind === "external") return theme.dfd.external.border;
  if (kind === "store") return theme.dfd.store.border;
  return theme.dfd.process.border;
}
