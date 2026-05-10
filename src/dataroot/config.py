"""Configuration helpers for DataRoot."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DataRootConfig:
    """Runtime configuration loaded from env vars and .dataroot/config.toml."""

    root: Path
    kb_backend: str = "gitkb"

    @property
    def dataroot_dir(self) -> Path:
        return self.root / ".dataroot"

    @property
    def local_kb_dir(self) -> Path:
        """Legacy unit-test store path; not used by the application CLI."""
        return self.dataroot_dir / "kb_docs"

    @property
    def config_path(self) -> Path:
        return self.dataroot_dir / "config.toml"


def load_config(root: Path | None = None) -> DataRootConfig:
    """Load config using env override first, then .dataroot/config.toml."""

    root = (root or Path.cwd()).resolve()
    _load_env_file(root)
    backend = os.environ.get("DATAROOT_KB_BACKEND")
    config_path = root / ".dataroot" / "config.toml"

    if not backend and config_path.exists():
        backend = _read_backend_from_toml(config_path)

    return DataRootConfig(root=root, kb_backend=(backend or "gitkb").lower())


def write_config(config: DataRootConfig) -> None:
    config.dataroot_dir.mkdir(parents=True, exist_ok=True)
    config.config_path.write_text(
        f'kb_backend = "{config.kb_backend}"\n',
        encoding="utf-8",
    )


def _read_backend_from_toml(path: Path) -> str | None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "kb_backend":
            return value.strip().strip('"').strip("'")
    return None


def _load_env_file(root: Path) -> None:
    path = root / ".env"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value
