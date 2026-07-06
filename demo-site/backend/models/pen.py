"""
PenFile — the canonical .pen project file model.

Structure:
  sources      — where the data came from (spreadsheet files, text statements)
  erd          — semantic ERD objects: entities, attributes, relationships
  dfd          — semantic DFD objects: external_entities, processes, data_stores, data_flows
  layout       — x/y/size positioning for ERD and DFD canvas nodes
  styles       — visual theme (never read by SQL/DBML/Mermaid exporters)
  postgres     — PostgreSQL-specific settings (dialect, extensions, PK strategy)
  review       — pending proposals and warnings

Rule: SQL exporters read erd + postgres ONLY. Layout and styles are ignored.
"""
from __future__ import annotations

import uuid
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────
# Sources
# ─────────────────────────────────────────────

class SourceRef(BaseModel):
    id: str
    type: Literal["xlsx", "csv", "text"]
    name: str                    # filename or short label
    raw_path: str | None = None  # original upload path (server-side temp)


# ─────────────────────────────────────────────
# ERD — Semantic objects
# ─────────────────────────────────────────────

class AttributeEvidence(BaseModel):
    source_id: str
    source_columns: list[str] = Field(default_factory=list)


class Attribute(BaseModel):
    id: str = Field(default_factory=lambda: f"attr_{uuid.uuid4().hex[:8]}")
    name: str
    display_name: str | None = None
    pg_type: str  # uuid | text | integer | bigint | numeric | boolean | date | timestamptz | jsonb
    key_role: Literal["primary", "foreign", "unique", "audit", "business_key", "none"] = "none"
    nullable: bool = True
    default: str | None = None
    check_constraint: str | None = None  # raw SQL expression e.g. "quantity > 0"
    enum_values: list[str] | None = None  # fixed value list (rendered as CREATE TYPE ... AS ENUM)
    # evidence / metadata
    source_columns: list[str] = Field(default_factory=list)
    evidence: list[AttributeEvidence] = Field(default_factory=list)
    confidence: float = 1.0
    review_status: Literal["accepted", "needs_review", "rejected"] = "accepted"


class IndexDef(BaseModel):
    id: str = Field(default_factory=lambda: f"idx_{uuid.uuid4().hex[:8]}")
    name: str
    attribute_ids: list[str] = Field(default_factory=list)  # Attribute.id refs — survive renames
    unique: bool = False


class Entity(BaseModel):
    id: str = Field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:8]}")
    kind: Literal["strong_entity", "weak_entity", "lookup_table"] = "strong_entity"
    name: str          # snake_case table name
    display_name: str  # human-readable label
    description: str | None = None  # exported as COMMENT ON TABLE
    color: str | None = None        # canvas header tint (never read by SQL exporters)
    attributes: list[Attribute] = Field(default_factory=list)
    indexes: list[IndexDef] = Field(default_factory=list)
    # evidence / metadata
    source_evidence: list[AttributeEvidence] = Field(default_factory=list)
    proposal_reason: str | None = None
    confidence: float = 1.0
    review_status: Literal["accepted", "needs_review", "rejected"] = "needs_review"


class Cardinality(BaseModel):
    from_min: int = 0        # 0 = optional, 1 = mandatory
    from_max: int | Literal["many"] = "many"
    to_min: int = 1
    to_max: int | Literal["many"] = 1


class RelationshipPostgres(BaseModel):
    constraint_name: str
    on_delete: Literal["restrict", "cascade", "set_null", "set_default", "no_action"] = "restrict"
    on_update: Literal["restrict", "cascade", "set_null", "set_default", "no_action"] = "no_action"


class RelationshipEndpoint(BaseModel):
    entity_id: str
    attribute_id: str  # the FK attribute on the "from" side or PK on the "to" side


class Relationship(BaseModel):
    id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    name: str | None = None   # optional verb label (e.g. "places")
    from_: RelationshipEndpoint = Field(alias="from")
    to: RelationshipEndpoint
    cardinality: Cardinality = Field(default_factory=Cardinality)
    postgres: RelationshipPostgres | None = None
    dfd_process_id: str | None = None  # DFD Process.id if auto-generated from this relationship
    # evidence / metadata
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    review_status: Literal["accepted", "needs_review", "rejected"] = "needs_review"

    model_config = {"populate_by_name": True}


class ErdModel(BaseModel):
    notation: Literal["crows_foot"] = "crows_foot"
    model_level: Literal["physical"] = "physical"
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


# ─────────────────────────────────────────────
# DFD — Semantic objects
# ─────────────────────────────────────────────

