import type { PenFile, Entity, Attribute } from "../types/pen";
import type { DiagramTheme } from "../styles/diagramThemes";

interface Props {
  pen: PenFile;
  theme: DiagramTheme;
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 85
    ? { bg: "#dcfce7", text: "#166534", border: "#bbf7d0" }
    : pct >= 65
    ? { bg: "#fef9c3", text: "#854d0e", border: "#fde047" }
    : { bg: "#ffedd5", text: "#9a3412", border: "#fed7aa" };
  return (
    <span style={{
      fontSize: 10, fontWeight: 700,
      background: color.bg, color: color.text,
      border: `1px solid ${color.border}`,
      borderRadius: 999, padding: "1px 7px",
    }}>
      {pct}%
    </span>
  );
}

function AttributeRow({ attr, theme }: { attr: Attribute; theme: DiagramTheme }) {
  const prefix =
    attr.key_role === "primary" ? "PK" :
    attr.key_role === "foreign" ? "FK" :
    attr.key_role === "unique" ? "UQ" :
    attr.key_role === "business_key" ? "BK" : "";

  const isChalk = theme.id === "chalkboard";
  const rowBg = isChalk ? theme.canvas.bg : "transparent";
  const monoColor = isChalk ? "#a8d5a8" : "#6b7280";
  const nameColor = isChalk ? theme.erd.entity.text : "#1f2937";
  const nullableColor = isChalk ? "rgba(239,232,213,0.45)" : "#9ca3af";
  const defaultBg = isChalk ? "rgba(239,232,213,0.10)" : "#f3f4f6";
  const defaultColor = isChalk ? theme.erd.entity.text : "#6b7280";

  return (
    <div
      className="flex items-center gap-2 py-2 px-3 text-sm border-b"
      style={{
        borderColor: `${theme.erd.entity.border}18`,
        background: rowBg,
      }}
    >
      {prefix ? (
        <span style={{
          width: 22, flexShrink: 0,
          fontSize: 9, fontWeight: 800,
          color: isChalk ? "#7bc47b" : theme.erd.entity.accent,
          letterSpacing: "0.04em",
        }}>{prefix}</span>
      ) : <span style={{ width: 22, flexShrink: 0 }} />}
      <span style={{
        flex: 1,
        fontFamily: "ui-monospace, 'Cascadia Code', 'Fira Code', monospace",
        fontSize: 12,
        color: nameColor,
      }}>{attr.name}</span>
      <span style={{
        fontFamily: "ui-monospace, 'Cascadia Code', 'Fira Code', monospace",
        fontSize: 11,
        color: monoColor,
        letterSpacing: "-0.01em",
      }}>{attr.pg_type}</span>
      {attr.nullable && (
        <span style={{ fontSize: 10, color: nullableColor, fontStyle: "italic" }}>null</span>
      )}
      {attr.default && (
        <span style={{
          fontSize: 10, fontFamily: "ui-monospace, monospace",
          background: defaultBg, color: defaultColor,
          borderRadius: 4, padding: "1px 5px",
          border: `1px solid ${theme.erd.entity.border}22`,
        }}>
          {attr.default}
        </span>
      )}
    </div>
  );
}

