from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from dataroot.systemmap import (
    SystemMap,
    generic_saas_abc_map,
    load_connector_registry,
    registry_to_system_map,
    stable_id,
)


def test_generic_saas_abc_fixture_validates_and_is_nexus_free() -> None:
    system_map = generic_saas_abc_map()
    payload = system_map.to_json_dict()

    assert {system.id for system in system_map.systems} == {"saas_a", "saas_b", "saas_c"}
    assert {surface.kind for surface in system_map.access_surfaces} >= {"mcp_tool", "openapi_endpoint"}
    assert system_map.business_rules[0].category == "validation"
    assert system_map.connectors[0].contract == "Order.device_id -> Device.device_id"
    assert "nexus" not in json.dumps(payload).lower()


def test_system_map_round_trips_through_json_dict() -> None:
    system_map = generic_saas_abc_map()
    round_tripped = SystemMap.from_json_dict(system_map.to_json_dict())

    assert round_tripped == system_map


def test_every_canonical_record_carries_evidence_confidence_and_review_status() -> None:
    system_map = generic_saas_abc_map()
    evidence_backed_groups = [
        system_map.systems,
        system_map.access_surfaces,
        system_map.data_objects,
        system_map.data_fields,
        system_map.business_rules,
        system_map.connectors,
    ]

    for group in evidence_backed_groups:
        for record in group:
            assert record.evidence
            assert 0.0 <= record.confidence <= 1.0
            assert record.review_status in {"accepted", "needs_review", "rejected"}

    for flow in system_map.data_flows:
        assert flow.evidence
        assert 0.0 <= flow.confidence <= 1.0


def test_system_map_rejects_unknown_references() -> None:
    payload = generic_saas_abc_map().to_json_dict()
    payload["data_fields"][0]["object_id"] = "object_missing"

    with pytest.raises(ValidationError, match="object_missing"):
        SystemMap.model_validate(payload)


def test_stable_id_is_deterministic_and_sanitized() -> None:
    first = stable_id("surface", "SaaS A", "GET /theta readings")
    second = stable_id("surface", "SaaS A", "GET /theta readings")

    assert first == second
    assert first.startswith("surface_saas_a_get_theta_readings_")
    assert "/" not in first
    assert " " not in first


def test_connector_registry_loads_saas_abc(tmp_path: Path) -> None:
    registry_path = tmp_path / ".dataroot" / "connectors.yaml"
    registry_path.parent.mkdir()
    registry_path.write_text(
        """
systems:
  - id: saas_a
    name: SaaS A
    kind: mcp_server
    discover:
      transport: stdio
      command: ["npx", "saas-a-mcp"]
    auth:
      method: oauth2
      scopes: ["theta:read", "iota:read"]
  - id: saas_b
    name: SaaS B
    kind: saas
    discover:
      openapi_url: https://api.saas-b.example/openapi.json
    auth:
      method: bearer
  - id: saas_c
    name: SaaS C
    kind: saas
    discover:
      openapi_url: https://api.saas-c.example/openapi.json
    auth:
      method: bearer
""",
        encoding="utf-8",
    )

    registry = load_connector_registry(tmp_path)
    system_map = registry_to_system_map(registry)

    assert [system.id for system in registry.systems] == ["saas_a", "saas_b", "saas_c"]
    assert {system.kind for system in system_map.systems} == {"mcp_server", "saas"}


def test_connector_registry_rejects_duplicates_and_inline_secrets(tmp_path: Path) -> None:
    registry_path = tmp_path / ".dataroot" / "connectors.yaml"
    registry_path.parent.mkdir()
    registry_path.write_text(
        """
systems:
  - id: saas_a
    name: SaaS A
    kind: mcp_server
    auth: { method: oauth2 }
  - id: saas_a
    name: SaaS A Duplicate
    kind: saas
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="duplicate connector system id"):
        load_connector_registry(tmp_path)

    registry_path.write_text(
        """
systems:
  - id: saas_b
    name: SaaS B
    kind: saas
    discover:
      openapi_url: https://api.saas-b.example/openapi.json
      token: not-allowed-inline
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="inline secret"):
        load_connector_registry(tmp_path)
