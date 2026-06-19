from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from dataroot.kb.base import DocumentRecord
import dataroot.server.app as app_module


class ServerAppTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._workspace_cache.clear()
        self.client = TestClient(app_module.app)

    def test_health_index_and_workspace_entrypoints_load(self) -> None:
        index = self.client.get("/")
        self.assertEqual(index.status_code, 200)
        self.assertEqual(index.json()["service"], "DataRoot Ask API")
        self.assertEqual(index.json()["rendering"], "in_app")

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(health.json()["rendering"], "in_app")
        labels = {company["label"] for company in health.json()["companies"]}
        self.assertIn("CropProtectorAI", labels)
        self.assertIn("BioReactorAI", labels)

        workspaces = self.client.get("/api/workspaces")
        self.assertEqual(workspaces.status_code, 200)
        keys = {workspace["key"] for workspace in workspaces.json()["workspaces"]}
        self.assertIn("company_a", keys)
        self.assertIn("austin_permits", keys)

        self.assertEqual(self.client.get("/miro/").status_code, 404)
        self.assertEqual(self.client.get("/miro/sdk").status_code, 404)

    def test_api_ask_profiles_answers_and_persists(self) -> None:
        question = "What specific genes make the tomato line powdery mildew resistant?"
        trace = _trace(question)
        answer = _agent_answer(question)

        with patch(
            "dataroot.server.app._answer_live_ask",
            return_value=(answer, trace, "agent"),
        ) as answerer:
            with patch(
                "dataroot.server.app.persist_answer_artifacts",
                return_value={"inquiry": "inquiries/demo", "provenance_trace": "provenance_traces/demo"},
            ) as persister:
                response = self.client.post(
                    "/api/ask",
                    json={
                        "company": "company_a",
                        "question": question,
                        "use_agent": True,
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("A-GEN-PMR3", payload["answer"])
        self.assertNotIn("<provenance>", payload["answer"])
        self.assertEqual(payload["question"], question)
        self.assertEqual(payload["company"], "company_a")
        self.assertEqual(payload["provenance_trace"], "provenance_traces/demo")
        self.assertEqual(payload["node_count"], 5)
        self.assertEqual(payload["edge_count"], 0)
        self.assertIn("marker_gene", payload["stages"])
        self.assertEqual(payload["trace"], trace)
        self.assertEqual(payload["answer_source"], "agent")
        self.assertIn(payload["backend"], {"local", "gitkb"})
        answerer.assert_called_once()
        self.assertTrue(answerer.call_args.kwargs["use_agent"])
        persister.assert_called_once()

    def test_live_ask_falls_back_when_agent_is_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "", "MINIMAX_API_KEY": "", "DATAROOT_KB_BACKEND": "local"},
            clear=True,
        ):
            with patch(
                "dataroot.server.app._answer_with_deterministic_fallback",
                return_value=(
                    _agent_answer("fallback"),
                    _trace("fallback"),
                ),
            ) as fallback:
                answer, trace, source = app_module._answer_live_ask(
                    app_module.COMPANIES["company_a"],
                    app_module.CompanyWorkspace(
                        config=app_module.COMPANIES["company_a"],
                        store=object(),
                        record_count=0,
                        cached=False,
                    ),
                    "fallback",
                    use_agent=True,
                )

        self.assertIn("A-GEN-PMR3", answer)
        self.assertEqual(trace["question"], "fallback")
        self.assertEqual(source, "deterministic_fallback")
        fallback.assert_called_once()

    def test_workspace_uses_gitkb_when_server_backend_requests_it(self) -> None:
        class FakeGitKBStore:
            def __init__(self, root):
                self.root = root

            def list(self, doc_type=None, path_prefix=None):
                return [
                    DocumentRecord(
                        doc_type="workspace",
                        slug="workspaces/demo",
                        title="Demo",
                        frontmatter={},
                    )
                ]

        with patch.dict(os.environ, {"DATAROOT_SERVER_KB_BACKEND": "gitkb"}, clear=False):
            with patch("dataroot.server.app.GitKBStore", FakeGitKBStore):
                with patch("dataroot.server.app.bootstrap_gitkb_runtime") as bootstrap:
                    workspace = app_module._workspace_for(app_module.COMPANIES["company_a"])

        bootstrap.assert_called_once()
        self.assertEqual(workspace.backend, "gitkb")
        self.assertEqual(workspace.record_count, 1)
        self.assertTrue(workspace.cached)

    def test_invalid_request_errors(self) -> None:
        missing_question = self.client.post("/api/ask", json={"company": "company_a", "question": ""})
        self.assertEqual(missing_question.status_code, 400)

        unknown_company = self.client.post("/api/ask", json={"company": "missing", "question": "hello"})
        self.assertEqual(unknown_company.status_code, 400)

    def test_live_ask_tool_filter_excludes_log_and_render_tools(self) -> None:
        tools = [
            {"function": {"name": "kb_search"}},
            {"function": {"name": "log_inquiry"}},
            {"function": {"name": "render_provenance"}},
        ]

        filtered = app_module._live_ask_tools(tools)

        self.assertEqual(filtered, [{"function": {"name": "kb_search"}}])


def _trace(question: str) -> dict:
    return {
        "question": question,
        "nodes": [
            {"id": "n1", "slug": "row_groups/registries/marker_gene_catalog.csv/a-gen-pmr3", "label": "A-GEN-PMR3", "stage": "marker_gene"},
            {"id": "n2", "slug": "row_groups/registries/marker_gene_catalog.csv/a-gen-pmr4", "label": "A-GEN-PMR4", "stage": "marker_gene"},
            {"id": "n3", "slug": "row_groups/registries/trait_ontology.csv/a-trt-pmr", "label": "A-TRT-PMR", "stage": "trait"},
            {"id": "n4", "slug": "row_groups/registries/cultivar_registry.csv/a-cul-tom-014", "label": "Solara-14", "stage": "cultivar"},
            {"id": "n5", "slug": "row_groups/trials/greenhouse_trials_2026_q1.csv/a-trl-gh-001", "label": "Trial", "stage": "greenhouse_trials"},
        ],
        "edges": [],
        "stages": ["query", "cultivar", "marker_gene", "greenhouse_trials", "answer"],
    }


def _agent_answer(question: str) -> str:
    return "\n".join(
        [
            f"Question: {question}",
            "",
            "Answer: Solara-14 is supported by A-GEN-PMR3, with A-GEN-PMR4 as alternate PMR evidence.",
            "",
            "<provenance>",
            json.dumps(_trace(question)),
            "</provenance>",
        ]
    )


if __name__ == "__main__":
    unittest.main()