class SystemBoundary(BaseModel):
    id: str = Field(default_factory=lambda: f"boundary_{uuid.uuid4().hex[:8]}")
    name: str = "System"


class ExternalEntity(BaseModel):
    id: str = Field(default_factory=lambda: f"ext_{uuid.uuid4().hex[:8]}")
    name: str
    description: str | None = None
    source: Literal["manual", "auto"] = "manual"
    source_evidence: list[str] = Field(default_factory=list)
    source_facts: list[str] = Field(default_factory=list)


class Process(BaseModel):
    id: str = Field(default_factory=lambda: f"proc_{uuid.uuid4().hex[:8]}")
    number: str | None = None   # e.g. "1.0", "2.1"
    name: str
    description: str | None = None
    user_modified: bool = False              # True if user manually edited name/description
    mapped_relationship_id: str | None = None  # ERD Relationship.id that spawned this process
    source_evidence: list[str] = Field(default_factory=list)
    source_facts: list[str] = Field(default_factory=list)
    # Level 1: sub-processes (if this is a Level 0 process being decomposed)
    level_1_diagram: DfdModel | None = None


class DataStore(BaseModel):
    id: str = Field(default_factory=lambda: f"store_{uuid.uuid4().hex[:8]}")
    name: str
    description: str | None = None
    mapped_erd_entity: str | None = None  # ERD Entity.id (1:1 enforced by type)
    user_modified: bool = False           # True if user manually edited name/description
    source_evidence: list[str] = Field(default_factory=list)
    source_facts: list[str] = Field(default_factory=list)


class DataFlow(BaseModel):
    id: str = Field(default_factory=lambda: f"flow_{uuid.uuid4().hex[:8]}")
    from_: str = Field(alias="from")  # ID of ExternalEntity | Process | DataStore
    to: str                            # ID of ExternalEntity | Process | DataStore
    data_name: str | None = None
    mapped_relationship_id: str | None = None  # ERD Relationship.id if auto-generated
    user_modified: bool = False  # True if user manually edited name/endpoints
    # optional cross-references to ERD objects
    mapped_erd_entities: list[str] = Field(default_factory=list)   # entity IDs
    mapped_erd_attributes: list[str] = Field(default_factory=list) # attribute IDs
    source_evidence: list[str] = Field(default_factory=list)
    source_facts: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class DfdModel(BaseModel):
    level: int = 0  # 0 = context diagram, 1 = detailed
    notation: Literal["yourdon_coad"] = "yourdon_coad"
    system_boundary: SystemBoundary = Field(default_factory=SystemBoundary)
    external_entities: list[ExternalEntity] = Field(default_factory=list)
    processes: list[Process] = Field(default_factory=list)
    data_stores: list[DataStore] = Field(default_factory=list)
    data_flows: list[DataFlow] = Field(default_factory=list)


# Allow Process to self-reference DfdModel
Process.model_rebuild()


# ─────────────────────────────────────────────
# Layout
# ─────────────────────────────────────────────

class LayoutNode(BaseModel):
    id: str
    x: float = 0.0
    y: float = 0.0
    width: float = 280.0
    height: float = 180.0


class LayoutPoint(BaseModel):
    x: float
    y: float


class LayoutEdge(BaseModel):
    id: str
    route: Literal["orthogonal", "straight", "bezier"] = "orthogonal"
    source_handle: str | None = None
    target_handle: str | None = None
    points: list[LayoutPoint] = Field(default_factory=list)
    label_t: float | None = None
    label_offset: float | None = None


class DiagramLayout(BaseModel):
    nodes: list[LayoutNode] = Field(default_factory=list)
    edges: list[LayoutEdge] = Field(default_factory=list)


class Layout(BaseModel):
    erd: DiagramLayout = Field(default_factory=DiagramLayout)
    dfd: DiagramLayout = Field(default_factory=DiagramLayout)
    dfd_level_1: dict[str, DiagramLayout] = Field(default_factory=dict)
    # keyed by Process.id when that process is decomposed into Level 1


# ─────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────

class ErdEntityStyle(BaseModel):
    shape: str = "rectangle"
    header_fill: str = "#f5f5f5"
    border_radius: int = 4
    border_color: str = "#d1d5db"
    font_size: int = 13


class ErdRelationshipStyle(BaseModel):
    notation: str = "crows_foot"
    line_style: str = "solid"
    line_color: str = "#6b7280"


