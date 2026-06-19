"""DataRoot stdio MCP server.

Wraps the existing ``ToolExecutor`` (``src/dataroot/agent/tools.py``) with a
small, bounded tool set for discovery, bounded query, summaries, and a one-shot
``ask`` tool that returns a cited answer plus persisted provenance records.

Design rules:

- **Real GitKB only.** This server refuses to start if ``git-kb`` is not on
  ``PATH``. There is no LocalMarkdownStore fallback.
- **Hard upper bounds on every tool.** A caller may ask for more, but the
  server clamps to the cap silently and reports the cap in the response so the
  caller sees that truncation occurred.
- **No persistent state of its own.** All state lives in GitKB. The server
  caches a per-workspace ``GitKBStore`` handle for the process lifetime; that
  is it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

SERVER_NAME = "dataroot-texas"
SERVER_VERSION = "0.1.0"

SEARCH_LIMIT = 50
LIST_LIMIT = 100
TABLE_LIMIT = 200
GRAPH_DEPTH_MAX = 3

DEFAULT_WORKSPACE = "austin_permits"


@dataclass
class _WorkspaceHandle:
    key: str
    label: str
    raw_path: Path
    store: Any
    record_count: int
    cached: bool = True
    backend: str = "gitkb"


def _project_root() -> Path:
    return Path(os.environ.get("DATAROOT_ROOT", Path.cwd())).resolve()


def _require_gitkb() -> None:
    from dataroot.kb.gitkb_store import GitKBStore

    if not GitKBStore.is_available():
        raise RuntimeError(
            "git-kb CLI is not available on PATH. The DataRoot MCP server requires "
            "the real GitKB backend (https://github.com/gitkb/gitkb-releases). "
            "On Windows install via WSL per the project README."
        )


_workspace_cache: dict[str, _WorkspaceHandle] = {}


def _resolve_workspace_key(name: str | None) -> str:
    from dataroot.server.app import COMPANIES, COMPANY_ALIASES

    if not name:
        return DEFAULT_WORKSPACE
    candidate = name.strip().lower().replace(" ", "").replace("-", "_")
    if candidate in COMPANIES:
        return candidate
    if candidate in COMPANY_ALIASES:
        return COMPANY_ALIASES[candidate]
    raise ValueError(
        f"unknown workspace {name!r}. Known: {sorted(COMPANIES.keys())}"
    )


def _get_workspace(name: str | None) -> _WorkspaceHandle:
    from dataroot.kb.gitkb_store import GitKBStore
    from dataroot.server.app import COMPANIES
    from dataroot.server.bootstrap import bootstrap_gitkb_runtime

    key = _resolve_workspace_key(name)
    if key in _workspace_cache:
        return _workspace_cache[key]

    _require_gitkb()
    project_root = _project_root()
    company = COMPANIES[key]
    raw_path = (project_root / company.raw_path).resolve()

    bootstrap_gitkb_runtime(project_root)
    store = GitKBStore(project_root)
    records = store.list()
    handle = _WorkspaceHandle(
        key=key,
        label=company.label,
        raw_path=raw_path,
        store=store,
        record_count=len(records),
    )
    _workspace_cache[key] = handle
    return handle


def _bound(value: Any, default: int, cap: int) -> int:
    if value is None:
        return min(default, cap)
    try:
        return min(max(int(value), 1), cap)
    except (TypeError, ValueError):
        return min(default, cap)


def _list_workspaces() -> list[dict[str, str]]:
    from dataroot.server.app import COMPANIES

    return [
        {"key": cfg.key, "label": cfg.label, "raw_path": str(cfg.raw_path)}
        for cfg in COMPANIES.values()
    ]


def _summarize(workspace: _WorkspaceHandle) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for record in workspace.store.list():
        counts[record.doc_type] = counts.get(record.doc_type, 0) + 1
    return {
        "workspace": workspace.key,
        "label": workspace.label,
        "raw_path": str(workspace.raw_path),
        "record_count": sum(counts.values()),
        "by_type": counts,
        "attribution": "City of Austin Open Data Terms - https://data.austintexas.gov/stories/s/ranj-cccq",
    }


def _ask(workspace: _WorkspaceHandle, question: str, *, use_agent: bool) -> dict[str, Any]:
    from dataroot.query import _extract_provenance, persist_answer_artifacts
    from dataroot.server.app import COMPANIES, CompanyWorkspace, _answer_live_ask, _strip_provenance

    company = COMPANIES[workspace.key]
    app_workspace = CompanyWorkspace(
        config=company,
        store=workspace.store,
        record_count=workspace.record_count,
        cached=workspace.cached,
        backend=workspace.backend,
    )
    answer, trace, answer_source = _answer_live_ask(company, app_workspace, question, use_agent=use_agent)
    if not _valid_trace_payload(trace):
        trace = _extract_provenance(answer)
    artifacts = persist_answer_artifacts(workspace.store, question, answer)
    return {
        "workspace": workspace.key,
        "question": question,
        "answer": _strip_provenance(answer),
        "inquiry": artifacts["inquiry"],
        "provenance_trace": artifacts["provenance_trace"],
        "node_count": len(trace.get("nodes", [])) if isinstance(trace, dict) else 0,
        "edge_count": len(trace.get("edges", [])) if isinstance(trace, dict) else 0,
        "stages": list(trace.get("stages", [])) if isinstance(trace, dict) else [],
        "trace": trace if isinstance(trace, dict) else {},
        "answer_source": answer_source,
        "use_agent": use_agent,
    }


def _valid_trace_payload(trace: Any) -> bool:
    return (
        isinstance(trace, dict)
        and "raw" not in trace
        and isinstance(trace.get("nodes"), list)
        and isinstance(trace.get("edges"), list)
        and isinstance(trace.get("stages"), list)
    )


def _tool_descriptors() -> list[types.Tool]:
    workspace_arg = {
        "type": "string",
        "description": f"Workspace key (default {DEFAULT_WORKSPACE!r}). Use list_datasets to discover.",
    }
    return [
        types.Tool(
            name="list_datasets",
            description="Discovery: list every workspace registered in DataRoot, with raw-data paths.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        types.Tool(
            name="summarize_workspace",
            description="Summary: counts of KB records by document type for a workspace.",
            inputSchema={
                "type": "object",
                "properties": {"workspace": workspace_arg},
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="kb_search",
            description=f"Bounded full-text search over KB documents. Hard cap: {SEARCH_LIMIT} results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "query": {"type": "string", "description": "Search query."},
                    "limit": {"type": "integer", "description": f"Max results (capped at {SEARCH_LIMIT})."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="kb_list",
            description=f"Bounded enumeration of KB documents by type or path prefix. Hard cap: {LIST_LIMIT} results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "type": {"type": "string", "description": "Document type filter (e.g. 'table', 'row_group')."},
                    "path": {"type": "string", "description": "Slug path prefix filter."},
                    "limit": {"type": "integer", "description": f"Max results (capped at {LIST_LIMIT})."},
                },
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="kb_show",
            description="Fetch a single KB record (frontmatter + body) by slug.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "slug": {"type": "string", "description": "Document slug."},
                },
                "required": ["slug"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="query_table",
            description=f"Bounded row query against a profiled table. Hard cap: {TABLE_LIMIT} rows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "table_slug": {"type": "string", "description": "Slug of the table record."},
                    "filters": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of {column, op, value} filter clauses.",
                    },
                    "limit": {"type": "integer", "description": f"Max rows (capped at {TABLE_LIMIT})."},
                },
                "required": ["table_slug"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="kb_graph",
            description=f"Connected subgraph of a KB record. Hard cap: depth {GRAPH_DEPTH_MAX}.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "slug": {"type": "string", "description": "Document slug to traverse from."},
                    "direction": {
                        "type": "string",
                        "enum": ["both", "in", "out"],
                        "description": "Edge direction (default 'both').",
                    },
                    "depth": {"type": "integer", "description": f"Traversal depth (capped at {GRAPH_DEPTH_MAX})."},
                },
                "required": ["slug"],
                "additionalProperties": False,
            },
        ),
        types.Tool(
            name="ask",
            description="Answer a free-form question against a workspace and return a cited answer plus provenance records.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace": workspace_arg,
                    "question": {"type": "string", "description": "Free-form question about the workspace."},
                    "use_agent": {"type": "boolean", "description": "Use the LLM tool-calling path when model credentials are configured."},
                },
                "required": ["question"],
                "additionalProperties": False,
            },
        ),
    ]


_KNOWN_TOOLS = frozenset(
    {
        "list_datasets",
        "summarize_workspace",
        "kb_search",
        "kb_list",
        "kb_show",
        "query_table",
        "kb_graph",
        "ask",
    }
)


def _dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    from dataroot.agent.tools import ToolExecutor

    if name not in _KNOWN_TOOLS:
        raise ValueError(f"unknown tool: {name}")

    if name == "list_datasets":
        return {"workspaces": _list_workspaces(), "default": DEFAULT_WORKSPACE}

    workspace = _get_workspace(args.get("workspace"))

    if name == "summarize_workspace":
        return _summarize(workspace)

    executor = ToolExecutor(workspace.store)

    if name == "kb_search":
        limit = _bound(args.get("limit"), default=10, cap=SEARCH_LIMIT)
        results = executor("kb_search", {"query": args["query"], "limit": limit})
        return {"workspace": workspace.key, "limit": limit, "cap": SEARCH_LIMIT, "results": results}

    if name == "kb_list":
        limit = _bound(args.get("limit"), default=50, cap=LIST_LIMIT)
        records = executor("kb_list", {"type": args.get("type"), "path": args.get("path")})
        truncated = len(records) > limit
        return {
            "workspace": workspace.key,
            "limit": limit,
            "cap": LIST_LIMIT,
            "truncated": truncated,
            "records": records[:limit],
        }

    if name == "kb_show":
        return {"workspace": workspace.key, "record": executor("kb_show", {"slug": args["slug"]})}

    if name == "query_table":
        limit = _bound(args.get("limit"), default=50, cap=TABLE_LIMIT)
        rows = executor(
            "query_table",
            {
                "table_slug": args["table_slug"],
                "filters": args.get("filters") or [],
                "limit": limit,
            },
        )
        return {"workspace": workspace.key, "limit": limit, "cap": TABLE_LIMIT, "rows": rows}

    if name == "kb_graph":
        depth = _bound(args.get("depth"), default=2, cap=GRAPH_DEPTH_MAX)
        graph = executor(
            "kb_graph",
            {
                "slug": args["slug"],
                "direction": args.get("direction", "both"),
                "depth": depth,
            },
        )
        return {"workspace": workspace.key, "depth": depth, "cap": GRAPH_DEPTH_MAX, "graph": graph}

    if name == "ask":
        return _ask(
            workspace,
            question=args["question"],
            use_agent=bool(args.get("use_agent")),
        )

    raise ValueError(f"unknown tool: {name}")


def build_server() -> Server:
    server: Server = Server(SERVER_NAME, version=SERVER_VERSION)

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return _tool_descriptors()

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[types.TextContent]:
        try:
            payload = _dispatch(name, arguments or {})
            text = json.dumps(payload, indent=2, default=str)
        except Exception as exc:  # surface as an MCP error response, not a crash
            text = json.dumps({"error": str(exc), "tool": name}, indent=2)
        return [types.TextContent(type="text", text=text)]

    return server


async def _run_async() -> None:
    _require_gitkb()
    server = build_server()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_stdio() -> int:
    try:
        asyncio.run(_run_async())
    except RuntimeError as exc:
        print(f"DataRoot MCP server failed to start: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_stdio())
