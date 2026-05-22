import { createContext, useCallback, useContext, useMemo, useRef, useState, useEffect } from "react";
import {
  Background,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type EdgeTypes,
  type Node,
  type NodeTypes,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Boxes, GitBranch, HardDrive, Users, Wand2 } from "lucide-react";
import type { DfdModel, DiagramScope, PenFile } from "../types/pen";
import { useLayoutPatch } from "../hooks/useLayoutPatch";
import { useProjectOps } from "../hooks/useProjectOps";
import { AttachmentHandles } from "./diagram/AttachmentHandles";
import { EdgeLabelDragProvider } from "./diagram/EdgeLabelDragProvider";
import { EdgeContextMenu } from "./diagram/EdgeContextMenu";
import { SmartDiagramEdge } from "./diagram/SmartDiagramEdge";
import {
  dfdNodeColor,
  dfdToFlow,
  type DfdNodeData,
  type DfdNodeKind,
} from "./diagram/adapters/dfdAdapter";
import { buildDfdLayoutGraph } from "./diagram/layout/graphModel";
import {
  optimizeDiagramLayout,
  toLayoutEdgePatch,
  toLayoutNodePatch,
} from "./diagram/layout/optimizeLayout";
import { useAppTheme, DiagramThemeProvider, useDiagramTheme } from "../context/ThemeContext";

type DiagramOption = {
  id: string;
  label: string;
  dfd: DfdModel;
  scope: DiagramScope;
};

type SaveStatus = "idle" | "saving" | "saved" | "error";

const DfdConnectionCtx = createContext(false);

function iconForKind(kind: DfdNodeKind) {
  if (kind === "external") return <Users className="w-4 h-4" />;
  if (kind === "store") return <HardDrive className="w-4 h-4" />;
  return <GitBranch className="w-4 h-4" />;
}

