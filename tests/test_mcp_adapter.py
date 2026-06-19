"""Pytest tests for MCP adapter (src/dataroot/systemmap/mcp_adapter.py)."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from dataroot.systemmap.mcp_adapter import (
    MCPClientAdapter,
    _infer_operation,
    _infer_sensitivity,
    _parse_schema_field,
    _pascal_case,
    discover_mcp_server,
)
from dataroot.systemmap.ids import stable_id
from dataroot.systemmap.models import (
    AccessSurface,
    DataField,
    DataObject,
    EnterpriseSystem,
    Evidence,
    SystemMap,
)


# =============================================================================
# Fixtures
# =============================================================================

MOCK_TOOLS_RESPONSE = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {
                "name": "get_theta",
                "description": "Retrieve theta reading for a given subject.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "subject_ref": {
                            "type": "string",
                            "description": "Reference to the subject.",
                        },
                        "include_history": {
                            "type": "boolean",
                            "description": "Include historical readings.",
                        },
                    },
                    "required": ["subject_ref"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "value": {"type": "number"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            {
                "name": "create_device",
                "description": "Create a new device record.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "owner_email": {"type": "string", "description": "Owner email address."},
                        "config": {"type": "object", "description": "Device configuration."},
                    },
                    "required": ["device_id"],
                },
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "device_id": {"type": "string"},
                        "created_at": {"type": "string"},
                    },
                },
            },
        ]
    },
}


# =============================================================================
# Test 1: stable_id generation for tools
# =============================================================================

class TestStableIdGeneration:
    """Tests for stable_id generation patterns used by MCP adapter."""

    def test_stable_id_for_system(self) -> None:
        """System IDs should be stable and deterministic."""
        sid = stable_id("system", "mcp_server", "saas_a")
        assert sid.startswith("system_mcp_server_saas_a_")
        assert len(sid) <= 96

    def test_stable_id_for_surface(self) -> None:
        """Surface IDs should include server and tool name."""
        sid = stable_id("surface", "saas_a", "get_theta")
        assert sid.startswith("surface_saas_a_get_theta_")
        assert "_" in sid

    def test_stable_id_for_object(self) -> None:
        """Object IDs should include server, tool name, and direction."""
        sid = stable_id("object", "saas_a", "get_theta", "input")
        assert "saas_a" in sid
        assert "get_theta" in sid
        assert "input" in sid

    def test_stable_id_for_field(self) -> None:
        """Field IDs should include field name and have correct prefix."""
        object_id = stable_id("object", "saas_a", "get_theta", "input")
        fid = stable_id("field", object_id, "subject_ref")
        assert "subject_ref" in fid
        # Field ID should start with field_ prefix
        assert fid.startswith("field_")
        # Field ID should be unique and valid length
        assert len(fid) <= 96

    def test_stable_id_for_evidence(self) -> None:
        """Evidence IDs should use mcp evidence prefix."""
        eid = stable_id("evidence", "mcp_server", "saas_a")
        assert eid.startswith("evidence_mcp_server_saas_a_")

    def test_stable_id_deterministic(self) -> None:
        """Same inputs should produce same ID."""
        sid1 = stable_id("surface", "saas_a", "get_theta")
        sid2 = stable_id("surface", "saas_a", "get_theta")
        assert sid1 == sid2

    def test_stable_id_handles_special_chars(self) -> None:
        """IDs should sanitize special characters."""
        sid = stable_id("surface", "SaaS A", "tool-name_foo")
        assert "/" not in sid
        assert " " not in sid


# =============================================================================
# Test 2: AccessSurface creation from tool descriptor
# =============================================================================

class TestAccessSurfaceCreation:
    """Tests for AccessSurface creation from MCP tool descriptors."""

    def test_surface_has_correct_kind(self) -> None:
        """MCP tool surfaces should have kind=mcp_tool."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        surfaces = system_map.access_surfaces
        assert all(s.kind == "mcp_tool" for s in surfaces)

    def test_surface_operation_inferred_from_name(self) -> None:
        """Operation should be inferred from tool name patterns."""
        assert _infer_operation("get_theta") == "read"
        assert _infer_operation("list_devices") == "read"
        assert _infer_operation("create_device") == "write"
        assert _infer_operation("update_config") == "write"
        assert _infer_operation("delete_record") == "write"
        assert _infer_operation("send_notification") == "write"
        assert _infer_operation("execute_query") == "write"

    def test_surface_has_correct_locator(self) -> None:
        """Surface address should follow mcp:// protocol."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        for surface in system_map.access_surfaces:
            assert surface.address.startswith("mcp://saas_a/")
            assert surface.name in surface.address

    def test_surface_references_system(self) -> None:
        """Surface should reference its parent system."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        for surface in system_map.access_surfaces:
            assert surface.system_id == "saas_a"

    def test_surface_auth_config(self) -> None:
        """Surface should carry auth configuration."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
            auth_method="oauth2",
            auth_scopes=["theta:read"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        for surface in system_map.access_surfaces:
            assert surface.auth.method == "oauth2"
            assert "theta:read" in surface.auth.scopes


# =============================================================================
# Test 3: DataObject+DataField parsing from JSON Schema
# =============================================================================

class TestDataObjectParsing:
    """Tests for DataObject and DataField parsing from JSON Schema."""

    def test_input_object_created(self) -> None:
        """Input schema should create a DataObject."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        object_names = [obj.name for obj in system_map.data_objects]
        assert "GetThetaInput" in object_names
        assert "CreateDeviceInput" in object_names

    def test_output_object_created(self) -> None:
        """Output schema should create a DataObject."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        object_names = [obj.name for obj in system_map.data_objects]
        assert "GetThetaOutput" in object_names
        assert "CreateDeviceOutput" in object_names

    def test_object_references_system(self) -> None:
        """DataObject should reference its parent system."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        for obj in system_map.data_objects:
            assert obj.system_id == "saas_a"

    def test_object_references_surface(self) -> None:
        """DataObject should reference its parent surface."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        for obj in system_map.data_objects:
            assert len(obj.surface_ids) >= 1


class TestDataFieldParsing:
    """Tests for DataField parsing from JSON Schema properties."""

    def test_fields_created_from_properties(self) -> None:
        """Fields should be created from schema properties."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        field_names = [f.name for f in system_map.data_fields]
        assert "subject_ref" in field_names
        assert "include_history" in field_names
        assert "device_id" in field_names
        assert "owner_email" in field_names

    def test_required_fields_not_nullable(self) -> None:
        """Required fields should have nullable=False."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Find subject_ref field (required in get_theta input)
        subject_ref_field = next(
            (f for f in system_map.data_fields if f.name == "subject_ref"), None
        )
        assert subject_ref_field is not None
        assert subject_ref_field.nullable is False

    def test_optional_fields_nullable(self) -> None:
        """Optional fields should have nullable=True."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Find include_history field (not required)
        include_history_field = next(
            (f for f in system_map.data_fields if f.name == "include_history"), None
        )
        assert include_history_field is not None
        assert include_history_field.nullable is True

    def test_array_type_parsed(self) -> None:
        """Array types should be parsed as item_type[]."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Find tags field (array of strings)
        tags_field = next(
            (f for f in system_map.data_fields if f.name == "tags"), None
        )
        assert tags_field is not None
        assert tags_field.type == "string[]"

    def test_object_type_parsed(self) -> None:
        """Object types should be parsed correctly."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Find config field (object type)
        config_field = next(
            (f for f in system_map.data_fields if f.name == "config"), None
        )
        assert config_field is not None
        assert config_field.type == "object"

    def test_field_source_path(self) -> None:
        """Fields should have correct source_path."""
        field = _parse_schema_field(
            field_name="test_field",
            field_def={"type": "string"},
            object_id="obj_123",
            locator="mcp://test/test#inputSchema/properties/test_field",
            required_fields=set(),
            captured_at="2026-01-01T00:00:00Z",
        )
        assert field.source_path == "$.test_field"

    def test_field_description_from_schema(self) -> None:
        """Field description should come from schema."""
        field = _parse_schema_field(
            field_name="owner_email",
            field_def={"type": "string", "description": "Owner email address."},
            object_id="obj_123",
            locator="mcp://test/test#inputSchema/properties/owner_email",
            required_fields=set(),
            captured_at="2026-01-01T00:00:00Z",
        )
        assert field.description == "Owner email address."


