import type { DiagramScope } from "../../../types/pen";
import type { AttachmentSide } from "../attachmentHandleUtils";

export type Point = { x: number; y: number };

export type Rect = {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type LayoutNodeKind = "erd_entity" | "dfd_external" | "dfd_process" | "dfd_store";

export type LayoutNodeBox = Rect & {
  kind: LayoutNodeKind;
};

export type LayoutEdgeRef = {
  id: string;
  source: string;
  target: string;
  label?: string;
  sourceHandle?: string;
  targetHandle?: string;
  points?: Point[];
  label_t?: number;
  label_offset?: number;
};

export type PlacedLabel = Rect & {
  edgeId: string;
  anchor: Point;
  t: number;
  offset: number;
};

export type RoutedEdge = LayoutEdgeRef & {
  sourceHandle: string;
  targetHandle: string;
  points: Point[];
  label?: string;
  placedLabel?: PlacedLabel;
};

export type LayoutGraph = {
  scope: DiagramScope;
  nodes: LayoutNodeBox[];
  edges: LayoutEdgeRef[];
};

export type LayoutOptimizationMode = "auto" | "tidy";

export type LayoutOptimizationOptions = {
  mode: LayoutOptimizationMode;
  gridSize?: number;
  nodeGap?: number;
};

export type LayoutOptimizationResult = {
  nodes: LayoutNodeBox[];
  edges: RoutedEdge[];
};

export type ParsedHandle = {
  kind: "source" | "target";
  side: AttachmentSide;
  lane: number;
};
