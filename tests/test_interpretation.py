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
    def test_extracts_only_the_answer_line_and_drops_supporting_evidence(self) -> None:
        raw = (
            "Question: foo?\n"
            "\n"
            "Best candidate: A-CUL-TOM-014 / Solara-14\n"
            "\n"
            "Answer: yes. DataRoot found a tomato line ready for spring planting.\n"
            "\n"
            "Evidence:\n"
            "- A-CUL-TOM-014 has trait A [citation: rows/a]\n"
            "- Greenhouse passed [citation: rows/b]\n"
            "\n"
            "Recommendation: proceed with A-CUL-TOM-014.\n"
        )
        sanitized = _sanitize_final_answer_text(raw)
        self.assertEqual(
            sanitized,
            "yes. DataRoot found a tomato line ready for spring planting.",
        )

    def test_extracts_best_candidate_heading_when_no_answer_line(self) -> None:
        raw = (
            "# Expected Answer - Inquiry B-INQ-001\n"
            "**Question:** \"Which microbial strain produces ester?\"\n"
            "---\n"
            "## Best Candidate: B-STR-YE-017 / Yeast EsterMax 17\n"
            "### Genetic Basis\n"
            "- Has pathway genes B-GEN-AAT1 and B-GEN-EHT1\n"
        )
        sanitized = _sanitize_final_answer_text(raw)
        self.assertEqual(sanitized, "Best candidate: B-STR-YE-017 / Yeast EsterMax 17")

    def test_extracts_recommendation_line_when_no_answer_or_candidate(self) -> None:
        raw = "Recommendation: proceed with permit P-9001 because reviews are passing."
        sanitized = _sanitize_final_answer_text(raw)
        self.assertEqual(
            sanitized,
            "proceed with permit P-9001 because reviews are passing.",
        )

    def test_falls_back_to_first_paragraph_skipping_evidence_bullets(self) -> None:
        raw = (
            "Question: which open code tasks?\n"
            "\n"
            "Top matching evidence:\n"
            "- task T-1 [citation: rows/a]\n"
            "- task T-2 [citation: rows/b]\n"
        )
        sanitized = _sanitize_final_answer_text(raw)
        self.assertEqual(sanitized, "")

    def test_caps_long_text_at_first_sentence(self) -> None:
        long_first = "this is a long headline sentence " + ("describing the cited match in detail " * 10) + "for the demo viewer."
        raw = f"Answer: {long_first} A second sentence we should drop because the headline is already over budget."
        sanitized = _sanitize_final_answer_text(raw)
        self.assertTrue(sanitized.endswith("...") or sanitized.endswith(long_first))
        self.assertNotIn("second sentence we should drop", sanitized)

    def test_caps_answer_at_two_sentences(self) -> None:
        raw = "Answer: first sentence. second sentence. third sentence should not be shown."
        sanitized = _sanitize_final_answer_text(raw)
        self.assertEqual(sanitized, "first sentence. second sentence.")

    def test_passes_plain_short_answer_through(self) -> None:
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
