from __future__ import annotations

import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dataroot.kb.base import DocumentRecord
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.render.miro_plan import plan_miro_board


class MiroPlanTests(unittest.TestCase):
    def test_deterministic_plan_groups_evidence_and_preserves_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            store.write(
                DocumentRecord(
                    doc_type="row_group",
                    slug="row_groups/registries/cultivar_registry.csv/a-cul-tom-014",
                    title="Solara-14",
                    frontmatter={
                        "table": "tables/registries/cultivar_registry.csv",
                        "row_data": {"cultivar_id": "A-CUL-TOM-014", "marker_ids": "A-GEN-PMR3"},
                    },
                )
            )
            trace = {
                "question": "What makes Solara resistant?",
                "nodes": [
                    {
                        "id": "n1",
                        "slug": "row_groups/registries/cultivar_registry.csv/a-cul-tom-014",
                        "label": "Solara-14",
                        "stage": "cultivar",
                    }
                ],
                "edges": [],
                "stages": ["query", "cultivar", "answer"],
                "provenance_summary": {
                    "primary_candidate": "A-CUL-TOM-014 / Solara-14",
                    "confidence": "high",
                    "reasoning": "Solara has the PMR marker.",
                },
            }

            with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "DATAROOT_USE_MIRO_PLANNER": "0"}, clear=False):
                plan = plan_miro_board(trace, store=store)

        self.assertEqual(plan.recommendation, "A-CUL-TOM-014 / Solara-14")
        self.assertEqual(plan.context_label, "CropProtectorAI")
        self.assertEqual(plan.title, "CropProtectorAI evidence path")
        self.assertIn("DataRoot found 1 cited evidence record", plan.retrieval_summary)
        self.assertEqual(plan.evidence_cards[0].citation, "row_groups/registries/cultivar_registry.csv/a-cul-tom-014")
        self.assertEqual(plan.evidence_cards[0].source, "registries/cultivar_registry.csv")
        self.assertIn("Solara-14", plan.evidence_cards[0].title)
        self.assertIn("marker_ids: A-GEN-PMR3", plan.proof_rows[0].raw_detail)
        self.assertEqual(plan.interpreter_source, "deterministic_fallback")
        self.assertEqual(plan.planner_source, "deterministic_fallback")

    def test_model_planner_invalid_json_falls_back(self) -> None:
        class FakeClient:
            def run(self, *args, **kwargs):
                from dataroot.agent.codex_client import AgentResult

                return AgentResult(messages=[], final_output="not json", tool_calls=[], error=None)

        trace = {
            "question": "Question?",
            "nodes": [{"id": "n1", "slug": "rows/a", "label": "Evidence", "stage": "evidence"}],
            "edges": [],
            "provenance_summary": {"reasoning": "Fallback answer."},
        }
        with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "OPENAI_API_KEY": "key"}, clear=False):
            with patch("dataroot.agent.codex_client.CodexClient", return_value=FakeClient()):
                plan = plan_miro_board(trace)

        self.assertEqual(plan.answer, "Fallback answer.")
        self.assertEqual(plan.evidence_cards[0].citation, "rows/a")
        self.assertEqual(plan.planner_source, "deterministic_fallback")

    def test_model_planner_is_default_when_openai_key_exists(self) -> None:
        class FakeClient:
            def run(self, *args, **kwargs):
                from dataroot.agent.codex_client import AgentResult

                payload = {
                    "title": "Friendly board",
                    "context_label": "DataRoot demo",
                    "question": "Question?",
                    "answer": "Friendly answer.",
                    "recommendation": "Use the cited record.",
                    "confidence": "high",
                    "retrieval_summary": "DataRoot found one useful record.",
                    "evidence_cards": [
                        {
                            "id": "claim_1",
                            "title": "Friendly claim",
                            "detail": "Why this matters.",
                            "stage": "evidence",
                            "citation": "rows/a",
                            "source": "rows/a",
                            "kind": "evidence",
                            "emphasis": "primary",
                        }
                    ],
                    "alternatives": [],
                    "connections": [],
                    "audit_notes": ["Planner used friendly card text."],
                }
                return AgentResult(messages=[], final_output=json.dumps(payload), tool_calls=[], error=None)

        trace = {
            "question": "Question?",
            "nodes": [{"id": "n1", "slug": "rows/a", "label": "Raw row", "stage": "evidence"}],
            "edges": [],
            "provenance_summary": {"reasoning": "Fallback answer."},
        }
        with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "OPENAI_API_KEY": "key"}, clear=False):
            with patch("dataroot.agent.codex_client.CodexClient", return_value=FakeClient()):
                plan = plan_miro_board(trace)

        self.assertEqual(plan.answer, "Friendly answer.")
        self.assertEqual(plan.evidence_cards[0].title, "Friendly claim")
        self.assertEqual(plan.evidence_cards[0].citation, "rows/a")
        self.assertEqual(plan.planner_source, "agent")

    def test_model_planner_can_be_disabled_with_env_flag(self) -> None:
        trace = {
            "question": "Question?",
            "nodes": [{"id": "n1", "slug": "rows/a", "label": "Raw row", "stage": "evidence"}],
            "edges": [],
            "provenance_summary": {"reasoning": "Fallback answer."},
        }
        with patch.dict(
            os.environ,
            {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "DATAROOT_USE_MIRO_PLANNER": "0", "OPENAI_API_KEY": "key"},
            clear=False,
        ):
            plan = plan_miro_board(trace)

        self.assertEqual(plan.answer, "Fallback answer.")
        self.assertEqual(plan.planner_source, "deterministic_fallback")


if __name__ == "__main__":
    unittest.main()