class TestSensitivityInference:
    """Tests for sensitivity inference from field names."""

    def test_secret_sensitivity(self) -> None:
        """Fields with secret indicators should be marked secret."""
        assert _infer_sensitivity("password") == "secret"
        assert _infer_sensitivity("api_secret") == "secret"
        assert _infer_sensitivity("auth_token") == "secret"
        assert _infer_sensitivity("private_key") == "secret"

    def test_pii_sensitivity(self) -> None:
        """Fields with PII indicators should be marked pii."""
        assert _infer_sensitivity("email") == "pii"
        assert _infer_sensitivity("owner_email") == "pii"
        assert _infer_sensitivity("phone_number") == "pii"
        assert _infer_sensitivity("full_name") == "pii"

    def test_internal_sensitivity(self) -> None:
        """Other fields should default to internal."""
        assert _infer_sensitivity("device_id") == "internal"
        assert _infer_sensitivity("created_at") == "internal"
        assert _infer_sensitivity("status") == "internal"


class TestPascalCase:
    """Tests for PascalCase conversion."""

    def test_snake_case_conversion(self) -> None:
        """Snake case names should convert to PascalCase."""
        assert _pascal_case("get_theta") == "GetTheta"
        assert _pascal_case("list_devices") == "ListDevices"
        assert _pascal_case("create_new_device") == "CreateNewDevice"

    def test_kebab_case_conversion(self) -> None:
        """Kebab case names should convert to PascalCase."""
        assert _pascal_case("get-theta") == "GetTheta"
        assert _pascal_case("list-devices") == "ListDevices"

    def test_uppercase_conversion(self) -> None:
        """Uppercase names should convert to PascalCase."""
        assert _pascal_case("GET_THETA") == "GetTheta"