class ErdStyles(BaseModel):
    entity: ErdEntityStyle = Field(default_factory=ErdEntityStyle)
    primary_key_attribute: dict[str, Any] = Field(default_factory=lambda: {"prefix": "PK", "font_weight": "bold"})
    foreign_key_attribute: dict[str, Any] = Field(default_factory=lambda: {"prefix": "FK"})
    unique_attribute: dict[str, Any] = Field(default_factory=lambda: {"prefix": "UQ"})
    audit_attribute: dict[str, Any] = Field(default_factory=lambda: {"prefix": ""})
    relationship: ErdRelationshipStyle = Field(default_factory=ErdRelationshipStyle)


class DfdStyles(BaseModel):
    external_entity: dict[str, Any] = Field(default_factory=lambda: {"shape": "rectangle"})
    process: dict[str, Any] = Field(default_factory=lambda: {"shape": "rounded_rectangle"})
    data_store: dict[str, Any] = Field(default_factory=lambda: {"shape": "open_ended_rectangle"})
    data_flow: dict[str, Any] = Field(default_factory=lambda: {"shape": "arrow", "label_position": "middle"})


class Styles(BaseModel):
    theme: str = "clean_default"
    erd: ErdStyles = Field(default_factory=ErdStyles)
    dfd: DfdStyles = Field(default_factory=DfdStyles)


# ─────────────────────────────────────────────
# PostgreSQL settings
# ─────────────────────────────────────────────

class DefaultPrimaryKey(BaseModel):
    type: str = "uuid"
    default: str = "gen_random_uuid()"


class PostgresSettings(BaseModel):
    dialect: str = "postgresql"
    extensions: list[str] = Field(default_factory=lambda: ["pgcrypto"])
    schema_name: str = "public"
    default_primary_key: DefaultPrimaryKey = Field(default_factory=DefaultPrimaryKey)
    add_audit_timestamps: bool = True  # auto-add created_at / updated_at


# ─────────────────────────────────────────────
# Review / Proposals
# ─────────────────────────────────────────────

class ReviewProposal(BaseModel):
    id: str = Field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:8]}")
    proposal_type: str
    # e.g. "entity_split" | "foreign_key" | "enum_to_lookup" | "add_column_from_dfd"
    title: str                       # short business-readable title
    question: str                    # the review card question (business language)
    options: list[str]               # 2-3 answer choices
    context: dict[str, Any] = Field(default_factory=dict)
    # machine-readable payload for applying the proposal
    source_evidence: list[str] = Field(default_factory=list)
    source_facts: list[str] = Field(default_factory=list)
    confidence: float = 0.75
    status: Literal["pending", "accepted", "rejected"] = "pending"


class WarningEntry(BaseModel):
    """A structural diagram-rule violation surfaced to the user.

    Produced by `generators.diagram_rules.detect_violations`. See
    `backend/generators/diagram_rules.md` for the rule catalog.
    """
    rule_id: str                              # e.g. "DFD-01"
    severity: Literal["blocking", "warning"] = "warning"
    node_kind: Literal[
        "entity", "relationship", "attribute",
        "data_store", "process", "external_entity", "data_flow",
        "global",
    ] = "global"
    node_id: str | None = None
    node_name: str | None = None
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class ReviewModel(BaseModel):
    proposals: list[ReviewProposal] = Field(default_factory=list)
    warnings: list[WarningEntry] = Field(default_factory=list)
    dismissed_warnings: list[str] = Field(default_factory=list)

    @field_validator("warnings", mode="before")
    @classmethod
    def _migrate_legacy_warnings(cls, v: Any) -> Any:
        # Pre-rules-engine projects stored warnings as list[str]. Upgrade silently.
        if isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            return [
                {"rule_id": "LEGACY", "severity": "warning",
                 "node_kind": "global", "message": s}
                for s in v
            ]
        return v


# ─────────────────────────────────────────────
# Top-level PenFile
# ─────────────────────────────────────────────

class ProjectMeta(BaseModel):
    id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:8]}")
    name: str = "Untitled Project"
    revision: int = 0


class PenFile(BaseModel):
    documentType: Literal["dashbot.dfdmaker"] = "dashbot.dfdmaker"
    schemaVersion: str = "0.2"
    pen_version: str = "0.1"
    project: ProjectMeta = Field(default_factory=ProjectMeta)
    sources: list[SourceRef] = Field(default_factory=list)
    erd: ErdModel = Field(default_factory=ErdModel)
    dfd: DfdModel = Field(default_factory=DfdModel)
    layout: Layout = Field(default_factory=Layout)
    styles: Styles = Field(default_factory=Styles)
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    review: ReviewModel = Field(default_factory=ReviewModel)
