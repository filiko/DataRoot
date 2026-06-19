"""Canonical source-agnostic System Map model.

The System Map is intentionally above ERD/DFD. Diagram files and GitKB docs are
projections from these records, not the canonical enterprise inventory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReviewStatus = Literal["accepted", "needs_review", "rejected"]
SystemKind = Literal["saas", "internal_service", "database", "mcp_server", "repo", "file_store", "event_bus"]
Environment = Literal["prod", "staging", "dev"]
AccessSurfaceKind = Literal[
    "mcp_tool",
    "openapi_endpoint",
    "graphql",
    "webhook",
    "db_table",
    "event_stream",
    "file_export",
    "sdk_method",
]
Operation = Literal["read", "write", "subscribe"]
AuthMethod = Literal["none", "api_key", "oauth2", "bearer", "basic", "mtls", "iam"]
Sensitivity = Literal["public", "internal", "confidential", "pii", "secret"]
RuleCategory = Literal["invariant", "state_machine", "gate", "validation", "lifecycle"]
RuleSeverity = Literal["constraint", "warning", "best_practice"]
RuleStatus = Literal["enforced", "gap", "deferred"]
ConnectorKind = Literal["seam", "webhook", "fan_out", "middleware", "shared_service", "auth", "etl", "sync"]
ConnectorStatus = Literal["wired", "deferred"]
EvidenceKind = Literal["mcp_descriptor", "openapi_spec", "repo_file", "db_metadata", "doc", "sample_payload", "manual"]
RefKind = Literal["system", "surface", "object", "process", "flow"]

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


def _captured_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictBaseModel):
    id: str
    kind: EvidenceKind
    locator: str
    excerpt: str | None = None
    confidence: Confidence = 1.0
    captured_at: str = Field(default_factory=_captured_now)


class EvidenceBacked(StrictBaseModel):
    evidence: list[Evidence] = Field(min_length=1)
    confidence: Confidence = 1.0
    review_status: ReviewStatus = "needs_review"


class EnterpriseSystem(EvidenceBacked):
    id: str
    name: str
    vendor: str | None = None
    kind: SystemKind
    environment: Environment | None = None
    owner: str | None = None
    description: str | None = None


class AuthConfig(StrictBaseModel):
    method: AuthMethod = "none"
    scopes: list[str] = Field(default_factory=list)


class AccessSurface(EvidenceBacked):
    id: str
    system_id: str
    kind: AccessSurfaceKind
    operation: Operation
    name: str
    address: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    rate_limits: str | None = None
    pagination: str | None = None
    request_schema_ref: str | None = None
    response_schema_ref: str | None = None


class DataObject(EvidenceBacked):
    id: str
    system_id: str
    surface_ids: list[str] = Field(default_factory=list)
    name: str
    description: str | None = None
    maps_to_entity_id: str | None = None


class DataField(EvidenceBacked):
    id: str
    object_id: str
    name: str
    type: str
    nullable: bool = True
    sensitivity: Sensitivity = "internal"
    owner: str | None = None
    source_path: str
    description: str | None = None


class Ref(StrictBaseModel):
    kind: RefKind
    id: str


class BusinessRule(EvidenceBacked):
    id: str
    scope: Ref
    title: str
    statement: str
    category: RuleCategory = "invariant"
    condition: str | None = None
    enforced_at: list[str] = Field(default_factory=list)
    spec_source: str | None = None
    severity: RuleSeverity = "constraint"
    status: RuleStatus = "enforced"


class Connector(EvidenceBacked):
    id: str
    name: str
    kind: ConnectorKind = "seam"
    trigger: str | None = None
    effect: str | None = None
    from_system: str | None = None
    to_systems: list[str] = Field(default_factory=list)
    contract: str | None = None
    enforced_at: list[str] = Field(default_factory=list)
    spec_source: str | None = None
    status: ConnectorStatus = "wired"


class DataFlow(StrictBaseModel):
    id: str
    from_ref: Ref
    to_ref: Ref
    via: str | None = None
    data_object_ids: list[str] = Field(default_factory=list)
    trigger: str | None = None
    evidence: list[Evidence] = Field(min_length=1)
    confidence: Confidence = 1.0


class SystemMap(StrictBaseModel):
    systems: list[EnterpriseSystem] = Field(default_factory=list)
    access_surfaces: list[AccessSurface] = Field(default_factory=list)
    data_objects: list[DataObject] = Field(default_factory=list)
    data_fields: list[DataField] = Field(default_factory=list)
    business_rules: list[BusinessRule] = Field(default_factory=list)
    connectors: list[Connector] = Field(default_factory=list)
    data_flows: list[DataFlow] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph(self) -> "SystemMap":
        system_ids = _ids("systems", self.systems)
        surface_ids = _ids("access_surfaces", self.access_surfaces)
        object_ids = _ids("data_objects", self.data_objects)
        field_ids = _ids("data_fields", self.data_fields)
        rule_ids = _ids("business_rules", self.business_rules)
        connector_ids = _ids("connectors", self.connectors)
        flow_ids = _ids("data_flows", self.data_flows)

        seen: dict[str, str] = {}
        for group, ids in {
            "systems": system_ids,
            "access_surfaces": surface_ids,
            "data_objects": object_ids,
            "data_fields": field_ids,
            "business_rules": rule_ids,
            "connectors": connector_ids,
            "data_flows": flow_ids,
        }.items():
            for record_id in ids:
                if record_id in seen:
                    raise ValueError(f"duplicate id across System Map: {record_id} in {seen[record_id]} and {group}")
                seen[record_id] = group

        for surface in self.access_surfaces:
            _require(surface.system_id, system_ids, f"access surface {surface.id} system_id")
            if surface.request_schema_ref:
                _require(surface.request_schema_ref, object_ids, f"access surface {surface.id} request_schema_ref")
            if surface.response_schema_ref:
                _require(surface.response_schema_ref, object_ids, f"access surface {surface.id} response_schema_ref")

        for obj in self.data_objects:
            _require(obj.system_id, system_ids, f"data object {obj.id} system_id")
            for surface_id in obj.surface_ids:
                _require(surface_id, surface_ids, f"data object {obj.id} surface_ids")

        for field in self.data_fields:
            _require(field.object_id, object_ids, f"data field {field.id} object_id")

        for rule in self.business_rules:
            _require_ref(rule.scope, system_ids, surface_ids, object_ids, flow_ids, f"business rule {rule.id} scope")

        for connector in self.connectors:
            if connector.from_system:
                _require(connector.from_system, system_ids, f"connector {connector.id} from_system")
            for system_id in connector.to_systems:
                _require(system_id, system_ids, f"connector {connector.id} to_systems")

        for flow in self.data_flows:
            _require_ref(flow.from_ref, system_ids, surface_ids, object_ids, flow_ids, f"data flow {flow.id} from_ref")
            _require_ref(flow.to_ref, system_ids, surface_ids, object_ids, flow_ids, f"data flow {flow.id} to_ref")
            for object_id in flow.data_object_ids:
                _require(object_id, object_ids, f"data flow {flow.id} data_object_ids")
            if flow.via and flow.via not in connector_ids and not flow.via.startswith("proc_"):
                raise ValueError(f"data flow {flow.id} via references unknown connector/process: {flow.via}")

        return self

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> "SystemMap":
        return cls.model_validate(payload)


def _ids(group: str, records: list[Any]) -> set[str]:
    ids = [record.id for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate ids in {group}")
    return set(ids)


def _require(record_id: str, valid_ids: set[str], label: str) -> None:
    if record_id not in valid_ids:
        raise ValueError(f"{label} references unknown id: {record_id}")


def _require_ref(
    ref: Ref,
    system_ids: set[str],
    surface_ids: set[str],
    object_ids: set[str],
    flow_ids: set[str],
    label: str,
) -> None:
    if ref.kind == "system":
        _require(ref.id, system_ids, label)
    elif ref.kind == "surface":
        _require(ref.id, surface_ids, label)
    elif ref.kind == "object":
        _require(ref.id, object_ids, label)
    elif ref.kind == "flow":
        _require(ref.id, flow_ids, label)
    elif ref.kind == "process":
        if not ref.id.startswith("proc_"):
            raise ValueError(f"{label} process refs must use proc_ IDs: {ref.id}")
