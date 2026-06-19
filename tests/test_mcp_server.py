from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.mcp import server as mcp_server


def _git_kb_available() -> bool:
    if not shutil.which("git") or not shutil.which("git-kb"):
        return False
    try:
        result = subprocess.run(
            ["git", "kb", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


class MCPToolDescriptorTests(unittest.TestCase):
    def test_eight_tools_registered_with_expected_names(self) -> None:
        tools = mcp_server._tool_descriptors()
        self.assertEqual(len(tools), 8)
        names = {tool.name for tool in tools}
        self.assertEqual(
            names,
            {
                "list_datasets",
                "summarize_workspace",
                "kb_search",
                "kb_list",
                "kb_show",
                "query_table",
                "kb_graph",
                "ask",
            },
        )

    def test_every_tool_has_object_input_schema(self) -> None:
        for tool in mcp_server._tool_descriptors():
            self.assertEqual(tool.inputSchema.get("type"), "object", tool.name)
            self.assertIn("properties", tool.inputSchema, tool.name)


class ListDatasetsTests(unittest.TestCase):
    def test_includes_austin_permits_workspace(self) -> None:
        result = mcp_server._dispatch("list_datasets", {})
        keys = {workspace["key"] for workspace in result["workspaces"]}
        self.assertIn("austin_permits", keys)
        self.assertEqual(result["default"], mcp_server.DEFAULT_WORKSPACE)


class WorkspaceAliasTests(unittest.TestCase):
    def test_live_ask_aliases_resolve_to_registered_workspaces(self) -> None:
        self.assertEqual(mcp_server._resolve_workspace_key("austin"), "austin_permits")
        self.assertEqual(mcp_server._resolve_workspace_key("cropprotectorai"), "company_a")
        self.assertEqual(mcp_server._resolve_workspace_key("bioreactorai"), "company_b")


class AskTests(unittest.TestCase):
    def test_uses_live_ask_path_extracts_trace_and_returns_records(self) -> None:
        question = "What specific genes make Solara-14 powdery mildew resistant?"
        trace = {
            "question": question,
            "nodes": [
                {"id": "n1", "slug": "row_groups/demo/1", "label": "A-GEN-PMR3", "stage": "marker_gene"},
                {"id": "n2", "slug": "row_groups/demo/2", "label": "A-GEN-PMR4", "stage": "marker_gene"},
            ],
            "edges": [{"from": "n1", "to": "n2", "label": "supports"}],
            "stages": ["query", "marker_gene", "answer"],
        }
        answer = "\n".join(["PMR3 and PMR4 support the PMR trait.", "", "<provenance>", json.dumps(trace), "</provenance>"])
        workspace = mcp_server._WorkspaceHandle(
            key="company_a",
            label="CropProtectorAI",
            raw_path=Path("ExampleData/CompanyA_AgriTrait/raw"),
            store=mock.Mock(),
            record_count=2,
            cached=True,
            backend="gitkb",
        )

        with mock.patch(
            "dataroot.server.app._answer_live_ask",
            return_value=(answer, {"raw": None}, "agent"),
        ) as answerer:
            with mock.patch(
                "dataroot.query.persist_answer_artifacts",
                return_value={"inquiry": "inquiries/demo", "provenance_trace": "provenance_traces/demo"},
            ):
                result = mcp_server._ask(
                    workspace,
                    question,
                    use_agent=True,
                )

        answerer.assert_called_once()
        self.assertTrue(answerer.call_args.kwargs["use_agent"])
        self.assertEqual(result["answer"], "PMR3 and PMR4 support the PMR trait.")
        self.assertEqual(result["answer_source"], "agent")
        self.assertTrue(result["use_agent"])
        self.assertEqual(result["node_count"], 2)
        self.assertEqual(result["edge_count"], 1)
        self.assertEqual(result["stages"], ["query", "marker_gene", "answer"])
        self.assertEqual(result["trace"], trace)
        self.assertEqual(result["provenance_trace"], "provenance_traces/demo")


class BoundedDispatchTests(unittest.TestCase):
    """Exercise the dispatch layer against an in-memory store via monkeypatch.

    These tests validate that the MCP layer enforces hard caps on result size.
    They are not a substitute for the full GitKB end-to-end test below; the
    production server path always uses GitKBStore.
    """

    def _make_workspace(self, raw_path: Path) -> mcp_server._WorkspaceHandle:
        kb_root = raw_path.parent / "kb"
        store = LocalMarkdownStore(kb_root)
        profile_workspace(raw_path, store)
        link_workspace(store)
        return mcp_server._WorkspaceHandle(
            key="austin_permits",
            label="Austin Permits Explorer",
            raw_path=raw_path,
            store=store,
            record_count=len(store.list()),
        )

    def test_kb_search_clamps_caller_supplied_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw"
            raw_path.mkdir()
            (raw_path / "permits.csv").write_text(
                "permit_id,description\n"
                + "\n".join(f"BP-{i:04d},Construction project number {i}" for i in range(120)),
                encoding="utf-8",
            )
            workspace = self._make_workspace(raw_path)
            with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
                result = mcp_server._dispatch("kb_search", {"query": "Construction", "limit": 1000})
            self.assertEqual(result["cap"], mcp_server.SEARCH_LIMIT)
            self.assertEqual(result["limit"], mcp_server.SEARCH_LIMIT)
            self.assertLessEqual(len(result["results"]), mcp_server.SEARCH_LIMIT)

    def test_kb_list_truncates_to_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw"
            raw_path.mkdir()
            (raw_path / "permits.csv").write_text(
                "permit_id,note\n"
                + "\n".join(f"BP-{i:04d},row {i}" for i in range(150)),
                encoding="utf-8",
            )
            workspace = self._make_workspace(raw_path)
            with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
                result = mcp_server._dispatch("kb_list", {"type": "row_group", "limit": 10000})
            self.assertEqual(result["cap"], mcp_server.LIST_LIMIT)
            self.assertEqual(result["limit"], mcp_server.LIST_LIMIT)
            self.assertLessEqual(len(result["records"]), mcp_server.LIST_LIMIT)

    def test_kb_graph_clamps_depth(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_path = Path(temp_dir) / "raw"
            raw_path.mkdir()
            (raw_path / "permits.csv").write_text(
                "permit_id,note\nBP-1,first\nBP-2,second\n",
                encoding="utf-8",
            )
            workspace = self._make_workspace(raw_path)
            with mock.patch.object(mcp_server, "_get_workspace", return_value=workspace):
                result = mcp_server._dispatch(
                    "kb_graph",
                    {"slug": "tables/permits.csv", "depth": 99},
                )
            self.assertEqual(result["cap"], mcp_server.GRAPH_DEPTH_MAX)
            self.assertEqual(result["depth"], mcp_server.GRAPH_DEPTH_MAX)


class GitKBRequiredTests(unittest.TestCase):
    """Exercise the production code path that requires a real git-kb CLI."""

    @unittest.skipUnless(_git_kb_available(), "git-kb CLI not on PATH; install per README to run this test")
    def test_run_stdio_proceeds_when_gitkb_available(self) -> None:
        # We cannot actually attach a stdio client in the test, but we can
        # confirm _require_gitkb does not raise when the CLI is present.
        try:
            mcp_server._require_gitkb()
        except RuntimeError as exc:
            self.fail(f"_require_gitkb raised even though git-kb is available: {exc}")

    def test_run_stdio_returns_nonzero_when_gitkb_missing(self) -> None:
        with mock.patch("dataroot.kb.gitkb_store.GitKBStore.is_available", return_value=False):
            exit_code = mcp_server.run_stdio()
        self.assertEqual(exit_code, 1)


class CallToolWiringTests(unittest.TestCase):
    """The Server.call_tool decorator must surface dispatch errors as JSON, not crash."""

    def test_unknown_tool_returns_error_payload(self) -> None:
        server = mcp_server.build_server()
        # The mcp Server stores call-tool handlers in request_handlers keyed by request type.
        # Rather than poking at the internal structure, we exercise the outer behavior by
        # invoking _dispatch directly (which is what the registered handler delegates to).
        with self.assertRaises(ValueError):
            mcp_server._dispatch("not_a_real_tool", {})

    def test_call_tool_handler_serializes_errors(self) -> None:
        # Verify the registered handler wraps exceptions as TextContent error payloads.
        from mcp import types

        server = mcp_server.build_server()
        # Find the registered call-tool handler (it lives in request_handlers).
        handler = None
        for request_type, fn in server.request_handlers.items():
            if request_type.__name__ == "CallToolRequest":
                handler = fn
                break
        self.assertIsNotNone(handler, "call_tool handler must be registered")

        request = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="not_a_real_tool", arguments={}),
        )
        result = asyncio.run(handler(request))
        # ServerResult wraps a CallToolResult whose .content is a list of TextContent.
        contents = result.root.content
        self.assertEqual(len(contents), 1)
        payload = json.loads(contents[0].text)
        self.assertIn("error", payload)
        self.assertEqual(payload["tool"], "not_a_real_tool")


if __name__ == "__main__":
    unittest.main()
