import { Pencil, Trash2 } from "lucide-react";

interface EdgeContextMenuProps {
  x: number;
  y: number;
  label?: string;
  onRename: () => void;
  onDelete: () => void;
}

export function EdgeContextMenu({
  x,
  y,
  label,
  onRename,
  onDelete,
}: EdgeContextMenuProps) {
  return (
    <div
      style={{
        position: "fixed",
        top: y,
        left: x,
        zIndex: 9999,
        minWidth: 180,
        background: "#fff",
        border: "1px solid #e5e7eb",
        borderRadius: 6,
        boxShadow: "0 8px 24px rgba(15,23,42,0.14)",
        overflow: "hidden",
      }}
      onClick={(event) => event.stopPropagation()}
    >
      {label && (
        <div
          style={{
            padding: "8px 12px",
            borderBottom: "1px solid #f3f4f6",
            color: "#6b7280",
            fontSize: 12,
            maxWidth: 240,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </div>
      )}
      <button
        type="button"
        onClick={onRename}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "8px 12px",
          border: "none",
          background: "transparent",
          color: "#374151",
          fontSize: 13,
          cursor: "pointer",
          textAlign: "left",
        }}
        onMouseEnter={(event) => { event.currentTarget.style.background = "#f9fafb"; }}
        onMouseLeave={(event) => { event.currentTarget.style.background = "transparent"; }}
      >
        <Pencil size={14} />
        Rename
      </button>
      <button
        type="button"
        onClick={onDelete}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          width: "100%",
          padding: "8px 12px",
          border: "none",
          background: "transparent",
          color: "#dc2626",
          fontSize: 13,
          cursor: "pointer",
          textAlign: "left",
        }}
        onMouseEnter={(event) => { event.currentTarget.style.background = "#fef2f2"; }}
        onMouseLeave={(event) => { event.currentTarget.style.background = "transparent"; }}
      >
        <Trash2 size={14} />
        Delete
      </button>
    </div>
  );
}
