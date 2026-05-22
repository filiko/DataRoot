import React, {
  useMemo, useCallback, useState, useEffect, useRef,
  useContext, createContext,
} from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  BaseEdge,
  getSmoothStepPath,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeProps,
  type EdgeTypes,
  type ReactFlowInstance,
  Position,
  Handle,
  useNodesState,
  useEdgesState,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Plus, Pencil, X, Wand2 } from "lucide-react";
import type {
  Entity, Attribute, PenFile, Relationship,
  KeyRole, ReviewStatus, Cardinality,
} from "../types/pen";
import { useLayoutPatch } from "../hooks/useLayoutPatch";
import { DraggableEdgeLabel } from "./diagram/DraggableEdgeLabel";
import { EdgeLabelDragProvider } from "./diagram/EdgeLabelDragProvider";
import { buildErdLayoutGraph } from "./diagram/layout/graphModel";
import {
  optimizeDiagramLayout,
  toLayoutEdgePatch,
  toLayoutNodePatch,
} from "./diagram/layout/optimizeLayout";
import type { Point } from "./diagram/layout/types";
import { useAppTheme, DiagramThemeProvider, useDiagramTheme } from "../context/ThemeContext";
import { getDiagramTheme, type DiagramThemeId } from "../styles/diagramThemes";

const API = "";

type AttachmentSide = "left" | "right" | "top" | "bottom";

const ATTACHMENT_SIDES: AttachmentSide[] = ["left", "right", "top", "bottom"];
const HANDLE_LANES = [0, 1, 2] as const;
const HANDLE_LANE_POSITIONS = [26, 50, 74] as const;
const HANDLE_POSITION: Record<AttachmentSide, Position> = {
  left: Position.Left,
  right: Position.Right,
  top: Position.Top,
  bottom: Position.Bottom,
};

function handleId(type: "source" | "target", side: AttachmentSide, lane: number) {
  return `${type}-${side}-${lane}`;
}

function handleStyle(
  side: AttachmentSide,
  lane: number,
  type: "source" | "target",
  visible: boolean,
  color?: string,
  border?: string,
): React.CSSProperties {
  const isHorizontalSide = side === "top" || side === "bottom";
  const size = 9;
  const offset = -5;
  const lanePosition = `${HANDLE_LANE_POSITIONS[lane] + (type === "source" ? -4 : 4)}%`;
  const style: React.CSSProperties = {
    width: size,
    height: size,
    borderRadius: 999,
    border: `2px solid ${border ?? (type === "source" ? "#fff" : "#6366f1")}`,
    background: color ?? (type === "source" ? "#6366f1" : "#fff"),
    opacity: visible ? 0.9 : 0,
    boxShadow: visible ? "0 1px 4px rgba(79,70,229,0.30)" : "none",
    transition: "opacity 120ms ease, box-shadow 120ms ease",
    pointerEvents: visible ? "auto" : "none",
    cursor: visible ? "crosshair" : "default",
    zIndex: 2,
  };

  if (isHorizontalSide) {
    style.left = lanePosition;
    style.top = side === "top" ? offset : undefined;
    style.bottom = side === "bottom" ? offset : undefined;
  } else {
    style.top = lanePosition;
    style.left = side === "left" ? offset : undefined;
    style.right = side === "right" ? offset : undefined;
  }

  return style;
}

// ── Entity actions context (avoids embedding callbacks in node data) ──────────

interface EntityActions {
  onEdit: (entity: Entity) => void;
  onDelete: (entity: Entity) => void;
}

const EntityActionsCtx = createContext<EntityActions>({
  onEdit: () => {},
  onDelete: () => {},
});

// ── Inline attr edit context ─────────────────────────────────────────────────

const InlineEditCtx = createContext<{
  editingId: string | null;
  setEditingId: (id: string | null) => void;
  isConnecting: boolean;
}>({ editingId: null, setEditingId: () => {}, isConnecting: false });

// ── Attribute row ─────────────────────────────────────────────────────────────

function AttributeRow({ attr }: { attr: Attribute }) {
  const { editingId, setEditingId } = useContext(InlineEditCtx);
  const { theme } = useDiagramTheme();
  const isEditing = editingId === attr.id;
  const [value, setValue] = useState(attr.name);

  const prefix =
    attr.key_role === "primary" ? "PK" :
    attr.key_role === "foreign" ? "FK" :
    attr.key_role === "unique"  ? "UQ" :
    attr.key_role === "business_key" ? "BK" : "";

  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "28px 1fr auto",
      gap: 4,
      padding: "2px 8px",
      fontSize: 12,
      borderTop: `1px solid ${theme.erd.entity.border}22`,
      background: attr.key_role === "primary" ? theme.erd.pkBadge.bg : "transparent",
      fontWeight: attr.key_role === "primary" ? 600 : 400,
      color: attr.review_status === "rejected" ? `${theme.erd.entity.text}55` : theme.erd.entity.text,
    }}>
      <span style={{ color: theme.erd.entity.accent, fontSize: 10, fontWeight: 600, alignSelf: "center" }}>
        {prefix}
      </span>
      {isEditing ? (
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => setEditingId(null)}
          onKeyDown={(e) => { if (e.key === "Enter") setEditingId(null); }}
          style={{
            border: `1px solid ${theme.erd.entity.accent}`, borderRadius: 4,
            padding: "1px 4px", fontSize: 12, outline: "none",
            background: "#fff",
          }}
        />
      ) : (
        <span
          onDoubleClick={() => {
            setValue(attr.name);
            setEditingId(attr.id);
          }}
          style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", cursor: "text" }}
        >
          {attr.name}
        </span>
      )}
      <span style={{ color: theme.erd.entity.accent, fontSize: 11, fontFamily: "monospace" }}>
        {attr.pg_type}
      </span>
    </div>
  );
}

// ── Table node ────────────────────────────────────────────────────────────────

interface TableNodeData {
  entity: Entity;
  [key: string]: unknown;
}

