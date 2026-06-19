// TypeScript mirrors of backend Pydantic models (pen.py + source.py)
// Keep in sync with backend/models/pen.py

export type KeyRole = "primary" | "foreign" | "unique" | "audit" | "business_key" | "none";
export type ReviewStatus = "accepted" | "needs_review" | "rejected";
export type ProposalStatus = "pending" | "accepted" | "rejected";
export type EntityKind = "strong_entity" | "weak_entity" | "lookup_table";

export interface AttributeEvidence {
  source_id: string;
  source_columns: string[];
}

export interface Attribute {
  id: string;
  name: string;
  display_name?: string;
  pg_type: string;
  key_role: KeyRole;
  nullable: boolean;
  default?: string;
  check_constraint?: string;
  source_columns: string[];
  evidence: AttributeEvidence[];
  confidence: number;
  review_status: ReviewStatus;
}

export interface Entity {
  id: string;
  kind: EntityKind;
  name: string;
  display_name: string;
  domain?: string;        // owning business process (labels/grouping only; not a color)
  connects?: string[];    // departments this entity bridges; non-empty => seam (connection point)
  attributes: Attribute[];
  source_evidence: AttributeEvidence[];
  proposal_reason?: string;
  confidence: number;
  review_status: ReviewStatus;
}

export interface Cardinality {
  from_min: number;
  from_max: number | "many";
  to_min: number;
  to_max: number | "many";
}

export interface RelationshipPostgres {
  constraint_name: string;
  on_delete: "restrict" | "cascade" | "set_null" | "set_default" | "no_action";
  on_update: "restrict" | "cascade" | "set_null" | "set_default" | "no_action";
}

export interface RelationshipEndpoint {
  entity_id: string;
  attribute_id: string;
}

export interface Relationship {
  id: string;
  name?: string;
  from: RelationshipEndpoint;
  to: RelationshipEndpoint;
  cardinality: Cardinality;
  postgres?: RelationshipPostgres;
  dfd_process_id?: string;
  evidence: string[];
  confidence: number;
  review_status: ReviewStatus;
}

export interface ErdModel {
  notation: "crows_foot";
  model_level: "physical";
  entities: Entity[];
  relationships: Relationship[];
}

export interface ExternalEntity {
  id: string;
  name: string;
  description?: string;
  source: "manual" | "auto";
  source_evidence: string[];
  source_facts: string[];
}

export interface Process {
  id: string;
  number?: string;
  name: string;
  description?: string;
  user_modified: boolean;
  mapped_relationship_id?: string;
  source_evidence: string[];
  source_facts: string[];
  level_1_diagram?: DfdModel;
}

export interface DataStore {
  id: string;
  name: string;
  description?: string;
  mapped_erd_entity?: string;
  user_modified: boolean;
  source_evidence: string[];
  source_facts: string[];
}

export interface DataFlow {
  id: string;
  from: string;
  to: string;
  data_name?: string;
  mapped_relationship_id?: string;
  user_modified?: boolean;
  mapped_erd_entities: string[];
  mapped_erd_attributes: string[];
  source_evidence: string[];
  source_facts: string[];
}

export interface SystemBoundary {
  id: string;
  name: string;
}

export type RuleCategory = "invariant" | "state_machine" | "gate" | "validation" | "lifecycle";
export type RuleSeverity = "constraint" | "warning" | "best_practice";

export interface BusinessRule {
  id: string;
  context?: string;
  entity_id?: string;
  relationship_id?: string;
  process_id?: string;
  title: string;
  statement: string;
  category: RuleCategory;
  condition?: string;
  enforced_at: string[];
  spec_source?: string;
  verified_by?: string;
  severity: RuleSeverity;
  status: "enforced" | "gap" | "deferred";
  review_status: ReviewStatus;
}

export type ConnectorKind = "seam" | "webhook" | "fan_out" | "middleware" | "shared_service" | "auth";

export interface Connector {
  id: string;
  name: string;
  kind: ConnectorKind;
  trigger?: string;
  effect?: string;
  from_context?: string;
  to_contexts: string[];
  contract?: string;
  enforced_at: string[];
  spec_source?: string;
  status: "wired" | "deferred";
  review_status: ReviewStatus;
}

