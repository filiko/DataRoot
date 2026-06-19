"""Connector registry loading for the System Map acquisition layer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, model_validator

from dataroot.systemmap.ids import stable_id
from dataroot.systemmap.models import AuthConfig, EnterpriseSystem, Evidence, StrictBaseModel, SystemKind, SystemMap

SECRET_KEYS = {
    "api_key",
    "apikey",
    "auth_token",
    "client_secret",
    "dsn",
    "password",
    "secret",
    "token",
}


class ConnectorRegistrySystem(StrictBaseModel):
    id: str
    name: str
    kind: SystemKind
    discover: dict[str, Any] = Field(default_factory=dict)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    vendor: str | None = None
    environment: str | None = None
    owner: str | None = None
    description: str | None = None
    enabled: bool = True


class ConnectorRegistry(StrictBaseModel):
    systems: list[ConnectorRegistrySystem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_registry(self) -> "ConnectorRegistry":
        seen: set[str] = set()
        for system in self.systems:
            if system.id in seen:
                raise ValueError(f"duplicate connector system id: {system.id}")
            seen.add(system.id)
            _reject_inline_secrets(system.model_dump(mode="json"), path=f"systems.{system.id}")
        return self


def connector_registry_path(root_or_path: Path) -> Path:
    path = root_or_path.resolve()
    if path.is_dir():
        return path / ".dataroot" / "connectors.yaml"
    return path


def load_connector_registry(root_or_path: Path | str) -> ConnectorRegistry:
    path = connector_registry_path(Path(root_or_path))
    if not path.exists():
        raise FileNotFoundError(f"connector registry not found: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"connector registry must be a mapping: {path}")
    return ConnectorRegistry.model_validate(payload)


def registry_to_system_map(registry: ConnectorRegistry) -> SystemMap:
    systems: list[EnterpriseSystem] = []
    for entry in registry.systems:
        if not entry.enabled:
            continue
        evidence = Evidence(
            id=stable_id("evidence", "connector_registry", entry.id),
            kind="manual",
            locator=f".dataroot/connectors.yaml#systems/{entry.id}",
            excerpt=f"Connector registry entry for {entry.name}",
            confidence=0.75,
        )
        systems.append(
            EnterpriseSystem(
                id=entry.id,
                name=entry.name,
                vendor=entry.vendor,
                kind=entry.kind,
                environment=entry.environment,  # type: ignore[arg-type]
                owner=entry.owner,
                description=entry.description,
                evidence=[evidence],
                confidence=0.75,
                review_status="needs_review",
            )
        )
    return SystemMap(systems=systems)


def _reject_inline_secrets(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            child_path = f"{path}.{key}"
            if normalized in SECRET_KEYS:
                raise ValueError(f"inline secret is not allowed at {child_path}; reference an *_env key instead")
            _reject_inline_secrets(child, path=child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_inline_secrets(child, path=f"{path}[{index}]")
