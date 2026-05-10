"""DataRoot compile timer — runs the full GitKB pipeline and reports per-datastore metrics.

Runs the full pipeline in a fresh temp git repo on the native Linux filesystem so that:
  - timings are always clean (no stale committed state from previous runs)
  - reset is reliable (no NTFS lock issues)
  - the real project .kb/ is not touched
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="compile_timer",
        description="Run the DataRoot GitKB compile pipeline and report timing per datastore.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="ExampleData",
        help="Root path containing datastores (default: ExampleData)",
    )
    parser.add_argument(
        "--skip-code-index",
        action="store_true",
        help="Skip git-kb code index step",
    )
    args = parser.parse_args(argv)

    try:
        from dataroot.kb.gitkb_store import GitKBStore
        from dataroot.link import link_workspace
        from dataroot.profile.parsers import parse_file
        from dataroot.profile.workspace import IGNORED_DIRS, _error_record, _workspace_record
    except ImportError as exc:
        print(f"error: could not import dataroot — run with PYTHONPATH=src: {exc}", file=sys.stderr)
        return 1

    project_root = Path.cwd().resolve()
    data_path = (project_root / args.path).resolve()

    if not data_path.exists():
        print(f"error: path does not exist: {data_path}", file=sys.stderr)
        return 1

    if not GitKBStore.is_available():
        print(
            "error: git-kb is not available. Install the real GitKB CLI from\n"
            "  https://github.com/gitkb/gitkb-releases\n"
            "On Windows use WSL:\n"
            '  curl -fsSL https://get.gitkb.com/install.sh | INSTALL_DIR="$HOME/.local/bin" bash',
            file=sys.stderr,
        )
        return 1

    # Use a temp git repo on Linux's native filesystem for a clean, isolated store.
    # This avoids NTFS lock issues and ensures no stale committed state from prior runs.
    tmp_dir = Path(tempfile.mkdtemp(prefix="dataroot_kb_timer_"))
    try:
        return _run_timer(
            tmp_dir=tmp_dir,
            data_path=data_path,
            args=args,
            imports={
                "GitKBStore": GitKBStore,
                "link_workspace": link_workspace,
                "parse_file": parse_file,
                "IGNORED_DIRS": IGNORED_DIRS,
                "_error_record": _error_record,
                "_workspace_record": _workspace_record,
            },
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_timer(*, tmp_dir: Path, data_path: Path, args, imports: dict) -> int:
    GitKBStore = imports["GitKBStore"]
    link_workspace = imports["link_workspace"]
    parse_file = imports["parse_file"]
    IGNORED_DIRS = imports["IGNORED_DIRS"]
    _error_record = imports["_error_record"]
    _workspace_record = imports["_workspace_record"]

    # Bootstrap a fresh git repo + git-kb in the temp dir
    name = os.environ.get("GIT_AUTHOR_NAME") or os.environ.get("GITKB_AUTHOR_NAME") or "DataRoot"
    email = os.environ.get("GIT_AUTHOR_EMAIL") or os.environ.get("GITKB_AUTHOR_EMAIL") or "dataroot@example.local"

    subprocess.run(["git", "init", str(tmp_dir)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(tmp_dir), "config", "user.name", name], capture_output=True, check=False)
    subprocess.run(["git", "-C", str(tmp_dir), "config", "user.email", email], capture_output=True, check=False)

    store = GitKBStore(tmp_dir)
    store.init()

    # Discover company-level datastores as direct subdirectories
    datastores = sorted(p for p in data_path.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not datastores:
        datastores = [data_path]

    _print_header()

    total_files = 0
    total_records = 0
    total_skipped = 0
    total_time = 0.0
    ds_rows: list[tuple[str, int, int, int, float]] = []

    for ds in datastores:
        t0 = time.perf_counter()

        # Use data_path (ExampleData) as slug root so each company's slugs include its
        # directory name (e.g. companya_agritrait/raw/...) and don't collide in the shared store.
        records = [_workspace_record(ds)]
        files_seen = 0
        skipped = 0

        for file_path in _iter_files(ds, IGNORED_DIRS):
            files_seen += 1
            try:
                records.extend(parse_file(data_path, file_path).records)
            except Exception as exc:
                skipped += 1
                records.append(_error_record(data_path, file_path, exc))

        for record in records:
            store.write(record)

        elapsed = time.perf_counter() - t0
        ds_rows.append((ds.name, files_seen, len(records), skipped, elapsed))
        total_files += files_seen
        total_records += len(records)
        total_skipped += skipped
        total_time += elapsed

    # Single commit for all datastores
    t_commit = time.perf_counter()
    store.commit("Profile all datastores")
    commit_elapsed = time.perf_counter() - t_commit
    total_time += commit_elapsed

    for name_ds, files, records, skipped, elapsed in ds_rows:
        print(f"{name_ds:<28} {files:>5}   {records:>7}   {skipped:>7}   {elapsed:>7.2f}s")
    print(f"{'  └─ git-kb commit':<28} {'—':>5}   {'—':>7}   {'—':>7}   {commit_elapsed:>7.2f}s")

    print("─" * 68)

    t0 = time.perf_counter()
    link_summary = link_workspace(store)
    link_elapsed = time.perf_counter() - t0
    total_time += link_elapsed
    print(f"{'link_workspace':<28} {'—':>5}   {'—':>7}   {'—':>7}   {link_elapsed:>7.2f}s")
    print(
        f"  {link_summary.relationship_docs} relationship docs, "
        f"{link_summary.documents_updated} docs updated, "
        f"{link_summary.links_added} links considered"
    )

    if not args.skip_code_index:
        t0 = time.perf_counter()
        result = subprocess.run(
            ["git-kb", "code", "index", "--prune", "--branch", "main", "."],
            cwd=tmp_dir,
            text=True,
            capture_output=True,
            check=False,
        )
        code_elapsed = time.perf_counter() - t0
        total_time += code_elapsed
        if result.returncode != 0:
            print(f"  warning: code index exited {result.returncode}: {result.stderr.strip()}", file=sys.stderr)
        print(f"{'code_index':<28} {'—':>5}   {'—':>7}   {'—':>7}   {code_elapsed:>7.2f}s")

    _print_footer(total_files, total_records, total_skipped, total_time)
    return 0


def _iter_files(root: Path, ignored_dirs: set[str]):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in ignored_dirs for part in path.parts):
            continue
        yield path


def _print_header() -> None:
    print("\nDataRoot Compile Timer")
    print(f"  binary: git-kb {_gitkb_version()}")
    print(f"  source: https://github.com/gitkb/gitkb-releases")
    print("═" * 68)
    print(f"{'Datastore':<28} {'Files':>5}   {'Records':>7}   {'Skipped':>7}   {'Time':>8}")
    print("─" * 68)


def _print_footer(files: int, records: int, skipped: int, elapsed: float) -> None:
    print("═" * 68)
    print(f"{'TOTAL':<28} {files:>5}   {records:>7}   {skipped:>7}   {elapsed:>7.2f}s\n")


def _gitkb_version() -> str:
    result = subprocess.run(["git-kb", "--version"], capture_output=True, text=True, check=False)
    return result.stdout.strip() or result.stderr.strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