# =============================================================================
# Test 4: Evidence creation with correct kind and locator
# =============================================================================

class TestEvidenceCreation:
    """Tests for Evidence creation with correct attributes."""

    def test_system_evidence_kind(self) -> None:
        """System evidence should have kind=mcp_descriptor."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        system = system_map.systems[0]
        assert len(system.evidence) >= 1
        assert all(e.kind == "mcp_descriptor" for e in system.evidence)

    def test_system_evidence_locator_format(self) -> None:
        """System evidence locator should follow mcp:// protocol."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        system = system_map.systems[0]
        evidence = system.evidence[0]
        assert evidence.locator == "mcp://saas_a/tools/list"

    def test_surface_evidence_locator_format(self) -> None:
        """Surface evidence locator should include tool name."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        surface = next(
            (s for s in system_map.access_surfaces if s.name == "get_theta"), None
        )
        assert surface is not None
        evidence = surface.evidence[0]
        assert evidence.locator == "mcp://saas_a/get_theta"
        assert evidence.kind == "mcp_descriptor"

    def test_object_evidence_locator_format(self) -> None:
        """Object evidence locator should include schema reference."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        obj = next((o for o in system_map.data_objects if o.name == "GetThetaInput"), None)
        assert obj is not None
        evidence = obj.evidence[0]
        assert "#inputSchema" in evidence.locator
        assert evidence.kind == "mcp_descriptor"

    def test_field_evidence_locator_format(self) -> None:
        """Field evidence locator should include property path."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        field = next(
            (f for f in system_map.data_fields if f.name == "subject_ref"), None
        )
        assert field is not None
        evidence = field.evidence[0]
        assert "properties/subject_ref" in evidence.locator
        assert evidence.kind == "mcp_descriptor"

    def test_evidence_confidence(self) -> None:
        """Evidence should have appropriate confidence values."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # System evidence should have high confidence
        assert system_map.systems[0].evidence[0].confidence == 0.9

        # Surface evidence should have high confidence
        assert system_map.access_surfaces[0].evidence[0].confidence == 0.9

        # Object/Field evidence should have slightly lower confidence
        for obj in system_map.data_objects:
            assert obj.evidence[0].confidence == 0.85


# =============================================================================
# Test 5: SystemMap validation after adding MCP-derived records
# =============================================================================

class TestSystemMapValidation:
    """Tests for SystemMap validation with MCP-derived records."""

    def test_system_map_validates_successfully(self) -> None:
        """MCP-derived SystemMap should pass validation."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Should not raise
        SystemMap.model_validate(system_map.model_dump())

    def test_system_map_graph_integrity(self) -> None:
        """SystemMap should maintain referential integrity."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        system_ids = {s.id for s in system_map.systems}
        surface_ids = {s.id for s in system_map.access_surfaces}
        object_ids = {o.id for o in system_map.data_objects}
        field_ids = {f.id for f in system_map.data_fields}

        # All surfaces should reference valid systems
        for surface in system_map.access_surfaces:
            assert surface.system_id in system_ids

        # All objects should reference valid systems
        for obj in system_map.data_objects:
            assert obj.system_id in system_ids
            for surface_id in obj.surface_ids:
                assert surface_id in surface_ids

        # All fields should reference valid objects
        for field in system_map.data_fields:
            assert field.object_id in object_ids

    def test_system_map_no_duplicate_ids(self) -> None:
        """SystemMap should not have duplicate IDs across record types."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        all_ids: list[str] = []
        all_ids.extend([s.id for s in system_map.systems])
        all_ids.extend([s.id for s in system_map.access_surfaces])
        all_ids.extend([o.id for o in system_map.data_objects])
        all_ids.extend([f.id for f in system_map.data_fields])

        assert len(all_ids) == len(set(all_ids))

    def test_system_map_round_trip(self) -> None:
        """MCP-derived SystemMap should round-trip through JSON."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = adapter.discover()

        # Round trip through JSON
        json_dict = system_map.to_json_dict()
        restored = SystemMap.from_json_dict(json_dict)

        assert len(restored.systems) == len(system_map.systems)
        assert len(restored.access_surfaces) == len(system_map.access_surfaces)
        assert len(restored.data_objects) == len(system_map.data_objects)
        assert len(restored.data_fields) == len(system_map.data_fields)


