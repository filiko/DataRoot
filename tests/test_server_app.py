from __future__ import annotations

import os
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from dataroot.agent.codex_client import AgentResult
from dataroot.kb.base import DocumentRecord
import dataroot.server.app as app_module


class ServerAppTests(unittest.TestCase):
    def setUp(self) -> None:
        app_module._workspace_cache.clear()
        self.client = TestClient(app_module.app)

    def test_health_and_miro_entrypoints_load(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        labels = {company["label"] for company in health.json()["companies"]}
        self.assertIn("CropProtectorAI", labels)
        self.assertIn("BioReactorAI", labels)

        page = self.client.get("/miro/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("DataRoot runs from the Miro board", page.text)
        self.assertNotIn("textarea", page.text)
        self.assertNotIn("Run board question", page.text)

        sdk = self.client.get("/miro/sdk")
        self.assertEqual(sdk.status_code, 200)
        self.assertIn("LIVE_ASK_POLL_MS = 5000", sdk.text)
        self.assertIn("pollLiveAskInputs", sdk.text)
        self.assertIn("/api/live-ask-board-input", sdk.text)
        self.assertIn("icon:click", sdk.text)
        self.assertIn("custom:run-live-ask", sdk.text)
        self.assertIn("/api/ask-render-board-question", sdk.text)
        self.assertNotIn("openPanel", sdk.text)
        self.assertNotIn("app_card:", sdk.text)

    def test_ask_render_profiles_answers_persists_and_renders(self) -> None:
        runner = FakeRunner(_agent_answer("What specific genes make the tomato line powdery mildew resistant?"))
        with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token", "OPENAI_API_KEY": "key"}, clear=False):
            with patch("dataroot.agent.runner.Runner", return_value=runner):
                with patch(
                    "dataroot.server.app.render_provenance_to_miro",
                    return_value="https://miro.com/app/board/board/",
                ) as renderer:
                    response = self.client.post(
                        "/api/ask-render",
                        json={
                            "company": "company_a",
                            "board_id": "board",
                            "question": "What specific genes make the tomato line powdery mildew resistant?",
                            "include_proof": True,
                        },
                    )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("A-GEN-PMR3", payload["answer"])
        self.assertIn("A-GEN-PMR4", payload["answer"])
        self.assertEqual(payload["question"], "What specific genes make the tomato line powdery mildew resistant?")
        self.assertEqual(payload["board_url"], "https://miro.com/app/board/board/")
        self.assertTrue(payload["provenance_trace"].startswith("provenance_traces/"))
        self.assertGreaterEqual(payload["node_count"], 5)
        self.assertIn("marker_gene", payload["stages"])
        self.assertEqual(payload["answer_source"], "agent")
        self.assertEqual(payload["interpreter_source"], "deterministic_fallback")
        self.assertEqual(payload["planner_source"], "deterministic_fallback")
        self.assertTrue(payload["proof_included"])
        self.assertEqual(payload["section_status"], "updated")
        self.assertEqual(payload["trigger_source"], "api_submit")
        self.assertTrue(all((tool.get("function") or {}).get("name") not in {"log_inquiry", "render_provenance"} for tool in runner.tools))
        renderer.assert_called_once()
        self.assertEqual(renderer.call_args.kwargs["board_id"], "board")
        self.assertEqual(renderer.call_args.kwargs["context_label"], "CropProtectorAI")
        self.assertEqual(renderer.call_args.kwargs["section_title"], "CropProtectorAI - Live Ask")
        self.assertIn("A-GEN-PMR3", renderer.call_args.kwargs["answer_text"])
        self.assertTrue(renderer.call_args.kwargs["update_existing_section"])
        self.assertTrue(renderer.call_args.kwargs["include_proof"])
        self.assertIsInstance(renderer.call_args.kwargs["render_metadata"], dict)

    def test_board_question_endpoint_reads_live_ask_input(self) -> None:
        with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token"}, clear=False):
            with patch("dataroot.server.app.MiroClient", return_value=FakeMiroClient()):
                with patch(
                    "dataroot.server.app._answer_with_agent",
                    return_value=(
                        _agent_answer("What are the next batches or runs coming out soon?"),
                        _trace("What are the next batches or runs coming out soon?"),
                    ),
                ):
                    with patch(
                        "dataroot.server.app.render_provenance_to_miro",
                        return_value="https://miro.com/app/board/board/",
                    ):
                        response = self.client.post(
                            "/api/ask-render-board-question",
                            json={
                                "board_id": "board",
                                "include_proof": False,
                            },
                        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["question"], "What are the next batches or runs coming out soon?")
        self.assertEqual(payload["company"], "company_b")
        self.assertEqual(payload["trigger_source"], "board_question_submit")

    def test_live_ask_board_input_runs_submitted_question(self) -> None:
        question = "Can BioReactorAI scale the next ester run soon?"
        with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token"}, clear=False):
            with patch("dataroot.server.app.MiroClient", return_value=FakeMiroClient()):
                with patch(
                    "dataroot.server.app._answer_with_agent",
                    return_value=(_agent_answer(question), _trace(question)),
                ):
                    with patch(
                        "dataroot.server.app.render_provenance_to_miro",
                        return_value="https://miro.com/app/board/board/",
                    ) as renderer:
                        response = self.client.post(
                            "/api/live-ask-board-input",
                            json={
                                "board_id": "board",
                                "input_item_id": "question-input",
                                "question": question,
                            },
                        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["question"], question)
        self.assertEqual(payload["company"], "company_b")
        self.assertEqual(payload["trigger_source"], "board_input_poll")
        renderer.assert_called_once()
        self.assertEqual(renderer.call_args.kwargs["section_title"], "BioReactorAI - Live Ask")

    def test_live_ask_board_input_blank_clears_section(self) -> None:
        with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token"}, clear=False):
            with patch("dataroot.server.app.MiroClient", return_value=FakeMiroClient()):
                with patch(
                    "dataroot.server.app.clear_live_ask_section_to_miro",
                    return_value="https://miro.com/app/board/board/",
                ) as clearer:
                    with patch("dataroot.server.app._answer_with_agent") as answerer:
                        response = self.client.post(
                            "/api/live-ask-board-input",
                            json={
                                "board_id": "board",
                                "input_item_id": "question-input",
                                "question": "   ",
                            },
                        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["question"], "")
        self.assertEqual(payload["answer"], "")
        self.assertEqual(payload["company"], "company_b")
        self.assertEqual(payload["section_status"], "cleared")
        self.assertEqual(payload["trigger_source"], "board_input_poll")
        clearer.assert_called_once_with(board_id="board", section_title="BioReactorAI - Live Ask")
        answerer.assert_not_called()

    def test_live_ask_falls_back_when_agent_is_unavailable(self) -> None:
        with patch.dict(
            os.environ,
            {"MIRO_ACCESS_TOKEN": "token", "OPENAI_API_KEY": "", "DATAROOT_KB_BACKEND": "local"},
            clear=True,
        ):
            with patch(
                "dataroot.server.app.render_provenance_to_miro",
                return_value="https://miro.com/app/board/board/",
            ) as renderer:
                response = self.client.post(
                    "/api/ask-render",
                    json={
                        "company": "company_a",
                        "board_id": "board",
                        "question": "What specific genes make the tomato line powdery mildew resistant?",
                        "include_proof": True,
                    },
                )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["answer_source"], "deterministic_fallback")
        renderer.assert_called_once()

        app_module._workspace_cache.clear()
        with patch.dict(
            os.environ,
            {"MIRO_ACCESS_TOKEN": "token", "OPENAI_API_KEY": "key", "DATAROOT_KB_BACKEND": "local"},
            clear=True,
        ):
            with patch(
                "dataroot.agent.runner.Runner",
                return_value=FakeRunner("Answer without provenance."),
            ):
                with patch(
                    "dataroot.server.app.render_provenance_to_miro",
                    return_value="https://miro.com/app/board/board/",
                ) as renderer:
                    invalid = self.client.post(
                        "/api/ask-render",
                        json={"company": "company_a", "board_id": "board", "question": "hello"},
                    )

        self.assertEqual(invalid.status_code, 200, invalid.text)
        self.assertEqual(invalid.json()["answer_source"], "deterministic_fallback")
        renderer.assert_called_once()

        app_module._workspace_cache.clear()
        with patch.dict(
            os.environ,
            {"MIRO_ACCESS_TOKEN": "token", "OPENAI_API_KEY": "key", "DATAROOT_KB_BACKEND": "local"},
            clear=True,
        ):
            with patch(
                "dataroot.agent.runner.Runner",
                return_value=FakeRunner(error=RuntimeError("Error code: 429 - insufficient_quota")),
            ):
                with patch(
                    "dataroot.server.app.render_provenance_to_miro",
                    return_value="https://miro.com/app/board/board/",
                ) as renderer:
                    quota = self.client.post(
                        "/api/ask-render",
                        json={
                            "company": "company_b",
                            "board_id": "board",
                            "question": "do we have the capacity to run another fermnation product",
                        },
                    )

        self.assertEqual(quota.status_code, 200, quota.text)
        self.assertEqual(quota.json()["answer_source"], "deterministic_fallback")
        self.assertIn("fermentation-side availability", quota.json()["answer"])
        renderer.assert_called_once()

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
        missing_question = self.client.post("/api/ask-render", json={"company": "company_a", "board_id": "board", "question": ""})
        self.assertEqual(missing_question.status_code, 400)

        unknown_company = self.client.post("/api/ask-render", json={"company": "missing", "board_id": "board", "question": "hello"})
        self.assertEqual(unknown_company.status_code, 400)

        with patch.dict(os.environ, {"MIRO_BOARD_ID": "optional_existing_board_id"}, clear=True):
            missing_board = self.client.post("/api/ask-render", json={"company": "company_a", "question": "hello"})
        self.assertEqual(missing_board.status_code, 400)
        self.assertIn("board_id is required", missing_board.text)


class FakeRunner:
    def __init__(self, final_output: str = "", error: Exception | None = None):
        self.final_output = final_output
        self.error = error
        self.tools = []

    def run(self, system_prompt, tools, messages, tool_executor, temperature=0.7):
        if self.error:
            raise self.error
        self.system_prompt = system_prompt
        self.tools = tools
        self.messages = messages
        self.tool_executor = tool_executor
        self.temperature = temperature
        return AgentResult(messages=[], final_output=self.final_output, tool_calls=[], error=None)


class FakeMiroClient:
    def list_frames(self, board_id):
        return [
            {
                "id": "company-b-live",
                "type": "frame",
                "data": {"title": "BioReactorAI - Live Ask"},
            }
        ]

    def list_items(self, board_id):
        return [
            {
                "id": "question-input",
                "type": "text",
                "parent": {"id": "company-b-live"},
                "data": {
                    "content": (
                        "<p><strong>Type your question here:</strong></p>"
                        "<p>What are the next batches or runs coming out soon?</p>"
                    )
                },
            }
        ]


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