function TableNode({ data }: { data: TableNodeData }) {
  const { entity } = data;
  const { onEdit, onDelete } = useContext(EntityActionsCtx);
  const { isConnecting } = useContext(InlineEditCtx);
  const { theme, themeId } = useDiagramTheme();
  const isLookup = entity.kind === "lookup_table";
  const tokens = isLookup
    ? { border: "#d1d5db", header: "#f9fafb", text: "#1f2937", accent: "#6b7280" }
    : { border: theme.erd.entity.border, header: theme.erd.entity.header, text: theme.erd.entity.text, accent: theme.erd.entity.accent };
  const isChalkboard = themeId === "chalkboard";

  return (
    <div style={{
      background: isChalkboard ? theme.erd.entity.header : "#fff",
      border: `1.5px ${isChalkboard ? "dashed" : "solid"} ${tokens.border}`,
      borderRadius: 8,
      minWidth: 260,
      boxShadow: isChalkboard ? "none" : "0 1px 3px rgba(0,0,0,0.08)",
      overflow: "visible",
      fontSize: 13,
    }}>
      {/* Entity handles */}
      {ATTACHMENT_SIDES.map((side) =>
        HANDLE_LANES.map((lane) => (
          <React.Fragment key={`${side}-${lane}`}>
            <Handle
              id={handleId("target", side, lane)}
              type="target"
              position={HANDLE_POSITION[side]}
              title="Drop relationship here"
              style={handleStyle(side, lane, "target", isConnecting, theme.erd.entity.header, tokens.accent)}
            />
            <Handle
              id={handleId("source", side, lane)}
              type="source"
              position={HANDLE_POSITION[side]}
              title="Drag relationship from here"
              style={handleStyle(side, lane, "source", isConnecting, tokens.accent, theme.erd.entity.header)}
            />
          </React.Fragment>
        )),
      )}

      {/* Header */}
      <div style={{
        padding: "6px 8px",
        background: tokens.header,
        borderBottom: "1.5px solid",
        borderColor: tokens.border,
        display: "flex",
        alignItems: "center",
        gap: 6,
      }}>
        <span style={{ fontSize: 14 }}>{isLookup ? "📋" : "🗂"}</span>
        <span style={{ fontWeight: 600, color: tokens.text, letterSpacing: "-0.01em", flex: 1 }}>
          {entity.display_name || entity.name}
        </span>
        {entity.review_status === "needs_review" && (
          <span style={{
            fontSize: 10,
            background: "#fef3c7",
            color: "#92400e",
            borderRadius: 4,
            padding: "1px 5px",
            fontWeight: 600,
          }}>review</span>
        )}
        {/* Edit / delete buttons */}
        <button
          onClick={() => onEdit(entity)}
          title="Edit entity"
          style={{
            border: "none", background: "transparent", cursor: "pointer",
            padding: "2px 4px", borderRadius: 4, color: tokens.accent,
            display: "flex", alignItems: "center",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = `${tokens.accent}22`)}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <Pencil size={12} />
        </button>
        <button
          onClick={() => onDelete(entity)}
          title="Delete entity"
          style={{
            border: "none", background: "transparent", cursor: "pointer",
            padding: "2px 4px", borderRadius: 4, color: "#ef4444",
            display: "flex", alignItems: "center",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "#fee2e2")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <X size={12} />
        </button>
      </div>

      {/* Attributes */}
      <div>
        {entity.attributes
          .filter((a) => a.review_status !== "rejected")
          .map((attr) => (
            <AttributeRow key={attr.id} attr={attr} />
          ))}
      </div>
    </div>
  );
}

const nodeTypes: NodeTypes = { tableNode: TableNode };

type CardinalityEdgeData = {
  cardinality?: Cardinality;
  points?: Point[];
  label_t?: number | null;
  label_offset?: number | null;
};

function markerVector(position: Position | undefined) {
  switch (position) {
    case Position.Left:
      return { dx: -1, dy: 0, px: 0, py: 1 };
    case Position.Right:
      return { dx: 1, dy: 0, px: 0, py: 1 };
    case Position.Top:
      return { dx: 0, dy: -1, px: 1, py: 0 };
    case Position.Bottom:
    default:
      return { dx: 0, dy: 1, px: 1, py: 0 };
  }
}

function CardinalityMarker({
  x,
  y,
  position,
  max,
  stroke,
}: {
  x: number;
  y: number;
  position: Position | undefined;
  max: number | "many" | undefined;
  stroke: string;
}) {
  const { dx, dy, px, py } = markerVector(position);
  const centerX = x + dx * 12;
  const centerY = y + dy * 12;
  const half = 7;

  if (max === "many") {
    const tipX = x + dx * 22;
    const tipY = y + dy * 22;
    return (
      <g pointerEvents="none" stroke={stroke} strokeWidth={1.6} strokeLinecap="round" fill="none">
        <line x1={tipX} y1={tipY} x2={centerX + px * half} y2={centerY + py * half} />
        <line x1={tipX} y1={tipY} x2={centerX} y2={centerY} />
        <line x1={tipX} y1={tipY} x2={centerX - px * half} y2={centerY - py * half} />
      </g>
    );
  }

  return (
    <g pointerEvents="none" stroke={stroke} strokeWidth={1.8} strokeLinecap="round">
      <line
        x1={centerX - px * half}
        y1={centerY - py * half}
        x2={centerX + px * half}
        y2={centerY + py * half}
      />
    </g>
  );
}

function CardinalityEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  label,
  labelStyle,
  data,
}: EdgeProps & { data?: CardinalityEdgeData }) {
  const [fallbackPath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const stroke = typeof style?.stroke === "string" ? style.stroke : "#6366f1";

  return (
    <>
      <BaseEdge
        id={id}
        path={fallbackPath}
        style={{ ...style, cursor: "pointer" }}
        interactionWidth={28}
      />
      <CardinalityMarker
        x={sourceX}
        y={sourceY}
        position={sourcePosition}
        max={data?.cardinality?.from_max}
        stroke={stroke}
      />
      <CardinalityMarker
        x={targetX}
        y={targetY}
        position={targetPosition}
        max={data?.cardinality?.to_max}
        stroke={stroke}
      />
      {label && (
        <DraggableEdgeLabel
          edgeId={id}
          fallbackX={labelX}
          fallbackY={labelY}
          labelT={data?.label_t}
          labelOffset={data?.label_offset}
          style={labelStyle}
        >
          {label}
        </DraggableEdgeLabel>
      )}
    </>
  );
}

const edgeTypes: EdgeTypes = { cardinality: CardinalityEdge };

// ── PenFile → React Flow nodes & edges ───────────────────────────────────────

function penToFlow(pen: PenFile, themeId: DiagramThemeId = "technical"): { nodes: Node[]; edges: Edge[] } {
  const t = getDiagramTheme(themeId);
  const layoutMap: Record<string, { x: number; y: number; width: number; height: number }> = {};
  pen.layout.erd.nodes.forEach((n) => {
    layoutMap[n.id] = {
      x: n.x,
      y: n.y,
      width: n.width || 280,
      height: n.height || 180,
    };
  });
  const edgeLayoutMap = new Map(pen.layout.erd.edges.map((edge) => [edge.id, edge]));

  const nodes: Node[] = pen.erd.entities
    .filter((e) => e.review_status !== "rejected")
    .map((entity) => ({
      id: entity.id,
      type: "tableNode",
      position: layoutMap[entity.id] ?? { x: 100, y: 100 },
      data: { entity } as TableNodeData,
    }));

  const handleUseCounts = new Map<string, number>();
  const nextLane = (entityId: string, side: AttachmentSide, type: "source" | "target") => {
    const key = `${entityId}:${side}:${type}`;
    const count = handleUseCounts.get(key) ?? 0;
    handleUseCounts.set(key, count + 1);
    return HANDLE_LANES[count % HANDLE_LANES.length];
  };
  const pickSides = (sourceId: string, targetId: string): {
    sourceSide: AttachmentSide;
    targetSide: AttachmentSide;
  } => {
    const source = layoutMap[sourceId] ?? { x: 0, y: 0, width: 280, height: 180 };
    const target = layoutMap[targetId] ?? { x: 340, y: 0, width: 280, height: 180 };
    const sourceCenter = {
      x: source.x + source.width / 2,
      y: source.y + source.height / 2,
    };
    const targetCenter = {
      x: target.x + target.width / 2,
      y: target.y + target.height / 2,
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
  };

  const edges: Edge[] = pen.erd.relationships
    .filter((r) => r.review_status !== "rejected")
    .map((rel) => {
      const { sourceSide, targetSide } = pickSides(rel.from.entity_id, rel.to.entity_id);
      const sourceLane = nextLane(rel.from.entity_id, sourceSide, "source");
      const targetLane = nextLane(rel.to.entity_id, targetSide, "target");
      const edgeLayout = edgeLayoutMap.get(rel.id);
      const isChalkboard = themeId === "chalkboard";

      return {
        id: rel.id,
        source: rel.from.entity_id,
        target: rel.to.entity_id,
        sourceHandle: edgeLayout?.source_handle ?? handleId("source", sourceSide, sourceLane),
        targetHandle: edgeLayout?.target_handle ?? handleId("target", targetSide, targetLane),
        type: "cardinality",
        label: rel.name,
        labelStyle: { fontSize: 11, fill: t.erd.relationship.labelText },
        style: {
          stroke: t.erd.relationship.stroke,
          strokeWidth: 1.5,
          strokeDasharray: isChalkboard ? "8 4" : undefined,
        },
        data: {
          cardinality: rel.cardinality,
          points: edgeLayout?.points,
          label_t: edgeLayout?.label_t,
          label_offset: edgeLayout?.label_offset,
        },
        reconnectable: true,
        animated: false,
      };
    });

  return { nodes, edges };
}

// ── Entity dialog ─────────────────────────────────────────────────────────────

interface AttrRow {
  id: string;
  name: string;
  pg_type: string;
  key_role: string;
}

const PG_TYPES = ["text", "integer", "numeric", "boolean", "date", "timestamptz", "uuid"];
const KEY_ROLES: Array<{ value: string; label: string }> = [
  { value: "none", label: "—" },
  { value: "unique", label: "Unique" },
  { value: "foreign", label: "FK" },
];

interface EntityDialogProps {
  open: boolean;
  editTarget: Entity | null;
  onClose: () => void;
  onConfirm: (name: string, displayName: string, attrs: AttrRow[]) => void;
  saving: boolean;
}

function EntityDialog({ open, editTarget, onClose, onConfirm, saving }: EntityDialogProps) {
  const [entityName, setEntityName] = useState("");
  const [attrRows, setAttrRows] = useState<AttrRow[]>([]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!open) return;
    if (editTarget) {
      setEntityName(editTarget.display_name || editTarget.name);
      setAttrRows(
        editTarget.attributes
          .filter((a) => a.key_role !== "primary" && a.key_role !== "audit")
          .map((a) => ({ id: a.id, name: a.name, pg_type: a.pg_type, key_role: a.key_role }))
      );
    } else {
      setEntityName("");
      setAttrRows([]);
    }
  }, [open, editTarget]);
  /* eslint-enable react-hooks/set-state-in-effect */

  if (!open) return null;

  const addRow = () =>
    setAttrRows((r) => [
      ...r,
      { id: `new_${Date.now()}`, name: "", pg_type: "text", key_role: "none" },
    ]);

  const updateRow = (idx: number, field: keyof AttrRow, val: string) =>
    setAttrRows((rows) => rows.map((r, i) => (i === idx ? { ...r, [field]: val } : r)));

  const removeRow = (idx: number) => setAttrRows((rows) => rows.filter((_, i) => i !== idx));

  const handleConfirm = () => {
    const trimmed = entityName.trim();
    if (!trimmed) return;
    onConfirm(
      trimmed.toLowerCase().replace(/\s+/g, "_"),
      trimmed,
      attrRows.filter((r) => r.name.trim()),
    );
  };

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={onClose}>
      <div style={{
        background: "#fff", borderRadius: 12, width: 440,
        boxShadow: "0 8px 32px rgba(0,0,0,0.18)", padding: 24,
      }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 16px", fontSize: 16, fontWeight: 700, color: "#1e1b4b" }}>
          {editTarget ? "Edit entity" : "Add entity"}
        </h2>

        <label style={{ display: "block", fontSize: 13, color: "#374151", marginBottom: 4 }}>
          Entity name
        </label>
        <input
          autoFocus
          value={entityName}
          onChange={(e) => setEntityName(e.target.value)}
          placeholder="e.g. Customers"
          style={{
            width: "100%", boxSizing: "border-box",
            border: "1.5px solid #d1d5db", borderRadius: 6, padding: "6px 10px",
            fontSize: 14, outline: "none", marginBottom: 16,
          }}
          onKeyDown={(e) => { if (e.key === "Enter") handleConfirm(); }}
        />

        <div style={{ marginBottom: 8, fontSize: 13, fontWeight: 600, color: "#374151" }}>
          Attributes
          <span style={{ fontSize: 11, fontWeight: 400, color: "#9ca3af", marginLeft: 8 }}>
            (PK + timestamps added automatically)
          </span>
        </div>

        {attrRows.map((row, idx) => (
          <div key={row.id} style={{ display: "flex", gap: 6, marginBottom: 6, alignItems: "center" }}>
            <input
              value={row.name}
              onChange={(e) => updateRow(idx, "name", e.target.value)}
              placeholder="column_name"
              style={{
                flex: 2, border: "1px solid #d1d5db", borderRadius: 6,
                padding: "4px 8px", fontSize: 12,
              }}
            />
            <select
              value={row.pg_type}
              onChange={(e) => updateRow(idx, "pg_type", e.target.value)}
              style={{ flex: 1, border: "1px solid #d1d5db", borderRadius: 6, padding: "4px 6px", fontSize: 12 }}
            >
              {PG_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <select
              value={row.key_role}
              onChange={(e) => updateRow(idx, "key_role", e.target.value)}
              style={{ flex: 1, border: "1px solid #d1d5db", borderRadius: 6, padding: "4px 6px", fontSize: 12 }}
            >
              {KEY_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <button
              onClick={() => removeRow(idx)}
              style={{
                border: "none", background: "transparent", cursor: "pointer",
                color: "#9ca3af", padding: "2px 4px",
              }}
            >
              <X size={14} />
            </button>
          </div>
        ))}

        <button
          onClick={addRow}
          style={{
            display: "flex", alignItems: "center", gap: 4,
            border: "1px dashed #d1d5db", background: "transparent",
            borderRadius: 6, padding: "4px 10px", fontSize: 12,
            color: "#6b7280", cursor: "pointer", marginBottom: 20, width: "100%",
            justifyContent: "center",
          }}
        >
          <Plus size={13} /> Add attribute
        </button>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            onClick={onClose}
            style={{
              border: "1px solid #d1d5db", background: "#fff", borderRadius: 6,
              padding: "7px 16px", fontSize: 13, cursor: "pointer", color: "#374151",
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={saving || !entityName.trim()}
            style={{
              border: "none", background: saving ? "#818cf8" : "#6366f1", color: "#fff",
              borderRadius: 6, padding: "7px 16px", fontSize: 13, cursor: "pointer",
              opacity: !entityName.trim() ? 0.5 : 1,
            }}
          >
            {saving ? "Saving…" : "Confirm"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Relationship dialog ───────────────────────────────────────────────────────

type CardinalityKey = "many_to_one" | "one_to_many" | "many_to_many" | "one_to_one";

const CARD_OPTIONS: Array<{ value: CardinalityKey; label: string }> = [
  { value: "many_to_one",  label: "Many -> One"  },
  { value: "one_to_many",  label: "One -> Many"  },
  { value: "many_to_many", label: "Many -> Many" },
  { value: "one_to_one",   label: "One -> One"   },
];
const RELATIONSHIP_ADD_OPTIONS = CARD_OPTIONS.filter(({ value }) => value !== "many_to_many");

const CARD_MAP: Record<CardinalityKey, Cardinality> = {
  many_to_one:  { from_min: 0, from_max: "many", to_min: 1, to_max: 1 },
  one_to_many:  { from_min: 1, from_max: 1, to_min: 0, to_max: "many" },
  many_to_many: { from_min: 0, from_max: "many", to_min: 0, to_max: "many" },
  one_to_one:   { from_min: 1, from_max: 1, to_min: 1, to_max: 1 },
};

function cardinalityKey(cardinality: Cardinality | undefined): CardinalityKey | null {
  if (!cardinality) return null;
  return CARD_OPTIONS.find(({ value }) => {
    const card = CARD_MAP[value];
    return card.from_max === cardinality.from_max && card.to_max === cardinality.to_max;
  })?.value ?? null;
}

interface RelDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: (verb: string, cardinality: CardinalityKey) => void;
  saving: boolean;
}

function RelationshipDialog({ open, onClose, onConfirm, saving }: RelDialogProps) {
  const [verb, setVerb] = useState("");
  const [cardinality, setCardinality] = useState<CardinalityKey>("many_to_one");

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (open) { setVerb(""); setCardinality("many_to_one"); }
  }, [open]);
  /* eslint-enable react-hooks/set-state-in-effect */

  if (!open) return null;

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      background: "rgba(0,0,0,0.35)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }} onClick={onClose}>
      <div style={{
        background: "#fff", borderRadius: 10, width: 320,
        boxShadow: "0 8px 32px rgba(0,0,0,0.18)", padding: 20,
      }} onClick={(e) => e.stopPropagation()}>
        <h2 style={{ margin: "0 0 14px", fontSize: 15, fontWeight: 700, color: "#1e1b4b" }}>
          Add relationship
        </h2>

        <label style={{ display: "block", fontSize: 13, color: "#374151", marginBottom: 4 }}>
          Verb (optional)
        </label>
        <input
          autoFocus
          value={verb}
          onChange={(e) => setVerb(e.target.value)}
          placeholder="e.g. places, belongs to"
          style={{
            width: "100%", boxSizing: "border-box",
            border: "1.5px solid #d1d5db", borderRadius: 6, padding: "6px 10px",
            fontSize: 13, outline: "none", marginBottom: 12,
          }}
          onKeyDown={(e) => { if (e.key === "Enter") onConfirm(verb, cardinality); }}
        />

        <label style={{ display: "block", fontSize: 13, color: "#374151", marginBottom: 4 }}>
          Cardinality
        </label>
        <select
          value={cardinality}
          onChange={(e) => setCardinality(e.target.value as CardinalityKey)}
          style={{
            width: "100%", border: "1.5px solid #d1d5db", borderRadius: 6,
            padding: "6px 10px", fontSize: 13, marginBottom: 18,
          }}
        >
          {RELATIONSHIP_ADD_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button
            onClick={onClose}
            style={{
              border: "1px solid #d1d5db", background: "#fff", borderRadius: 6,
              padding: "6px 14px", fontSize: 13, cursor: "pointer", color: "#374151",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => onConfirm(verb, cardinality)}
            disabled={saving}
            style={{
              border: "none", background: saving ? "#818cf8" : "#6366f1",
              color: "#fff", borderRadius: 6, padding: "6px 14px",
              fontSize: 13, cursor: "pointer",
            }}
          >
            {saving ? "Saving…" : "Add"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── ERDCanvas component ───────────────────────────────────────────────────────

interface Props {
  pen: PenFile;
  projectId: string;
  onPenUpdate: (updated: PenFile) => void;
}

export function ERDCanvas({ pen, projectId, onPenUpdate }: Props) {
  const { diagramThemeId } = useAppTheme();
  // Stable refs so callbacks don't stale-close over pen/projectId
  const penRef = useRef(pen);
  const onPenUpdateRef = useRef(onPenUpdate);

  useEffect(() => {
    penRef.current = pen;
  }, [pen]);

  useEffect(() => {
    onPenUpdateRef.current = onPenUpdate;
  }, [onPenUpdate]);

  // Flow state
  const initialFlow = useMemo(
    () => penToFlow(pen, diagramThemeId),
    [pen, diagramThemeId],
  );
  const [nodes, setNodes, onNodesChange] = useNodesState(initialFlow.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialFlow.edges);

  // Sync nodes/edges when pen prop changes
  useEffect(() => {
    const { nodes: n, edges: e } = penToFlow(pen, diagramThemeId);
    setNodes(n);
    setEdges(e);
  }, [pen, setNodes, setEdges]);

  // Dialog state
  const [entityDialogOpen, setEntityDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Entity | null>(null);
  const [pendingConnection, setPendingConnection] = useState<Connection | null>(null);
  const [relDialogOpen, setRelDialogOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; edgeId: string } | null>(null);
  const [entityContextMenu, setEntityContextMenu] = useState<{ x: number; y: number; entityId: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [inlineEditingAttrId, setInlineEditingAttrId] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);
  const reactFlowRef = useRef<ReactFlowInstance | null>(null);
  const { patchLayout } = useLayoutPatch(projectId);
  const { theme } = useDiagramTheme();

  // ── Helpers ──────────────────────────────────────────────────────────────

  const patchPen = useCallback(async (updated: PenFile): Promise<PenFile> => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/schema/${projectId}/pen`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updated),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg);
      }
      return res.json();
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  const saveNodePosition = useCallback(async (node: Node) => {
    const cur = penRef.current;
    setSaving(true);
    try {
      const result = await patchLayout({
        scope: { diagram: "erd", level: "root" },
        baseRevision: cur.project.revision,
        nodes: [{
          id: node.id,
          x: node.position.x,
          y: node.position.y,
          width: node.width,
          height: node.height,
        }],
      });
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to save layout: ${err}`);
    } finally {
      setSaving(false);
    }
  }, [patchLayout]);

  const autoArrange = useCallback(async () => {
    const cur = penRef.current;
    setSaving(true);
    try {
      const measuredNodes = reactFlowRef.current?.getNodes() ?? nodes;
      const graph = buildErdLayoutGraph(cur, measuredNodes);
      const result = await optimizeDiagramLayout(graph, { mode: "auto", gridSize: 20 });
      const updated = await patchLayout({
        scope: { diagram: "erd", level: "root" },
        baseRevision: cur.project.revision,
        nodes: result.nodes.map(toLayoutNodePatch),
        edges: result.edges.map(toLayoutEdgePatch),
      });
      onPenUpdateRef.current(updated);
    } catch (err) {
      alert(`Failed to auto arrange ERD: ${err}`);
    } finally {
      setSaving(false);
    }
  }, [nodes, patchLayout]);

  const moveEdgeLabel = useCallback(async (edgeId: string, labelT: number, labelOffset: number) => {
    const cur = penRef.current;
    setSaving(true);
    try {
      const updated = await patchLayout({
        scope: { diagram: "erd", level: "root" },
        baseRevision: cur.project.revision,
        edges: [{
          id: edgeId,
          label_t: labelT,
          label_offset: labelOffset,
        }],
      });
      onPenUpdateRef.current(updated);
    } catch (err) {
      alert(`Failed to move relationship label: ${err}`);
    } finally {
      setSaving(false);
    }
  }, [patchLayout]);

  const callOps = useCallback(async (
    ops: Array<{ op: string; payload: Record<string, unknown> }>,
  ): Promise<PenFile> => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/projects/${projectId}/ops`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ops }),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg);
      }
      const data = await res.json();
      return data.pen as PenFile;
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  // ── Entity callbacks (stable refs) ───────────────────────────────────────

  const handleEditEntity = useCallback((entity: Entity) => {
    setEditTarget(entity);
    setEntityDialogOpen(true);
  }, []);

  const handleDeleteEntity = useCallback(async (entity: Entity) => {
    if (!window.confirm(`Delete entity "${entity.display_name || entity.name}"? This will also cascade to its relationships and DFD objects.`)) return;
    setSaving(true);
    try {
      const doDelete = async (force: boolean) => {
        const url = `${API}/schema/${projectId}/entity/${entity.id}${force ? "?force=true" : ""}`;
        return fetch(url, { method: "DELETE" });
      };
      let res = await doDelete(false);
      if (res.status === 409) {
        const detail = await res.json();
        const names = (detail?.detail?.would_remove ?? [])
          .map((o: { name: string }) => o.name).join(", ");
        if (window.confirm(
          `This will also remove user-modified DFD objects: ${names || "unknown"}.\nProceed?`
        )) {
          res = await doDelete(true);
        } else {
          return;
        }
      }
      if (!res.ok) throw new Error(await res.text());
      const result = await res.json();
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to delete entity: ${err}`);
    } finally {
      setSaving(false);
    }
  }, [projectId]);

  const entityActions = useMemo<EntityActions>(
    () => ({ onEdit: handleEditEntity, onDelete: handleDeleteEntity }),
    [handleEditEntity, handleDeleteEntity]
  );

  // ── Entity dialog confirm ─────────────────────────────────────────────────

  const handleEntityConfirm = useCallback(async (
    snakeName: string,
    displayName: string,
    attrRows: AttrRow[],
  ) => {
    const cur = penRef.current;

    const pkAttr: Attribute = {
      id: `attr_${snakeName}_id`,
      name: "id",
      display_name: "id",
      pg_type: "uuid",
      key_role: "primary",
      nullable: false,
      default: "gen_random_uuid()",
      source_columns: [],
      evidence: [],
      confidence: 1.0,
      review_status: "accepted",
    };
    const auditAttrs: Attribute[] = [
      {
        id: `attr_${snakeName}_created_at`,
        name: "created_at",
        display_name: "created_at",
        pg_type: "timestamptz",
        key_role: "audit",
        nullable: false,
        default: "now()",
        source_columns: [],
        evidence: [],
        confidence: 1.0,
        review_status: "accepted",
      },
      {
        id: `attr_${snakeName}_updated_at`,
        name: "updated_at",
        display_name: "updated_at",
        pg_type: "timestamptz",
        key_role: "audit",
        nullable: false,
        default: "now()",
        source_columns: [],
        evidence: [],
        confidence: 1.0,
        review_status: "accepted",
      },
    ];
    const userAttrs: Attribute[] = attrRows.map((r, i) => ({
      id: `attr_${snakeName}_${r.name.toLowerCase().replace(/\s+/g, "_")}_${i}`,
      name: r.name.toLowerCase().replace(/\s+/g, "_"),
      display_name: r.name,
      pg_type: r.pg_type,
      key_role: r.key_role as KeyRole,
      nullable: true,
      source_columns: [],
      evidence: [],
      confidence: 1.0,
      review_status: "accepted" as ReviewStatus,
    }));

    let newPen: PenFile;
    if (editTarget) {
      // Edit: preserve PK and audit attrs
      const origPk = editTarget.attributes.find((a) => a.key_role === "primary");
      const origAudit = editTarget.attributes.filter((a) => a.key_role === "audit");
      const updatedEntity: Entity = {
        ...editTarget,
        name: snakeName,
        display_name: displayName,
        attributes: [
          origPk ?? pkAttr,
          ...userAttrs,
          ...(origAudit.length ? origAudit : auditAttrs),
        ],
      };
      newPen = {
        ...cur,
        erd: {
          ...cur.erd,
          entities: cur.erd.entities.map((e) =>
            e.id === editTarget.id ? updatedEntity : e
          ),
        },
      };
    } else {
      // Add: generate ID and layout position
      const entityId = `ent_${snakeName}`;
      const newEntity: Entity = {
        id: entityId,
        kind: "strong_entity",
        name: snakeName,
        display_name: displayName,
        attributes: [pkAttr, ...userAttrs, ...auditAttrs],
        source_evidence: [],
        confidence: 1.0,
        review_status: "accepted",
      };
      const allAttrs = [pkAttr, ...userAttrs, ...auditAttrs];
      const h = 80 + allAttrs.length * 24;
      const lastNode = cur.layout.erd.nodes[cur.layout.erd.nodes.length - 1];
      const newX = lastNode ? lastNode.x + 360 : 40;
      const newY = lastNode ? lastNode.y : 40;
      newPen = {
        ...cur,
        erd: { ...cur.erd, entities: [...cur.erd.entities, newEntity] },
        layout: {
          ...cur.layout,
          erd: {
            ...cur.layout.erd,
            nodes: [
              ...cur.layout.erd.nodes,
              { id: entityId, x: newX, y: newY, width: 280, height: h },
            ],
          },
        },
      };
    }

    try {
      const result = await patchPen(newPen);
      onPenUpdateRef.current(result);
      setEntityDialogOpen(false);
      setEditTarget(null);
    } catch (err) {
      alert(`Failed to save entity: ${err}`);
    }
  }, [editTarget, patchPen]);

  // ── Relationship connection via drag ──────────────────────────────────────

  const onConnectStart = useCallback(() => {
    setIsConnecting(true);
  }, []);

  const onConnectEnd = useCallback(() => {
    setIsConnecting(false);
  }, []);

  const onConnect = useCallback((params: Connection) => {
    setPendingConnection(params);
    setRelDialogOpen(true);
  }, []);

  const handleRelConfirm = useCallback(async (verb: string, cardinality: CardinalityKey) => {
    if (!pendingConnection) return;
    const cur = penRef.current;
    const fromEntity = cur.erd.entities.find((e) => e.id === pendingConnection.source);
    const toEntity = cur.erd.entities.find((e) => e.id === pendingConnection.target);
    if (!fromEntity || !toEntity) {
      setRelDialogOpen(false);
      return;
    }
    const fromPk = fromEntity.attributes.find((a) => a.key_role === "primary");
    const toPk = toEntity.attributes.find((a) => a.key_role === "primary");
    const card = CARD_MAP[cardinality] ?? CARD_MAP.many_to_one;
    const relId = `rel_${Math.random().toString(36).slice(2, 10)}`;
    const newRel: Relationship = {
      id: relId,
      name: verb.trim() || "relates to",
      from: { entity_id: fromEntity.id, attribute_id: fromPk?.id ?? "" },
      to: { entity_id: toEntity.id, attribute_id: toPk?.id ?? "" },
      cardinality: card,
      postgres: {
        constraint_name: `fk_${fromEntity.name}_${toEntity.name}`,
        on_delete: "restrict",
        on_update: "no_action",
      },
      evidence: [],
      confidence: 1.0,
      review_status: "accepted",
    };
    const newPen: PenFile = {
      ...cur,
      erd: { ...cur.erd, relationships: [...cur.erd.relationships, newRel] },
      layout: {
        ...cur.layout,
        erd: {
          ...cur.layout.erd,
          edges: [
            ...cur.layout.erd.edges,
            {
              id: relId,
              route: "orthogonal",
              source_handle: pendingConnection.sourceHandle ?? undefined,
              target_handle: pendingConnection.targetHandle ?? undefined,
            },
          ],
        },
      },
    };
    try {
      const result = await patchPen(newPen);
      onPenUpdateRef.current(result);
      setRelDialogOpen(false);
      setPendingConnection(null);
    } catch (err) {
      alert(`Failed to add relationship: ${err}`);
      setRelDialogOpen(false);
      setPendingConnection(null);
    }
  }, [pendingConnection, patchPen]);

  // ── Edge right-click → delete ─────────────────────────────────────────────

  const onReconnectStart = useCallback(() => {
    setIsConnecting(true);
  }, []);

  const onReconnectEnd = useCallback(() => {
    setIsConnecting(false);
  }, []);

  const onReconnect = useCallback(async (oldEdge: Edge, connection: Connection) => {
    const cur = penRef.current;
    const rel = cur.erd.relationships.find((r) => r.id === oldEdge.id);
    const sourceEntity = cur.erd.entities.find((e) => e.id === connection.source);
    const targetEntity = cur.erd.entities.find((e) => e.id === connection.target);
    if (!rel || !sourceEntity || !targetEntity) {
      setIsConnecting(false);
      return;
    }

    const sourceChanged = connection.source !== rel.from.entity_id;
    const targetChanged = connection.target !== rel.to.entity_id;
    const sourcePk = sourceEntity.attributes.find((a) => a.key_role === "primary");
    const targetPk = targetEntity.attributes.find((a) => a.key_role === "primary");

    const updatedRel: Relationship = {
      ...rel,
      from: {
        entity_id: connection.source ?? rel.from.entity_id,
        attribute_id: sourceChanged ? (sourcePk?.id ?? rel.from.attribute_id) : rel.from.attribute_id,
      },
      to: {
        entity_id: connection.target ?? rel.to.entity_id,
        attribute_id: targetChanged ? (targetPk?.id ?? rel.to.attribute_id) : rel.to.attribute_id,
      },
    };
    const nextEdges = cur.layout.erd.edges.filter((edge) => edge.id !== oldEdge.id);
    nextEdges.push({
      id: oldEdge.id,
      route: "orthogonal",
      source_handle: connection.sourceHandle ?? oldEdge.sourceHandle ?? undefined,
      target_handle: connection.targetHandle ?? oldEdge.targetHandle ?? undefined,
    });

    const newPen: PenFile = {
      ...cur,
      erd: {
        ...cur.erd,
        relationships: cur.erd.relationships.map((item) =>
          item.id === oldEdge.id ? updatedRel : item
        ),
      },
      layout: {
        ...cur.layout,
        erd: {
          ...cur.layout.erd,
          edges: nextEdges,
        },
      },
    };

    try {
      const result = await patchPen(newPen);
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to move relationship endpoint: ${err}`);
    } finally {
      setIsConnecting(false);
    }
  }, [patchPen]);

  const openEdgeMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault();
    event.stopPropagation();
    setIsConnecting(true);
    setContextMenu({ x: event.clientX, y: event.clientY, edgeId: edge.id });
  }, []);

  const openEntityMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    event.stopPropagation();
    setIsConnecting(true);
    const entity = (node.data as TableNodeData)?.entity;
    if (entity) {
      setEntityContextMenu({ x: event.clientX, y: event.clientY, entityId: entity.id });
    }
  }, []);

  const onNodeClick = useCallback(() => {
    setIsConnecting(true);
    setContextMenu(null);
    setEntityContextMenu(null);
  }, []);

  const onNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    openEntityMenu(event, node);
  }, [openEntityMenu]);

  const onEdgeContextMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    openEdgeMenu(event, edge);
  }, [openEdgeMenu]);

  const onEdgeClick = useCallback((event: React.MouseEvent, edge: Edge) => {
    openEdgeMenu(event, edge);
  }, [openEdgeMenu]);

  const onPaneClick = useCallback(() => {
    setIsConnecting(false);
    setContextMenu(null);
    setEntityContextMenu(null);
  }, []);

  const handleDeleteEdge = useCallback(async (edgeId: string) => {
    setIsConnecting(false);
    setContextMenu(null);
    try {
      const result = await callOps([
        { op: "relationship.delete", payload: { id: edgeId } },
      ]);
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to delete relationship: ${err}`);
    }
  }, [callOps]);

  const handleChangeCardinality = useCallback(async (
    edgeId: string,
    cardKey: CardinalityKey,
  ) => {
    setIsConnecting(false);
    setContextMenu(null);
    try {
      const result = await callOps([
        {
          op: "relationship.update",
          payload: { id: edgeId, cardinality: CARD_MAP[cardKey] },
        },
      ]);
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to update cardinality: ${err}`);
    }
  }, [callOps]);

  const handleConvertM2M = useCallback(async (edgeId: string) => {
    setIsConnecting(false);
    setContextMenu(null);
    try {
      const result = await callOps([
        { op: "relationship.m2m_convert", payload: { id: edgeId } },
      ]);
      onPenUpdateRef.current(result);
    } catch (err) {
      alert(`Failed to convert relationship: ${err}`);
    }
  }, [callOps]);

  // ── Dismiss context menus on click elsewhere ───────────────────────────────

  useEffect(() => {
    if (!contextMenu && !entityContextMenu) return;
    const dismiss = () => {
      setIsConnecting(false);
      setContextMenu(null);
      setEntityContextMenu(null);
    };
    document.addEventListener("click", dismiss);
    return () => document.removeEventListener("click", dismiss);
  }, [contextMenu, entityContextMenu]);

  // ── Render ────────────────────────────────────────────────────────────────

  const isEmpty = pen.erd.entities.length === 0;
  const contextRelationship = contextMenu
    ? pen.erd.relationships.find((rel) => rel.id === contextMenu.edgeId)
    : null;
  const activeCardinality = cardinalityKey(contextRelationship?.cardinality);

  return (
    <DiagramThemeProvider themeId={diagramThemeId}>
    <EntityActionsCtx.Provider value={entityActions}>
      <InlineEditCtx.Provider value={{ editingId: inlineEditingAttrId, setEditingId: setInlineEditingAttrId, isConnecting }}>
        <EdgeLabelDragProvider onLabelMove={moveEdgeLabel}>
        <div style={{ width: "100%", height: "100%", position: "relative", background: undefined }}>
        {isEmpty ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
            <p className="text-gray-400 text-sm">No entities yet</p>
            <button
              onClick={() => { setEditTarget(null); setEntityDialogOpen(true); }}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add your first entity
            </button>
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onInit={(instance) => {
              reactFlowRef.current = instance;
            }}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeDragStop={(_, node) => saveNodePosition(node)}
            onConnectStart={onConnectStart}
            onConnectEnd={onConnectEnd}
            onConnect={onConnect}
            onReconnectStart={onReconnectStart}
            onReconnectEnd={onReconnectEnd}
            onReconnect={onReconnect}
            onEdgeClick={onEdgeClick}
            onEdgeContextMenu={onEdgeContextMenu}
            onNodeClick={onNodeClick}
            onNodeContextMenu={onNodeContextMenu}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            edgesReconnectable
            reconnectRadius={18}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            minZoom={0.05}
            maxZoom={2}
          >
            <Panel position="top-left">
              <button
                onClick={autoArrange}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white border border-indigo-200 text-xs font-semibold text-indigo-700 shadow-sm hover:bg-indigo-50"
              >
                <Wand2 className="w-3.5 h-3.5" />
                Auto Arrange
              </button>
            </Panel>
            <Background color={theme.canvas.grid} gap={20} />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const entity = (n.data as TableNodeData)?.entity;
                if (entity?.kind === "lookup_table") return theme.erd.entity.border;
                return theme.erd.entity.border;
              }}
              maskColor="rgba(0,0,0,0.06)"
            />

            {/* Toolbar: Add Entity button */}
            <div style={{
              position: "absolute", bottom: 48, left: 12, zIndex: 4,
            }}>
              <button
                onClick={() => { setEditTarget(null); setEntityDialogOpen(true); }}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  background: theme.erd.entity.accent, color: "#fff", border: "none",
                  borderRadius: 8, padding: "7px 14px", fontSize: 13,
                  fontWeight: 600, cursor: "pointer", boxShadow: "0 2px 8px rgba(99,102,241,0.35)",
                }}
              >
                <Plus size={15} /> Add Entity
              </button>
            </div>
          </ReactFlow>
        )}

        {/* Edge right-click context menu */}
        {contextMenu && (
          <div
            style={{
              position: "fixed", top: contextMenu.y, left: contextMenu.x,
              background: "#fff", border: "1px solid #e5e7eb",
              borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
              zIndex: 9999, minWidth: 190,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {CARD_OPTIONS
              .filter(({ value }) => value !== "many_to_many" && value !== activeCardinality)
              .map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => handleChangeCardinality(contextMenu.edgeId, value)}
                  style={{
                    display: "block", width: "100%", textAlign: "left",
                    padding: "8px 14px", fontSize: 13, color: "#374151",
                    background: "transparent", border: "none", cursor: "pointer",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "#f9fafb")}
                  onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                >
                  Set {label}
                </button>
              ))}
            <div style={{ height: 1, background: "#e5e7eb", margin: "4px 0" }} />
            <button
              onClick={() => handleConvertM2M(contextMenu.edgeId)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "8px 14px", fontSize: 13, color: "#4f46e5",
                background: "transparent", border: "none", cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#eef2ff")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              Convert to many-to-many
            </button>
            <div style={{ height: 1, background: "#e5e7eb", margin: "4px 0" }} />
            <button
              onClick={() => handleDeleteEdge(contextMenu.edgeId)}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "8px 14px", fontSize: 13, color: "#dc2626",
                background: "transparent", border: "none", cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#fef2f2")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              Delete relationship
            </button>
          </div>
        )}

        {/* Entity right-click context menu */}
        {entityContextMenu && (
          <div
            style={{
              position: "fixed", top: entityContextMenu.y, left: entityContextMenu.x,
              background: "#fff", border: "1px solid #e5e7eb",
              borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
              zIndex: 9999, minWidth: 190,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => {
                const entity = pen.erd.entities.find((e) => e.id === entityContextMenu.entityId);
                if (entity) {
                  setEntityContextMenu(null);
                  setEditTarget(entity);
                  setEntityDialogOpen(true);
                }
              }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "8px 14px", fontSize: 13, color: "#374151",
                background: "transparent", border: "none", cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#f9fafb")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              Edit entity
            </button>
            <div style={{ height: 1, background: "#e5e7eb", margin: "4px 0" }} />
            <button
              onClick={async () => {
                setEntityContextMenu(null);
                const entity = pen.erd.entities.find((e) => e.id === entityContextMenu.entityId);
                if (entity) {
                  if (!window.confirm(`Delete entity "${entity.display_name || entity.name}"? This will also cascade to its relationships and DFD objects.`)) return;
                  setSaving(true);
                  try {
                    const doDelete = async (force: boolean) => {
                      const url = `${API}/schema/${projectId}/entity/${entity.id}${force ? "?force=true" : ""}`;
                      return fetch(url, { method: "DELETE" });
                    };
                    let res = await doDelete(false);
                    if (res.status === 409) {
                      const detail = await res.json();
                      const names = (detail?.detail?.would_remove ?? [])
                        .map((o: { name: string }) => o.name).join(", ");
                      if (window.confirm(`This will also remove user-modified DFD objects: ${names || "unknown"}.\nProceed?`)) {
                        res = await doDelete(true);
                      } else {
                        return;
                      }
                    }
                    if (!res.ok) throw new Error(await res.text());
                    const result = await res.json();
                    onPenUpdateRef.current(result);
                  } catch (err) {
                    alert(`Failed to delete entity: ${err}`);
                  } finally {
                    setSaving(false);
                  }
                }
              }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "8px 14px", fontSize: 13, color: "#dc2626",
                background: "transparent", border: "none", cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "#fef2f2")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              Delete entity
            </button>
          </div>
        )}

        {/* Saving indicator */}
        {saving && (
          <div style={{
            position: "absolute", top: 12, right: 12,
            background: "#6366f1", color: "#fff",
            borderRadius: 6, padding: "4px 12px", fontSize: 12,
            fontWeight: 600, zIndex: 10,
          }}>
            Saving…
          </div>
        )}
        </div>
        </EdgeLabelDragProvider>

      <EntityDialog
        open={entityDialogOpen}
        editTarget={editTarget}
        onClose={() => { setEntityDialogOpen(false); setEditTarget(null); }}
        onConfirm={handleEntityConfirm}
        saving={saving}
      />

      <RelationshipDialog
        open={relDialogOpen}
        onClose={() => { setRelDialogOpen(false); setPendingConnection(null); setIsConnecting(false); }}
        onConfirm={handleRelConfirm}
        saving={saving}
      />
      </InlineEditCtx.Provider>
    </EntityActionsCtx.Provider>
    </DiagramThemeProvider>
  );
}
