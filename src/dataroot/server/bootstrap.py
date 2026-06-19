"""Runtime bootstrap for the hosted DataRoot Ask API."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dataroot.config import DataRootConfig, write_config
from dataroot.kb.gitkb_store import GitKBStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace


def bootstrap_gitkb_runtime(root: Path | None = None) -> None:
    """Initialize and warm the local GitKB store when the runtime uses GitKB."""

    if os.environ.get("DATAROOT_SKIP_GITKB_BOOTSTRAP") == "1":
        return
    if not _server_wants_gitkb():
        return
    if not GitKBStore.is_available():
        raise RuntimeError("DATAROOT_SERVER_KB_BACKEND=gitkb but git-kb is not available.")

    root = (root or Path.cwd()).resolve()
    print("DataRoot bootstrap: configuring GitKB author.", file=sys.stderr, flush=True)
    _ensure_author_config()
    write_config(DataRootConfig(root=root, kb_backend="gitkb"))
    store = GitKBStore(root)
    print("DataRoot bootstrap: initializing GitKB store.", file=sys.stderr, flush=True)
    store.init()

    print("DataRoot bootstrap: listing GitKB records.", file=sys.stderr, flush=True)
    records = store.list()
    if not records:
        print("DataRoot bootstrap: profiling ExampleData into GitKB.", file=sys.stderr, flush=True)
        profile_workspace(root / "ExampleData", store)
        records = store.list()
    if not any(record.doc_type == "relationship" for record in records):
        print("DataRoot bootstrap: linking GitKB workspace.", file=sys.stderr, flush=True)
        link_workspace(store)

    if os.environ.get("DATAROOT_BOOTSTRAP_CODE_INDEX", "1") == "1":
        print("DataRoot bootstrap: indexing code symbols.", file=sys.stderr, flush=True)
        _run(["git-kb", "code", "index", "--prune", "--branch", "main", "."], root)
    print("DataRoot bootstrap: complete.", file=sys.stderr, flush=True)


def _server_wants_gitkb() -> bool:
    backend = os.environ.get("DATAROOT_SERVER_KB_BACKEND")
    if backend:
        return backend.lower() == "gitkb"
    return bool(os.environ.get("RAILWAY_ENVIRONMENT"))


def _run(command: list[str], cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: "
            + " ".join(command)
            + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if result.stdout:
        print(result.stdout.strip(), file=sys.stderr)
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)


def _ensure_author_config() -> None:
    name = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GITKB_AUTHOR_NAME") or "DataRoot"
    email = os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GITKB_AUTHOR_EMAIL") or "dataroot@example.local"
    subprocess.run(["git", "config", "--global", "user.name", name], text=True, check=False)
    subprocess.run(["git", "config", "--global", "user.email", email], text=True, check=False)


def main() -> int:
    try:
        bootstrap_gitkb_runtime()
    except Exception as exc:
        print(f"DataRoot bootstrap failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