# =============================================================================
# Test convenience function
# =============================================================================

class TestDiscoverMcpServer:
    """Tests for the discover_mcp_server convenience function."""

    def test_discover_returns_system_map(self) -> None:
        """discover_mcp_server should return a valid SystemMap."""
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = discover_mcp_server(
                server_id="saas_a",
                server_name="SaaS A",
                command=["npx", "saas-a-mcp"],
            )

        assert isinstance(system_map, SystemMap)
        assert len(system_map.systems) == 1
        assert len(system_map.access_surfaces) == 2

    def test_discover_with_auth(self) -> None:
        """discover_mcp_server should pass auth configuration."""
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, MOCK_TOOLS_RESPONSE)
            system_map = discover_mcp_server(
                server_id="saas_a",
                server_name="SaaS A",
                command=["npx", "saas-a-mcp"],
                auth_method="oauth2",
                auth_scopes=["theta:read", "iota:read"],
            )

        for surface in system_map.access_surfaces:
            assert surface.auth.method == "oauth2"
            assert "theta:read" in surface.auth.scopes


# =============================================================================
# Test error handling
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in MCP adapter."""

    def test_handles_empty_tools_list(self) -> None:
        """Adapter should handle empty tools list."""
        empty_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"tools": []},
        }
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, empty_response)
            system_map = adapter.discover()

        assert len(system_map.systems) == 1
        assert len(system_map.access_surfaces) == 0

    def test_handles_tools_as_list(self) -> None:
        """Adapter should handle tools as direct list."""
        list_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                {"name": "tool_one", "description": "First tool", "inputSchema": {"type": "object", "properties": {}}},
            ],
        }
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, list_response)
            system_map = adapter.discover()

        assert len(system_map.access_surfaces) == 1
        assert system_map.access_surfaces[0].name == "tool_one"

    def test_handles_no_schema(self) -> None:
        """Adapter should handle tools without schemas."""
        no_schema_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {"name": "simple_tool", "description": "A simple tool"},
                ]
            },
        }
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, no_schema_response)
            system_map = adapter.discover()

        assert len(system_map.access_surfaces) == 1
        assert len(system_map.data_objects) == 0

    def test_raises_on_subprocess_error(self) -> None:
        """Adapter should raise RuntimeError on subprocess failure."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "nonexistent-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("Command not found")

            with pytest.raises(RuntimeError, match="Failed to spawn"):
                adapter.discover()

    def test_raises_on_invalid_json(self) -> None:
        """Adapter should raise RuntimeError on invalid JSON response."""
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            mock_proc = MagicMock()
            mock_proc.stdin = MagicMock()
            mock_proc.stdout = MagicMock()
            mock_proc.stdout.readline.return_value = "not valid json"
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.read.return_value = ""
            mock_proc.returncode = 0
            mock_popen.return_value = mock_proc

            with pytest.raises(RuntimeError, match="Invalid JSON"):
                adapter.discover()

    def test_raises_on_mcp_error(self) -> None:
        """Adapter should raise RuntimeError on MCP server error."""
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32603, "message": "Internal error"},
        }
        adapter = MCPClientAdapter(
            server_id="saas_a",
            server_name="SaaS A",
            command=["npx", "saas-a-mcp"],
        )
        with patch("subprocess.Popen") as mock_popen:
            _setup_mock_subprocess(mock_popen, error_response)

            with pytest.raises(RuntimeError, match="MCP server error"):
                adapter.discover()


# =============================================================================
# Helper functions
# =============================================================================

def _setup_mock_subprocess(mock_popen: MagicMock, response: dict[str, object]) -> None:
    """Set up a mock subprocess that returns the given JSON response."""
    mock_proc = MagicMock()
    mock_proc.stdin = MagicMock()
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.readline.return_value = json.dumps(response) + "\n"
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = ""
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc
