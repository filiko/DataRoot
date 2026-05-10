from __future__ import annotations

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

    def test_health_and_panel_load(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        labels = {company["label"] for company in health.json()["companies"]}
        self.assertIn("CropProtectorAI", labels)
        self.assertIn("BioReactorAI", labels)

        panel = self.client.get("/miro/")
        self.assertEqual(panel.status_code, 200)
        self.assertIn("Ask DataRoot", panel.text)
        self.assertIn("CropProtectorAI", panel.text)
        self.assertIn("BioReactorAI", panel.text)
        self.assertIn("Current board auto-detected", panel.text)
        self.assertIn("Include precise proof frame", panel.text)

        sdk = self.client.get("/miro/sdk")
        self.assertEqual(sdk.status_code, 200)
        self.assertIn("icon:click", sdk.text)
        self.assertIn("openPanel", sdk.text)
        self.assertIn('url: "/miro/"', sdk.text)

    def test_ask_render_profiles_answers_persists_and_renders(self) -> None:
        with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token"}, clear=False):
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
        self.assertEqual(payload["board_url"], "https://miro.com/app/board/board/")
        self.assertTrue(payload["provenance_trace"].startswith("provenance_traces/"))
        self.assertGreaterEqual(payload["node_count"], 5)
        self.assertIn("marker_gene", payload["stages"])
        self.assertEqual(payload["interpreter_source"], "deterministic_fallback")
        self.assertEqual(payload["planner_source"], "deterministic_fallback")
        self.assertTrue(payload["proof_included"])
        renderer.assert_called_once()
        self.assertEqual(renderer.call_args.kwargs["board_id"], "board")
        self.assertEqual(renderer.call_args.kwargs["context_label"], "CropProtectorAI")
        self.assertEqual(renderer.call_args.kwargs["section_title"], "CropProtectorAI - Live Ask")
        self.assertTrue(renderer.call_args.kwargs["update_existing_section"])
        self.assertTrue(renderer.call_args.kwargs["include_proof"])
        self.assertIsInstance(renderer.call_args.kwargs["render_metadata"], dict)

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


if __name__ == "__main__":
    unittest.main()
