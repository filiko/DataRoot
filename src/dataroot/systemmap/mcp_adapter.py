"""MCP client adapter for System Map discovery.

Spawns an MCP server over stdio, sends tools/list, and converts the response
into System Map records (EnterpriseSystem, AccessSurface, DataObject, DataField)
with evidence-backed provenance.

This adapter is source-agnostic: it works with any MCP server that implements
the standard tools/list protocol. No Nexus or vendor-specific logic is included.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from dataroot.systemmap.ids import stable_id
from dataroot.systemmap.models import (
    AccessSurface,
    AuthConfig,
    DataField,
    DataObject,
    EnterpriseSystem,
    Evidence,
    SystemMap,
)

# JSON-RPC constants
JSONRPC_VERSION = "2.0"
TOOLS_LIST_METHOD = "tools/list"


def _captured_now() -> str:
    """Return ISO timestamp without microseconds."""
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MCPClientAdapter:
    """Adapter that introspects an MCP server and emits System Map records.

    Args:
        server_id: Stable identifier for the MCP server being introspected.
        server_name: Human-readable name for the server.
        command: Command line to spawn the MCP server (e.g., ["npx", "some-mcp"]).
        auth_method: Auth method to record on discovered surfaces.
        auth_scopes: Auth scopes to record on discovered surfaces.
    """

    def __init__(
        self,
        server_id: str,
        server_name: str,
        command: list[str],
        auth_method: str = "none",
        auth_scopes: list[str] | None = None,
    ) -> None:
        self.server_id = server_id
        self.server_name = server_name
        self.command = command
        self.auth = AuthConfig(method=auth_method, scopes=auth_scopes or [])

    def discover(self) -> SystemMap:
        """Connect to the MCP server, run tools/list, and return System Map records.

        Returns:
            SystemMap containing the server, its tools as AccessSurfaces,
            and parsed input/output schemas as DataObjects with DataFields.

        Raises:
            RuntimeError: If the MCP server cannot be started or responds with an error.
        """
        tools = self._list_tools()
        return self._build_system_map(tools)

    def _list_tools(self) -> list[dict[str, Any]]:
        """Spawn the MCP server and request tools/list.

        Returns:
            List of tool descriptor dicts from the server's response.

        Raises:
            RuntimeError: If the server cannot be started or the response is invalid.
        """
        request = {
            "jsonrpc": JSONRPC_VERSION,
            "id": 1,
            "method": TOOLS_LIST_METHOD,
            "params": {},
        }

        try:
            proc = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as exc:
            raise RuntimeError(f"Failed to spawn MCP server command {self.command}: {exc}") from exc

        if proc.stdin is None or proc.stdout is None:
            raise RuntimeError(f"MCP server stdin/stdout not available for command {self.command}")

        try:
            proc.stdin.write(json.dumps(request) + "\n")
            proc.stdin.flush()
            response_line = proc.stdout.readline()
            proc.stdin.close()
            proc.wait(timeout=30)
        except TimeoutError:
            proc.kill()
            proc.wait()
            raise RuntimeError(f"MCP server command {self.command} timed out after 30s") from None
        except OSError as exc:
            proc.kill()
            proc.wait()
            raise RuntimeError(f"Communication error with MCP server {self.command}: {exc}") from exc

        if proc.returncode != 0:
            stderr = proc.stderr.read() if proc.stderr else ""
            raise RuntimeError(f"MCP server exited with code {proc.returncode}: {stderr}")

        if not response_line:
            raise RuntimeError(f"Empty response from MCP server {self.command}")

        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from MCP server {self.command}: {exc}") from exc

        if "error" in response:
            error = response["error"]
            raise RuntimeError(f"MCP server error: {error.get('message', error)}")

        if "result" not in response:
            raise RuntimeError(f"Missing result in MCP server response: {response}")

        result = response["result"]
        if isinstance(result, dict) and "tools" in result:
            return result["tools"]
        if isinstance(result, list):
            return result

        raise RuntimeError(f"Unexpected tools/list response structure: {result}")

    def _build_system_map(self, tools: list[dict[str, Any]]) -> SystemMap:
        """Convert tool descriptors into System Map records.

        Args:
            tools: List of tool descriptor dicts from the MCP server.

        Returns:
            SystemMap with server, surfaces, objects, and fields.
        """
        captured_at = _captured_now()

        # Create the enterprise system record
        system_evidence = Evidence(
            id=stable_id("evidence", "mcp_server", self.server_id),
            kind="mcp_descriptor",
            locator=f"mcp://{self.server_id}/tools/list",
            excerpt=f"MCP server {self.server_name} exposes {len(tools)} tool(s)",
            confidence=0.9,
            captured_at=captured_at,
        )

        system = EnterpriseSystem(
            id=self.server_id,
            name=self.server_name,
            kind="mcp_server",
            evidence=[system_evidence],
            confidence=0.9,
            review_status="needs_review",
        )

        surfaces: list[AccessSurface] = []
        objects: list[DataObject] = []
        fields: list[DataField] = []

        for tool in tools:
            tool_name = tool.get("name", "")
            tool_description = tool.get("description", "")
            input_schema = tool.get("inputSchema") or tool.get("input_schema") or {}
            output_schema = tool.get("outputSchema") or tool.get("output_schema") or {}

            # Determine operation type from tool name patterns
            operation = _infer_operation(tool_name)

            # Create AccessSurface for this tool
            surface_id = stable_id("surface", self.server_id, tool_name)
            surface_locator = f"mcp://{self.server_id}/{tool_name}"

            surface_evidence = Evidence(
                id=stable_id("evidence", "mcp_tool", self.server_id, tool_name),
                kind="mcp_descriptor",
                locator=surface_locator,
                excerpt=tool_description[:200] if tool_description else f"MCP tool: {tool_name}",
                confidence=0.9,
                captured_at=captured_at,
            )

            surface = AccessSurface(
                id=surface_id,
                system_id=self.server_id,
                kind="mcp_tool",
                operation=operation,
                name=tool_name,
                address=surface_locator,
                auth=self.auth,
                evidence=[surface_evidence],
                confidence=0.9,
                review_status="needs_review",
            )
            surfaces.append(surface)

            # Parse input schema into DataObject + DataFields
            if input_schema and input_schema.get("type") == "object":
                object_id = stable_id("object", self.server_id, tool_name, "input")
                object_name = f"{_pascal_case(tool_name)}Input"

                object_evidence = Evidence(
                    id=stable_id("evidence", "mcp_object", self.server_id, tool_name, "input"),
                    kind="mcp_descriptor",
                    locator=f"{surface_locator}#inputSchema",
                    excerpt=f"Input schema for MCP tool {tool_name}",
                    confidence=0.85,
                    captured_at=captured_at,
                )

                obj = DataObject(
                    id=object_id,
                    system_id=self.server_id,
                    surface_ids=[surface_id],
                    name=object_name,
                    description=f"Input parameters for MCP tool {tool_name}",
                    evidence=[object_evidence],
                    confidence=0.85,
                    review_status="needs_review",
                )
                objects.append(obj)

                # Parse fields from input schema properties
                properties = input_schema.get("properties") or {}
                required = set(input_schema.get("required") or [])
                for field_name, field_def in properties.items():
                    field = _parse_schema_field(
                        field_name,
                        field_def,
                        object_id,
                        f"{surface_locator}#inputSchema/properties/{field_name}",
                        required,
                        captured_at,
                    )
                    fields.append(field)

            # Parse output schema into DataObject + DataFields
            if output_schema and output_schema.get("type") == "object":
                object_id = stable_id("object", self.server_id, tool_name, "output")
                object_name = f"{_pascal_case(tool_name)}Output"

                object_evidence = Evidence(
                    id=stable_id("evidence", "mcp_object", self.server_id, tool_name, "output"),
                    kind="mcp_descriptor",
                    locator=f"{surface_locator}#outputSchema",
                    excerpt=f"Output schema for MCP tool {tool_name}",
                    confidence=0.85,
                    captured_at=captured_at,
                )

                obj = DataObject(
                    id=object_id,
                    system_id=self.server_id,
                    surface_ids=[surface_id],
                    name=object_name,
                    description=f"Output from MCP tool {tool_name}",
                    evidence=[object_evidence],
                    confidence=0.85,
                    review_status="needs_review",
                )
                objects.append(obj)

                # Parse fields from output schema properties
                properties = output_schema.get("properties") or {}
                required = set(output_schema.get("required") or [])
                for field_name, field_def in properties.items():
                    field = _parse_schema_field(
                        field_name,
                        field_def,
                        object_id,
                        f"{surface_locator}#outputSchema/properties/{field_name}",
                        required,
                        captured_at,
                    )
                    fields.append(field)

        return SystemMap(
            systems=[system],
            access_surfaces=surfaces,
            data_objects=objects,
            data_fields=fields,
        )


def _infer_operation(tool_name: str) -> str:
    """Infer the operation type from the tool name.

    Args:
        tool_name: The name of the MCP tool.

    Returns:
        "write" if the tool name suggests mutation, otherwise "read".
    """
    write_indicators = {"create", "update", "delete", "upsert", "put", "post", "patch", "send", "execute", "run"}
    name_lower = tool_name.lower()
    for indicator in write_indicators:
        if indicator in name_lower:
            return "write"
    return "read"


def _pascal_case(name: str) -> str:
    """Convert a tool name to PascalCase for use as an object name.

    Args:
        name: Tool name like "get_theta" or "list_devices".

    Returns:
        PascalCase version like "GetTheta" or "ListDevices".
    """
    parts = name.replace("-", "_").split("_")
    return "".join(part.capitalize() for part in parts if part)


def _parse_schema_field(
    field_name: str,
    field_def: dict[str, Any],
    object_id: str,
    locator: str,
    required_fields: set[str],
    captured_at: str,
) -> DataField:
    """Parse a JSON Schema field definition into a DataField record.

    Args:
        field_name: Name of the field.
        field_def: JSON Schema definition for the field.
        object_id: ID of the parent DataObject.
        locator: Evidence locator pointing to this field.
        required_fields: Set of required field names.
        captured_at: Timestamp for the evidence record.

    Returns:
        DataField record with provenance.
    """
    field_id = stable_id("field", object_id, field_name)

    # Extract type, handling array and object types
    json_type = field_def.get("type", "string")
    if json_type == "array":
        items = field_def.get("items") or {}
        item_type = items.get("type", "any")
        type_str = f"{item_type}[]"
    elif json_type == "object":
        type_str = "object"
    else:
        type_str = json_type

    # Determine nullability
    nullable = field_name not in required_fields

    # Infer sensitivity from field name patterns
    sensitivity = _infer_sensitivity(field_name)

    evidence = Evidence(
        id=stable_id("evidence", "mcp_field", object_id, field_name),
        kind="mcp_descriptor",
        locator=locator,
        excerpt=field_def.get("description", "")[:200] if field_def.get("description") else None,
        confidence=0.85,
        captured_at=captured_at,
    )

    return DataField(
        id=field_id,
        object_id=object_id,
        name=field_name,
        type=type_str,
        nullable=nullable,
        sensitivity=sensitivity,
        source_path=f"$.{field_name}",
        description=field_def.get("description"),
        evidence=[evidence],
        confidence=0.85,
        review_status="needs_review",
    )


def _infer_sensitivity(field_name: str) -> str:
    """Infer field sensitivity from common naming patterns.

    Args:
        field_name: Name of the field.

    Returns:
        Sensitivity level: "pii", "secret", or "internal" (default).
    """
    name_lower = field_name.lower()

    pii_indicators = {"email", "phone", "address", "ssn", "name", "first_name", "last_name", "full_name", "dob", "birth"}
    secret_indicators = {"password", "secret", "token", "key", "credential", "auth", "private"}

    for indicator in secret_indicators:
        if indicator in name_lower:
            return "secret"
    for indicator in pii_indicators:
        if indicator in name_lower:
            return "pii"

    return "internal"


def discover_mcp_server(
    server_id: str,
    server_name: str,
    command: list[str],
    auth_method: str = "none",
    auth_scopes: list[str] | None = None,
) -> SystemMap:
    """Convenience function to discover an MCP server and return System Map records.

    Args:
        server_id: Stable identifier for the MCP server.
        server_name: Human-readable name for the server.
        command: Command line to spawn the MCP server.
        auth_method: Auth method to record on surfaces (default: "none").
        auth_scopes: Auth scopes to record on surfaces.

    Returns:
        SystemMap with the server, its tools as AccessSurfaces,
        and parsed schemas as DataObjects with DataFields.

    Example:
        >>> sm = discover_mcp_server(
        ...     "saas_a",
        ...     "SaaS A",
        ...     ["npx", "saas-a-mcp"],
        ...     "oauth2",
        ...     ["theta:read", "iota:read"],
        ... )
        >>> len(sm.access_surfaces)  # Number of tools discovered
    """
    adapter = MCPClientAdapter(
        server_id=server_id,
        server_name=server_name,
        command=command,
        auth_method=auth_method,
        auth_scopes=auth_scopes,
    )
    return adapter.discover()