export interface DfdModel {
  level: number;
  notation: "yourdon_coad";
  system_boundary: SystemBoundary;
  external_entities: ExternalEntity[];
  processes: Process[];
  data_stores: DataStore[];
  data_flows: DataFlow[];
  business_rules?: BusinessRule[];
  connectors?: Connector[];
}

export interface LayoutNode {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface LayoutPoint {
  x: number;
  y: number;
}

export interface LayoutEdge {
  id: string;
  route: "orthogonal" | "straight" | "bezier";
  source_handle?: string;
  target_handle?: string;
  points?: LayoutPoint[];
  label_t?: number;
  label_offset?: number;
}

export interface DiagramLayout {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
}

export interface Layout {
  erd: DiagramLayout;
  dfd: DiagramLayout;
  dfd_level_1: Record<string, DiagramLayout>;
}

export interface Styles {
  theme: string;
  erd: Record<string, unknown>;
  dfd: Record<string, unknown>;
}

export interface DefaultPrimaryKey {
  type: string;
  default: string;
}

export interface PostgresSettings {
  dialect: string;
  extensions: string[];
  schema_name: string;
  default_primary_key: DefaultPrimaryKey;
  add_audit_timestamps: boolean;
}

export interface ReviewProposal {
  id: string;
  proposal_type: string;
  title: string;
  question: string;
  options: string[];
  context: Record<string, unknown>;
  source_evidence: string[];
  source_facts: string[];
  confidence: number;
  status: ProposalStatus;
}

export type WarningNodeKind =
  | "entity"
  | "relationship"
  | "attribute"
  | "data_store"
  | "process"
  | "external_entity"
  | "data_flow"
  | "global";

export interface WarningEntry {
  rule_id: string;
  severity: "blocking" | "warning";
  node_kind: WarningNodeKind;
  node_id?: string | null;
  node_name?: string | null;
  message: string;
  context: Record<string, unknown>;
}

export interface ReviewModel {
  proposals: ReviewProposal[];
  warnings: WarningEntry[];
  dismissed_warnings?: string[];
}

export interface SourceRef {
  id: string;
  type: "xlsx" | "csv" | "text";
  name: string;
  raw_path?: string;
}

export interface ProjectMeta {
  id: string;
  name: string;
  revision: number;
}

export type DiagramScope =
  | { diagram: "erd"; level?: "root" }
  | { diagram: "dfd"; level: "root" }
  | { diagram: "dfd"; level: "process"; process_id: string };

export interface PenFile {
  pen_version: string;
  project: ProjectMeta;
  sources: SourceRef[];
  erd: ErdModel;
  dfd: DfdModel;
  layout: Layout;
  styles: Styles;
  postgres: PostgresSettings;
  review: ReviewModel;
}

// API response types

export interface IngestResponse {
  project_id: string;
  source_tables: unknown[];
  pen: PenFile;
}

export interface Conflict {
  type: string;
  severity: "blocking" | "warning";
  message: string;
  object_id: string;
  context: Record<string, unknown>;
}

export interface ValidateResponse {
  valid: boolean;
  conflicts: Conflict[];
}

export interface StaticAnalysisIssue {
  severity: "error" | "warning";
  category: string;
  message: string;
  object_id: string;
  object_type: "entity" | "relationship" | "attribute" | "process" | "data_store" | "external_entity" | "data_flow";
  fix_suggestion: string | null;
  context: Record<string, unknown>;
}

export interface AnalyzeResponse {
  valid: boolean;
  blocking_count: number;
  warning_count: number;
  static_issue_count: number;
  conflicts: Conflict[];
  static_issues: StaticAnalysisIssue[];
}

export interface FixSuggestion {
  op: string;
  payload: Record<string, unknown>;
  label: string;
  reason: string;
}

export interface ChatMessage {
  role: "user" | "ai";
  text: string;
  suggestions?: FixSuggestion[];
}

export interface ChatResponse {
  message: string;
  suggestions: FixSuggestion[];
}
