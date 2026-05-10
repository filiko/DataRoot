from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from dataroot.kb.base import DocumentRecord
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.render.interpretation import (
    _sanitize_final_answer_text,
    _stage_from_slug,
    interpret_data_tidbits,
)


class InterpretationTests(unittest.TestCase):
    def test_deterministic_interpreter_preserves_proof_rows(self) -> None:
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
                "provenance_summary": {"reasoning": "Solara has the PMR marker.", "confidence": "high"},
            }

            with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0"}, clear=False):
                interpretation = interpret_data_tidbits(trace, store=store)

        self.assertEqual(interpretation.source, "deterministic_fallback")
        self.assertEqual(interpretation.confidence, "high")
        self.assertIn("Solara-14", interpretation.claims[0].claim)
        self.assertEqual(
            interpretation.claims[0].evidence_refs,
            ["row_groups/registries/cultivar_registry.csv/a-cul-tom-014"],
        )
        self.assertIn("marker_ids: A-GEN-PMR3", interpretation.proof_rows[0].raw_detail)

    def test_agent_interpreter_filters_invented_evidence_refs(self) -> None:
        class FakeClient:
            def run(self, *args, **kwargs):
                from dataroot.agent.codex_client import AgentResult

                payload = {
                    "takeaway": "Solara carries PMR evidence.",
                    "confidence": "high",
                    "retrieval_explanation": "DataRoot found one useful record.",
                    "claims": [
                        {
                            "claim": "Solara carries the PMR marker.",
                            "why_it_matters": "The marker is the cited resistance signal.",
                            "evidence_refs": ["rows/a"],
                            "source_label": "rows/a",
                            "importance": "primary",
                        },
                        {
                            "claim": "Invented claim.",
                            "why_it_matters": "Should be removed.",
                            "evidence_refs": ["rows/missing"],
                            "source_label": "rows/missing",
                            "importance": "primary",
                        },
                    ],
                    "caveats": [],
                }
                return AgentResult(messages=[], final_output=json.dumps(payload), tool_calls=[], error=None)

        trace = {
            "question": "Question?",
            "nodes": [{"id": "n1", "slug": "rows/a", "label": "Solara", "stage": "evidence"}],
            "edges": [],
            "provenance_summary": {"reasoning": "Fallback answer."},
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key"}, clear=False):
            with patch("dataroot.agent.codex_client.CodexClient", return_value=FakeClient()):
                interpretation = interpret_data_tidbits(trace)

        self.assertEqual(interpretation.source, "agent")
        self.assertEqual([claim.claim for claim in interpretation.claims], ["Solara carries the PMR marker."])
        self.assertEqual(interpretation.claims[0].evidence_refs, ["rows/a"])

    def test_agent_interpreter_invalid_json_falls_back(self) -> None:
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
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key"}, clear=False):
            with patch("dataroot.agent.codex_client.CodexClient", return_value=FakeClient()):
                interpretation = interpret_data_tidbits(trace)

        self.assertEqual(interpretation.source, "deterministic_fallback")
        self.assertEqual(interpretation.takeaway, "Fallback answer.")


class FinalAnswerSanitizerTests(unittest.TestCase):
    def test_strips_live_ask_prefix_and_citations(self) -> None:
        raw = "Answer: foo bar baz [citation: rows/x] qux [citation: rows/y]"
        self.assertEqual(_sanitize_final_answer_text(raw), "foo bar baz qux")

    def test_strips_expected_answer_header_and_question_line(self) -> None:
        raw = (
            "# Expected Answer — Inquiry B-INQ-001\n"
            "**Question:** \"Which microbial strain produces ester?\"\n"
            "---\n"
            "## Best Candidate: B-STR-YE-017\n"
            "Body text follows."
        )
        sanitized = _sanitize_final_answer_text(raw)
        self.assertNotIn("Expected Answer", sanitized)
        self.assertNotIn("Question:", sanitized)
        self.assertNotIn("---", sanitized)
        self.assertIn("Body text follows.", sanitized)

    def test_passes_plain_answer_through(self) -> None:
        raw = "DataRoot identified strain B-STR-YE-017 as the strongest match."
        self.assertEqual(_sanitize_final_answer_text(raw), raw)

    def test_strips_provenance_block(self) -> None:
        raw = "Plain answer text\n<provenance>{\"x\": 1}</provenance>"
        self.assertEqual(_sanitize_final_answer_text(raw), "Plain answer text")


class SlugStageTests(unittest.TestCase):
    def test_row_groups_dataset_segment(self) -> None:
        self.assertEqual(
            _stage_from_slug("row_groups/permits/issued_construction_permits.csv/abc"),
            "permits",
        )

    def test_tables_dataset_segment(self) -> None:
        self.assertEqual(_stage_from_slug("tables/reviews/plan_review_cases.csv"), "reviews")

    def test_unrecognized_slug_returns_empty(self) -> None:
        self.assertEqual(_stage_from_slug("inquiries/A-INQ-001"), "")

    def test_blank_slug_returns_empty(self) -> None:
        self.assertEqual(_stage_from_slug(""), "")


if __name__ == "__main__":
    unittest.main()
