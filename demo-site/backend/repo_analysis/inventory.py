from __future__ import annotations

import hashlib
import json
from fnmatch import fnmatch
from pathlib import Path

from .models import InventoryFile, RepositoryInventory


EXCLUDED_DIRS = {
    ".git",
    ".next",
    ".turbo",
    ".cache",
    ".dfdmaker",
    ".venv",
    "__pycache__",
    "archive",
    "artifacts",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}

LANG_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".sql": "sql",
    ".json": "json",
    ".md": "markdown",
    ".toml": "toml",
    ".yml": "yaml",
    ".yaml": "yaml",
}


def stable_file_id(path: str) -> str:
    normalized = path.replace("\\", "/").lower()
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]
    return f"file:{digest}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _kind_for_path(path: Path) -> str:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in {".py", ".ts", ".tsx", ".js", ".jsx"}:
        return "source"
    if suffix == ".sql" or "migration" in path.as_posix().lower():
        return "migration"
    if suffix in {".md", ".rst"}:
        return "documentation"
    if name in {"package.json", "requirements.txt", "pyproject.toml", "docker-compose.yml", "docker-compose.yaml"}:
        return "manifest"
    if suffix in {".json", ".toml", ".yml", ".yaml"}:
        return "config"
    return "other"


def _detect_stack(repo_root: Path, files: list[InventoryFile]) -> dict[str, list[str]]:
    languages = sorted({item.language for item in files if item.included and item.language})
    frameworks: set[str] = set()
    package_managers: set[str] = set()

    requirements = repo_root / "backend" / "requirements.txt"
    if not requirements.exists():
        requirements = repo_root / "requirements.txt"
    if requirements.exists():
        package_managers.add("pip")
        text = requirements.read_text(encoding="utf-8", errors="ignore").lower()
        if "fastapi" in text:
            frameworks.add("fastapi")
        if "django" in text:
            frameworks.add("django")
        if "flask" in text:
            frameworks.add("flask")

    package_json = repo_root / "frontend" / "package.json"
    if not package_json.exists():
        package_json = repo_root / "package.json"
    if package_json.exists():
        package_managers.add("npm")
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
            deps = {
                **package.get("dependencies", {}),
                **package.get("devDependencies", {}),
            }
            if "react" in deps:
                frameworks.add("react")
            if "vite" in deps:
                frameworks.add("vite")
            if "express" in deps:
                frameworks.add("express")
        except json.JSONDecodeError:
            pass

    return {
        "languages": languages,
        "frameworks": sorted(frameworks),
        "package_managers": sorted(package_managers),
    }


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    normalized = rel_path.replace("\\", "/")
    return any(fnmatch(normalized, pattern.replace("\\", "/")) for pattern in patterns)


def build_inventory(
    repo_root: Path,
    max_file_size: int = 2_000_000,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> RepositoryInventory:
    repo_root = repo_root.resolve()
    files: list[InventoryFile] = []
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or []

    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(repo_root).as_posix()
        parts = set(path.relative_to(repo_root).parts[:-1])
        if parts.intersection(EXCLUDED_DIRS):
            continue
        if include_patterns and not _matches_any(rel_path, include_patterns):
            continue
        if exclude_patterns and _matches_any(rel_path, exclude_patterns):
            continue

        size = path.stat().st_size
        included = size <= max_file_size
        skip_reason = None if included else "file_too_large"
        language = LANG_BY_SUFFIX.get(path.suffix.lower())
        files.append(InventoryFile(
            id=stable_file_id(rel_path),
            path=rel_path,
            kind=_kind_for_path(path),
            language=language,
            size_bytes=size,
            sha256=_sha256(path) if included else None,
            included=included,
            skip_reason=skip_reason,
        ))

    inventory = RepositoryInventory(repo_root=str(repo_root), files=files)
    inventory.detected_stack = _detect_stack(repo_root, files)
    return inventory