function DfdNode({ data }: { data: DfdNodeData }) {
  const isConnecting = useContext(DfdConnectionCtx);
  const { theme, themeId } = useDiagramTheme();
  const tokens = data.kind === "external" ? theme.dfd.external
    : data.kind === "store" ? theme.dfd.store
    : theme.dfd.process;
  const isChalkboard = themeId === "chalkboard";

  const borderRadius = data.kind === "process" ? 18 : 6;
  const storeStyle = data.kind === "store"
    ? { borderLeftWidth: 6, borderRightWidth: 6, borderLeftColor: tokens.lightAccent, borderRightColor: tokens.lightAccent }
    : {};

  return (
    <div
      style={{
        minWidth: 210,
        minHeight: 78,
        border: `1.5px ${isChalkboard ? "dashed" : "solid"} ${tokens.border}`,
        borderRadius,
        background: tokens.header,
        boxShadow: isChalkboard ? "none" : "0 1px 3px rgba(15, 23, 42, 0.10)",
        overflow: "visible",
        position: "relative",
        ...storeStyle,
      }}
    >
      <AttachmentHandles
        visible={data.isConnecting || isConnecting}
        sourceTitle="Drag data flow from here"
        targetTitle="Drop data flow here"
        sourceColor={tokens.accent}
        targetColor={tokens.header}
        sourceBorder={tokens.header}
        targetBorder={tokens.accent}
      />

      <div style={{ overflow: "hidden", borderRadius }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "8px 10px",
            background: tokens.header,
            borderBottom: `1px solid ${tokens.border}22`,
            color: tokens.text,
          }}
        >
          <span style={{ color: tokens.accent, display: "inline-flex", flexShrink: 0 }}>
            {iconForKind(data.kind)}
          </span>
          {data.number && (
            <span
              style={{
                flexShrink: 0,
                border: `1px solid ${tokens.border}`,
                borderRadius: 999,
                padding: "1px 6px",
                fontSize: 11,
                fontWeight: 700,
                color: tokens.accent,
                background: isChalkboard ? theme.canvas.bg : "#fff",
              }}
            >
              {data.number}
            </span>
          )}
          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              lineHeight: 1.25,
              color: tokens.text,
              overflowWrap: "anywhere",
            }}
          >
            {data.label}
          </span>
        </div>

        {(data.description || data.hasLevel1) && (
          <div style={{ padding: "8px 10px", color: tokens.text, fontSize: 11, lineHeight: 1.35, opacity: 0.75 }}>
            {data.description && (
              <div style={{ display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                {data.description}
              </div>
            )}
            {data.hasLevel1 && (
              <div style={{ marginTop: data.description ? 6 : 0, color: tokens.accent, fontWeight: 700 }}>
                Level 1 diagram available
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { dfdNode: DfdNode };
const edgeTypes: EdgeTypes = { dfdFlow: SmartDiagramEdge };

interface DFDCanvasProps {
  pen: PenFile;
  projectId: string;
  onPenUpdate: (updated: PenFile) => void;
}

interface DfdFlowViewProps {
  pen: PenFile;
  projectId: string;
  active: DiagramOption;
  onPenUpdate: (updated: PenFile) => void;
  onSaveStatus: (status: SaveStatus) => void;
}

function DfdFlowView({
  pen,
  projectId,
  active,
  onPenUpdate,
  onSaveStatus,
}: DfdFlowViewProps) {
  const { theme, themeId } = useDiagramTheme();
  const [isConnecting, setIsConnecting] = useState(false);
  const initialFlow = useMemo(
    () => dfdToFlow(active.dfd, pen, active.scope, false, themeId),
    [active.dfd, active.scope, pen, themeId],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; edgeId: string } | null>(null);
  const dragSaveTimer = useRef<number | null>(null);
  const isDragging = useRef(false);
  const reactFlowRef = useRef<ReactFlowInstance<Node<DfdNodeData>, Edge> | null>(null);
  const { patchLayout } = useLayoutPatch(projectId);
  const { runOps } = useProjectOps(projectId);

  useEffect(() => () => {
    if (dragSaveTimer.current !== null) {
      window.clearTimeout(dragSaveTimer.current);
    }
  }, []);

  useEffect(() => {
    if (isDragging.current) return;
    setNodes(initialFlow.nodes);
    setEdges(initialFlow.edges);
  }, [initialFlow, setNodes, setEdges]);

  const saveNodePosition = useCallback((node: Node) => {
    if (dragSaveTimer.current !== null) {
      window.clearTimeout(dragSaveTimer.current);
    }

    dragSaveTimer.current = window.setTimeout(async () => {
      onSaveStatus("saving");
      try {
        const updated = await patchLayout({
          scope: active.scope,
          baseRevision: pen.project.revision,
          nodes: [{
            id: node.id,
            x: node.position.x,
            y: node.position.y,
            width: node.width,
            height: node.height,
          }],
        });
        onPenUpdate(updated);
        onSaveStatus("saved");
      } catch (err) {
        console.error(err);
        onSaveStatus("error");
      }
    }, 500);
  }, [active.scope, onPenUpdate, onSaveStatus, patchLayout, pen.project.revision]);

  const onReconnect = useCallback(async (oldEdge: Edge, connection: Connection) => {
    if (!connection.source || !connection.target) return;
    onSaveStatus("saving");
    try {
      const updated = await runOps([{
        op: "dfd.flow.reconnect",
        payload: {
          scope: active.scope,
          id: oldEdge.id,
          from: connection.source,
          to: connection.target,
          source_handle: connection.sourceHandle,
          target_handle: connection.targetHandle,
        },
      }], {
        baseRevision: pen.project.revision,
        propagate: false,
      });
      onPenUpdate(updated);
      onSaveStatus("saved");
    } catch (err) {
      console.error(err);
      onSaveStatus("error");
    } finally {
      setIsConnecting(false);
    }
  }, [active.scope, onPenUpdate, onSaveStatus, pen.project.revision, runOps]);

  const contextEdge = contextMenu
    ? active.dfd.data_flows.find((flow) => flow.id === contextMenu.edgeId)
    : null;

  const renameEdge = useCallback(async () => {
    if (!contextEdge) return;
    const nextName = window.prompt("Data flow label", contextEdge.data_name ?? "");
    setContextMenu(null);
    if (nextName === null) return;

    onSaveStatus("saving");
    try {
      const updated = await runOps([{
        op: "dfd.flow.rename",
        payload: {
          scope: active.scope,
          id: contextEdge.id,
          data_name: nextName,
        },
      }], {
        baseRevision: pen.project.revision,
        propagate: false,
      });
      onPenUpdate(updated);
      onSaveStatus("saved");
    } catch (err) {
      console.error(err);
      onSaveStatus("error");
    }
  }, [active.scope, contextEdge, onPenUpdate, onSaveStatus, pen.project.revision, runOps]);

  const deleteEdge = useCallback(async () => {
    if (!contextEdge) return;
    const confirmed = window.confirm(`Delete data flow "${contextEdge.data_name || contextEdge.id}"?`);
    setContextMenu(null);
    if (!confirmed) return;

    onSaveStatus("saving");
    try {
      const updated = await runOps([{
        op: "dfd.flow.delete",
        payload: {
          scope: active.scope,
          id: contextEdge.id,
        },
      }], {
        baseRevision: pen.project.revision,
        propagate: false,
      });
      onPenUpdate(updated);
      onSaveStatus("saved");
    } catch (err) {
      console.error(err);
      onSaveStatus("error");
    }
  }, [active.scope, contextEdge, onPenUpdate, onSaveStatus, pen.project.revision, runOps]);

  const autoArrange = useCallback(async () => {
    onSaveStatus("saving");
    try {
      const measuredNodes = reactFlowRef.current?.getNodes() ?? nodes;
      const graph = buildDfdLayoutGraph(pen, active.scope, measuredNodes);
      const result = await optimizeDiagramLayout(graph, { mode: "auto", gridSize: 24 });
      const updated = await patchLayout({
        scope: active.scope,
        baseRevision: pen.project.revision,
        nodes: result.nodes.map(toLayoutNodePatch),
        edges: result.edges.map(toLayoutEdgePatch),
      });
      onPenUpdate(updated);
      onSaveStatus("saved");
    } catch (err) {
      console.error(err);
      onSaveStatus("error");
    }
  }, [active.scope, nodes, onPenUpdate, onSaveStatus, patchLayout, pen]);

  const moveEdgeLabel = useCallback(async (edgeId: string, labelT: number, labelOffset: number) => {
    onSaveStatus("saving");
    try {
      const updated = await patchLayout({
        scope: active.scope,
        baseRevision: pen.project.revision,
        edges: [{
          id: edgeId,
          label_t: labelT,
          label_offset: labelOffset,
        }],
      });
      onPenUpdate(updated);
      onSaveStatus("saved");
    } catch (err) {
      console.error(err);
      onSaveStatus("error");
    }
  }, [active.scope, onPenUpdate, onSaveStatus, patchLayout, pen.project.revision]);

  return (
    <>
      <EdgeLabelDragProvider onLabelMove={moveEdgeLabel}>
        <DfdConnectionCtx.Provider value={isConnecting}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onInit={(instance) => {
              reactFlowRef.current = instance;
            }}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeDragStart={() => { isDragging.current = true; }}
            onNodeDragStop={(_, node) => { isDragging.current = false; saveNodePosition(node); }}
            onConnectStart={() => setIsConnecting(true)}
            onConnectEnd={() => setIsConnecting(false)}
            onReconnectStart={() => setIsConnecting(true)}
            onReconnectEnd={() => setIsConnecting(false)}
            onReconnect={onReconnect}
            onEdgeContextMenu={(event, edge) => {
              event.preventDefault();
              setContextMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
            }}
            onEdgeClick={(event, edge) => {
              event.preventDefault();
              setContextMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
            }}
            onPaneClick={() => setContextMenu(null)}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            nodesDraggable
            nodesConnectable
            elementsSelectable
            edgesReconnectable
            reconnectRadius={18}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            proOptions={{ hideAttribution: true }}
          >
            <Panel position="top-left">
              <button
                onClick={autoArrange}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-slate-200 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50"
              >
                <Wand2 className="w-3.5 h-3.5" />
                Auto Arrange
              </button>
            </Panel>
            <Background color={theme.canvas.grid} gap={24} />
            <MiniMap nodeColor={(n) => dfdNodeColor(n, themeId)} pannable zoomable />
            <Controls showInteractive={false} />
          </ReactFlow>
        </DfdConnectionCtx.Provider>
      </EdgeLabelDragProvider>

      {contextMenu && contextEdge && (
        <EdgeContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          label={contextEdge.data_name}
          onRename={renameEdge}
          onDelete={deleteEdge}
        />
      )}
    </>
  );
}

export function DFDCanvas({ pen, projectId, onPenUpdate }: DFDCanvasProps) {
  const [activeId, setActiveId] = useState("root");
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const { diagramThemeId } = useAppTheme();
  const { theme } = useDiagramTheme();
  const diagrams = useMemo<DiagramOption[]>(() => [
    { id: "root", label: "Context", dfd: pen.dfd, scope: { diagram: "dfd", level: "root" } },
    ...pen.dfd.processes
      .filter((process) => process.level_1_diagram)
      .map((process) => ({
        id: process.id,
        label: `${process.number ?? ""} ${process.name}`.trim(),
        dfd: process.level_1_diagram!,
        scope: { diagram: "dfd" as const, level: "process" as const, process_id: process.id },
      })),
  ], [pen]);

  const active = diagrams.find((diagram) => diagram.id === activeId) ?? diagrams[0];

  return (
    <DiagramThemeProvider themeId={diagramThemeId}>
    <div className="h-full flex flex-col" style={{ background: theme.canvas.bg }}>
      <div className="flex items-center justify-between gap-3 px-4 py-3 bg-white border-b border-gray-200">
        <div className="flex items-center gap-2 min-w-0">
          <Boxes className="w-4 h-4 text-blue-600 flex-shrink-0" />
          <div className="min-w-0">
            <div className="text-sm font-semibold text-gray-900 truncate">{active.dfd.system_boundary.name}</div>
            <div className="text-xs text-gray-500">
              {active.dfd.external_entities.length} external | {active.dfd.processes.length} processes | {active.dfd.data_stores.length} stores | {active.dfd.data_flows.length} flows
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap justify-end">
          {saveStatus !== "idle" && (
            <span
              className={`text-xs font-medium ${
                saveStatus === "error" ? "text-red-600" :
                saveStatus === "saving" ? "text-blue-600" :
                "text-emerald-600"
              }`}
            >
              {saveStatus === "saving" ? "Saving..." : saveStatus === "saved" ? "Saved" : "Save failed"}
            </span>
          )}
          {diagrams.map((diagram) => (
            <button
              key={diagram.id}
              onClick={() => setActiveId(diagram.id)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                active.id === diagram.id
                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                  : "text-gray-600 hover:bg-gray-100 border border-transparent"
              }`}
            >
              {diagram.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {active.dfd.external_entities.length + active.dfd.processes.length + active.dfd.data_stores.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-gray-500">
            No DFD objects in this project.
          </div>
        ) : (
          <DfdFlowView
            key={`${active.id}:${pen.project.revision}`}
            pen={pen}
            projectId={projectId}
            active={active}
            onPenUpdate={onPenUpdate}
            onSaveStatus={setSaveStatus}
          />
        )}
      </div>
    </div>
    </DiagramThemeProvider>
  );
}
