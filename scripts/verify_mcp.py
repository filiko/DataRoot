"""End-to-end verification for the DataRoot stdio MCP server.

Runs in-process: builds the server, calls its registered ``list_tools`` and
``call_tool`` handlers via the same JSON-RPC entry points an external client
would use, and prints a pass/fail matrix.

Stubs the GitKB-only path (``_get_workspace`` / ``_require_gitkb``) so this
verification works on Windows without WSL. The stubbed workspace uses an
in-memory ``LocalMarkdownStore`` so dispatch can complete; the production
server still requires real ``git-kb`` per the design rules in
``src/dataroot/mcp/server.py``.

Usage::

    PYTHONPATH=src python scripts/verify_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

from mcp import types

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dataroot.kb.local_store import LocalMarkdownStore  # noqa: E402
from dataroot.link import link_workspace  # noqa: E402
from dataroot.mcp import server as mcp_server  # noqa: E402
from dataroot.profile import profile_workspace  # noqa: E402


GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def _fmt(ok: bool, label: str, detail: str = "") -> str:
    mark = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
    return f"  {mark}  {label}" + (f" — {detail}" if detail else "")


def _build_stub_workspace(tmpdir: Path) -> mcp_server._WorkspaceHandle:
    raw = tmpdir / "raw"
    raw.mkdir()
    (raw / "permits.csv").write_text(
        "permit_id,address,description\n"
        "BP-0001,1623 S LAMAR BLVD,Construction project alpha\n"
        "BP-0002,7010 EASY WIND DR UNIT 130,Construction project beta\n",
        encoding="utf-8",
    )
    store = LocalMarkdownStore(tmpdir / "kb")
    profile_workspace(raw, store)
    link_workspace(store)
    return mcp_server._WorkspaceHandle(
        key="austin_permits",
        label="Austin Permits Explorer",
        raw_path=raw,
        store=store,
        record_count=len(store.list()),
    )


def _find_handler(server, request_type_name: str):
    for request_type, fn in server.request_handlers.items():
        if request_type.__name__ == request_type_name:
            return fn
    return None


async def _call_tool(server, name: str, arguments: dict) -> dict:
    handler = _find_handler(server, "CallToolRequest")
    request = types.CallToolRequest(
        method="tools/call",
        params=types.CallToolRequestParams(name=name, arguments=arguments),
    )
    result = await handler(request)
    contents = result.root.content
    return json.loads(contents[0].text)


async def _list_tools(server) -> list[types.Tool]:
    handler = _find_handler(server, "ListToolsRequest")
    request = types.ListToolsRequest(method="tools/list")
    result = await handler(request)
    return list(result.root.tools)


async def main() -> int:
    failures: list[str] = []
    print("DataRoot MCP server — in-process verification")

    # ---- 0. Build server
    server = mcp_server.build_server()
    ok = server.name == mcp_server.SERVER_NAME and server.version == mcp_server.SERVER_VERSION
    print(_fmt(ok, "build_server() returns configured Server", f"name={server.name} version={server.version}"))
    if not ok:
        failures.append("build_server")

    # ---- 1. tools/list returns the eight expected tools
    tools = await _list_tools(server)
    expected = {
        "list_datasets", "summarize_workspace", "kb_search", "kb_list",
        "kb_show", "query_table", "kb_graph", "ask_and_render",
    }
    names = {tool.name for tool in tools}
    ok = names == expected and len(tools) == 8
    print(_fmt(ok, "tools/list returns 8 tools with expected names", ", ".join(sorted(names))))
    if not ok:
        failures.append("tools/list")

    # ---- 2. tools/call list_datasets (no GitKB needed)
    payload = await _call_tool(server, "list_datasets", {})
    ok = "workspaces" in payload and any(w["key"] == "austin_permits" for w in payload["workspaces"])
    print(_fmt(ok, "list_datasets includes austin_permits", f"default={payload.get('default')!r}"))
    if not ok:
        failures.append("list_datasets")

    # ---- 3. tools/call unknown_tool surfaces an error payload (no crash)
    payload = await _call_tool(server, "not_a_real_tool", {})
    ok = payload.get("error", "").startswith("unknown tool") and payload.get("tool") == "not_a_real_tool"
    print(_fmt(ok, "unknown tool returns error payload (no crash)", payload.get("error", "")))
    if not ok:
        failures.append("unknown_tool")

    # ---- 4. tools/call summarize_workspace with a stubbed workspace
    with tempfile.TemporaryDirectory() as tmp:
        workspace = _build_stub_workspace(Path(tmp))
        with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
            payload = await _call_tool(server, "summarize_workspace", {"workspace": "austin_permits"})
        ok = (
            payload.get("workspace") == "austin_permits"
            and payload.get("record_count", 0) > 0
            and "by_type" in payload
            and "attribution" in payload
        )
        print(_fmt(
            ok,
            "summarize_workspace returns counts + attribution",
            f"record_count={payload.get('record_count')} types={list((payload.get('by_type') or {}).keys())}",
        ))
        if not ok:
            failures.append("summarize_workspace")

        # ---- 5. tools/call kb_search clamps caller-supplied limit to SEARCH_LIMIT
        with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
            payload = await _call_tool(server, "kb_search", {"query": "Construction", "limit": 1000})
        ok = (
            payload.get("cap") == mcp_server.SEARCH_LIMIT
            and payload.get("limit") == mcp_server.SEARCH_LIMIT
            and isinstance(payload.get("results"), list)
            and len(payload["results"]) <= mcp_server.SEARCH_LIMIT
        )
        print(_fmt(ok, f"kb_search clamps limit to {mcp_server.SEARCH_LIMIT}", f"hits={len(payload.get('results') or [])}"))
        if not ok:
            failures.append("kb_search")

        # ---- 6. tools/call kb_graph clamps depth to GRAPH_DEPTH_MAX
        with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
            payload = await _call_tool(server, "kb_graph", {"slug": "tables/permits.csv", "depth": 99})
        ok = payload.get("cap") == mcp_server.GRAPH_DEPTH_MAX and payload.get("depth") == mcp_server.GRAPH_DEPTH_MAX
        print(_fmt(ok, f"kb_graph clamps depth to {mcp_server.GRAPH_DEPTH_MAX}", f"nodes={len((payload.get('graph') or {}).get('nodes') or [])}"))
        if not ok:
            failures.append("kb_graph")

    # ---- 7. _require_gitkb raises when git-kb is missing (no silent fallback)
    with mock.patch("dataroot.kb.gitkb_store.GitKBStore.is_available", return_value=False):
        ok = False
        detail = "no exception raised"
        try:
            mcp_server._require_gitkb()
        except RuntimeError as exc:
            ok = "git-kb CLI is not available" in str(exc)
            detail = str(exc).split(".")[0] + "."
    print(_fmt(ok, "_require_gitkb() raises RuntimeError when git-kb is missing", detail))
    if not ok:
        failures.append("require_gitkb_no_gitkb")

    print()
    if failures:
        print(f"{RED}{len(failures)} check(s) failed: {failures}{RESET}")
        return 1
    print(f"{GREEN}All MCP verification checks passed.{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
