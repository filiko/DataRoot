"""Source-agnostic enterprise System Map models and registry helpers."""

from dataroot.systemmap.fixtures import generic_saas_abc_map
from dataroot.systemmap.ids import stable_id
from dataroot.systemmap.mcp_adapter import MCPClientAdapter, discover_mcp_server
from dataroot.systemmap.models import (
    AccessSurface,
    AuthConfig,
    BusinessRule,
    Connector,
    DataField,
    DataFlow,
    DataObject,
    EnterpriseSystem,
    Evidence,
    Ref,
    SystemMap,
)
from dataroot.systemmap.registry import (
    ConnectorRegistry,
    ConnectorRegistrySystem,
    load_connector_registry,
    registry_to_system_map,
)
from dataroot.systemmap.seams import (
    RuleGrounding,
    detect_cross_system_seams,
    ground_business_rules,
)

__all__ = [
    "AccessSurface",
    "AuthConfig",
    "BusinessRule",
    "Connector",
    "ConnectorRegistry",
    "ConnectorRegistrySystem",
    "DataField",
    "DataFlow",
    "DataObject",
    "EnterpriseSystem",
    "Evidence",
    "MCPClientAdapter",
    "Ref",
    "RuleGrounding",
    "SystemMap",
    "detect_cross_system_seams",
    "discover_mcp_server",
    "generic_saas_abc_map",
    "ground_business_rules",
    "load_connector_registry",
    "registry_to_system_map",
    "stable_id",
]