function EntityCard({ entity, theme }: { entity: Entity; theme: DiagramTheme }) {
  const accepted = entity.attributes.filter((a) => a.review_status !== "rejected");
  const isChalk = theme.id === "chalkboard";

  const headerBg = isChalk ? "rgba(239,232,213,0.06)" : "#f8fafc";
  const cardBorder = isChalk ? "rgba(239,232,213,0.20)" : "#e2e8f0";
  const nameColor = isChalk ? theme.erd.entity.text : "#0f172a";
  const labelBg = isChalk ? "rgba(239,232,213,0.12)" : "#f3e8ff";
  const labelColor = isChalk ? "#a8d5a8" : "#7c3aed";
  const reviewBg = isChalk ? "rgba(239,232,213,0.15)" : "#fef9c3";
  const reviewColor = isChalk ? "#e8f5e8" : "#a16207";
  const reasonBg = isChalk ? "rgba(90,158,90,0.12)" : "#eff6ff";
  const reasonColor = isChalk ? "#a8d5a8" : "#1d4ed8";
  const reasonBorder = isChalk ? "rgba(90,158,90,0.25)" : "#bfdbfe";
  const evidenceBg = isChalk ? "rgba(239,232,213,0.04)" : "#f8fafc";

  return (
    <div style={{
      marginBottom: 16,
      border: `1px solid ${cardBorder}`,
      borderRadius: 8,
      overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 12px",
        background: headerBg,
        borderBottom: `1px solid ${cardBorder}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 13, fontWeight: 700,
            color: nameColor,
            fontFamily: "ui-monospace, monospace",
          }}>{entity.name}</span>
          {entity.kind === "lookup_table" && (
            <span style={{
              fontSize: 10, fontWeight: 600,
              background: labelBg, color: labelColor,
              borderRadius: 4, padding: "1px 6px",
              letterSpacing: "0.03em",
            }}>lookup</span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <ConfidenceBadge value={entity.confidence} />
          {entity.review_status === "needs_review" && (
            <span style={{
              fontSize: 10, fontWeight: 600,
              background: reviewBg, color: reviewColor,
              borderRadius: 4, padding: "1px 6px",
            }}>review</span>
          )}
        </div>
      </div>

      {/* Proposal reason */}
      {entity.proposal_reason && (
        <div style={{
          padding: "7px 12px",
          background: reasonBg,
          borderBottom: `1px solid ${reasonBorder}`,
          fontSize: 11, color: reasonColor, lineHeight: 1.5,
        }}>
          {entity.proposal_reason}
        </div>
      )}

      {/* Attributes */}
      <div>
        {accepted.map((attr) => (
          <AttributeRow key={attr.id} attr={attr} theme={theme} />
        ))}
      </div>

      {/* Source evidence */}
      {entity.source_evidence.length > 0 && (
        <div style={{
          padding: "7px 12px",
          background: evidenceBg,
          borderTop: `1px solid ${cardBorder}33`,
          display: "flex", flexWrap: "wrap", gap: 5,
        }}>
          {entity.source_evidence.map((ev, i) => (
            <span key={i} style={{
              fontSize: 10,
              fontFamily: "ui-monospace, monospace",
              background: isChalk ? "rgba(239,232,213,0.08)" : "#ffffff",
              color: isChalk ? "rgba(239,232,213,0.55)" : "#64748b",
              border: `1px solid ${cardBorder}`,
              borderRadius: 4, padding: "2px 7px",
            }}>
              {ev.source_id}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function RelationshipRow({ rel, pen, theme }: { rel: Props["pen"]["erd"]["relationships"][number]; pen: PenFile; theme: DiagramTheme }) {
  const fromEnt = pen.erd.entities.find((e) => e.id === rel.from.entity_id);
  const toEnt = pen.erd.entities.find((e) => e.id === rel.to.entity_id);
  const fromAttr = pen.erd.entities.flatMap((e) => e.attributes).find((a) => a.id === rel.from.attribute_id);
  const toAttr = pen.erd.entities.flatMap((e) => e.attributes).find((a) => a.id === rel.to.attribute_id);
  if (!fromEnt || !toEnt) return null;

  const isChalk = theme.id === "chalkboard";
  const bg = isChalk ? "rgba(239,232,213,0.06)" : "#f8fafc";
  const border = isChalk ? "rgba(239,232,213,0.18)" : "#e2e8f0";
  const textColor = isChalk ? theme.erd.entity.text : "#475569";
  const arrowColor = isChalk ? "#7bc47b" : theme.erd.entity.accent;
  const monoColor = isChalk ? "rgba(239,232,213,0.55)" : "#94a3b8";

  return (
    <div style={{
      padding: "8px 12px",
      background: bg,
      border: `1px solid ${border}`,
      borderRadius: 6,
      marginBottom: 6,
      display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap",
    }}>
      <span style={{
        fontFamily: "ui-monospace, monospace", fontSize: 12,
        fontWeight: 600, color: textColor,
      }}>{fromEnt.name}</span>
      <span style={{ color: arrowColor, fontSize: 13 }}>·</span>
      <span style={{
        fontFamily: "ui-monospace, monospace", fontSize: 11,
        color: monoColor,
      }}>{fromAttr?.name ?? "?"}</span>
      <span style={{ color: arrowColor, fontSize: 16, fontWeight: 300 }}>→</span>
      <span style={{
        fontFamily: "ui-monospace, monospace", fontSize: 12,
        fontWeight: 600, color: textColor,
      }}>{toEnt.name}</span>
      <span style={{ color: arrowColor, fontSize: 13 }}>·</span>
      <span style={{
        fontFamily: "ui-monospace, monospace", fontSize: 11,
        color: monoColor,
      }}>{toAttr?.name ?? "id"}</span>
      {rel.postgres && (
        <span style={{
          marginLeft: "auto",
          fontSize: 10, fontFamily: "ui-monospace, monospace",
          color: monoColor,
          background: isChalk ? "rgba(239,232,213,0.08)" : "#f1f5f9",
          border: `1px solid ${border}`,
          borderRadius: 4, padding: "1px 6px",
        }}>
          ON DELETE {rel.postgres.on_delete.toUpperCase()}
        </span>
      )}
    </div>
  );
}

export function SchemaInspector({ pen, theme }: Props) {
  const accepted = pen.erd.entities.filter((e) => e.review_status !== "rejected");
  const isChalk = theme.id === "chalkboard";

  const headingColor = isChalk ? theme.erd.entity.text : "#0f172a";
  const subColor = isChalk ? "rgba(239,232,213,0.50)" : "#64748b";
  const sectionColor = isChalk ? "rgba(239,232,213,0.55)" : "#475569";
  const borderColor = isChalk ? "rgba(239,232,213,0.18)" : "#e2e8f0";
  const emptyColor = isChalk ? "rgba(239,232,213,0.35)" : "#9ca3af";

  if (accepted.length === 0) {
    return (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        height: "100%", fontSize: 13, color: emptyColor,
      }}>
        No entities yet.
      </div>
    );
  }

  return (
    <div style={{ height: "100%", overflowY: "auto", padding: 16 }}>
      {/* Header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 16,
        paddingBottom: 12,
        borderBottom: `1px solid ${borderColor}`,
      }}>
        <h2 style={{
          fontSize: 14, fontWeight: 700,
          color: headingColor,
          letterSpacing: "-0.01em",
        }}>Schema Inspector</h2>
        <span style={{ fontSize: 12, color: subColor }}>
          {accepted.length} {accepted.length === 1 ? "table" : "tables"}
        </span>
      </div>

      {/* Entities */}
      {accepted.map((entity) => (
        <EntityCard key={entity.id} entity={entity} theme={theme} />
      ))}

      {/* Relationships */}
      {pen.erd.relationships.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h3 style={{
            fontSize: 11, fontWeight: 700, textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: sectionColor,
            marginBottom: 10, paddingLeft: 2,
          }}>
            Relationships ({pen.erd.relationships.filter((r) => r.review_status !== "rejected").length})
          </h3>
          {pen.erd.relationships
            .filter((r) => r.review_status !== "rejected")
            .map((rel) => (
              <RelationshipRow key={rel.id} rel={rel} pen={pen} theme={theme} />
            ))}
        </div>
      )}
    </div>
  );
}
