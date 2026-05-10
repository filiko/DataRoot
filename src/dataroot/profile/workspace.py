"""Workspace profiler."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dataroot.kb.base import DocumentRecord

from .parsers import parse_file
from .slug import slugify

IGNORED_DIRS = {".git", ".kb", ".dataroot", ".opencode", "__pycache__", "node_modules"}


@dataclass
class ProfileSummary:
    root: Path
    files_seen: int
    records_written: int
    skipped_files: int = 0


def profile_workspace(path: Path, store) -> ProfileSummary:
    root = path.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Workspace path does not exist: {path}")
    store.init()

    records = [_workspace_record(root)]
    files_seen = 0
    skipped = 0

    for file_path in _iter_files(root):
        files_seen += 1
        try:
            records.extend(parse_file(root, file_path).records)
        except Exception as exc:
            skipped += 1
            records.append(_error_record(root, file_path, exc))

    for record in records:
        store.write(record)

    store.commit(f"Profile workspace {root.name}")
    return ProfileSummary(root=root, files_seen=files_seen, records_written=len(records), skipped_files=skipped)


def _iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        yield path


def _workspace_record(root: Path) -> DocumentRecord:
    return DocumentRecord(
        doc_type="workspace",
        slug=f"workspaces/{slugify(root.name)}",
        title=root.name,
        frontmatter={"path": str(root), "workspace_name": root.name},
        body=f"# {root.name}\n\nProfiled workspace root: `{root}`",
    )


def _error_record(root: Path, path: Path, exc: Exception) -> DocumentRecord:
    rel = path.resolve().relative_to(root).as_posix()
    return DocumentRecord(
        doc_type="source_file",
        slug=f"source_files/{slugify(rel)}",
        title=path.name,
        frontmatter={"path": rel, "file_type": "error", "error": str(exc)},
        body=f"# {path.name}\n\nFailed to parse `{rel}`: `{exc}`",
    )
