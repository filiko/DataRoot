from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import requests

from dataroot.agent.tools import ToolExecutor
from dataroot.cli import main
from dataroot.config import load_config
from dataroot.kb.base import DocumentRecord
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.render.miro import MiroClient, render_provenance_to_miro
from dataroot.render.miro_refresh import plan_miro_board_refresh, refresh_ask_board


class FakeResponse:
    def __init__(self, payload: dict | None = None, status_code: int = 200):
        self.payload = payload or {}
        self.status_code = status_code
        self.text = json.dumps(self.payload)
        self.content = self.text.encode("utf-8") if payload is not None else b""

    def json(self) -> dict:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(self.text)


class FakeMiroHTTP:
    def __init__(
        self,
        existing_items: list[dict] | None = None,
        existing_frames: list[dict] | None = None,
        existing_connectors: list[dict] | None = None,
    ):
        self.existing_items = existing_items or []
        self.existing_frames = existing_frames or []
        self.existing_connectors = existing_connectors or []
        self.calls: list[dict] = []
        self.counts: dict[str, int] = {}

    def __call__(self, method: str, url: str, **kwargs) -> FakeResponse:
        self.calls.append({"method": method, "url": url, "json": kwargs.get("json"), "params": kwargs.get("params")})
        if method == "GET" and url.endswith("/items"):
            return FakeResponse({"data": self.existing_items})
        if method == "GET" and url.endswith("/frames"):
            return FakeResponse({"data": self.existing_frames})
        if method == "GET" and url.endswith("/connectors"):
            return FakeResponse({"data": self.existing_connectors})
        if method == "DELETE":
            return FakeResponse(None)
        if method == "PATCH":
            return FakeResponse({"id": url.rsplit("/", 1)[-1]})
        endpoint = url.rsplit("/", 1)[-1]
        self.counts[endpoint] = self.counts.get(endpoint, 0) + 1
        return FakeResponse({"id": f"{endpoint}-{self.counts[endpoint]}"})

    def posts(self, endpoint: str) -> list[dict]:
        return [call for call in self.calls if call["method"] == "POST" and call["url"].endswith(f"/{endpoint}")]

    def deletes(self) -> list[dict]:
        return [call for call in self.calls if call["method"] == "DELETE"]

    def patches(self, endpoint: str) -> list[dict]:
        return [call for call in self.calls if call["method"] == "PATCH" and f"/{endpoint}/" in call["url"]]


class MiroRendererTests(unittest.TestCase):
    def test_declared_empty_stages_and_visual_anchors_are_rendered(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[{"id": "n1", "slug": "row_groups/demo.csv/a", "label": "Evidence row", "stage": "evidence"}],
            stages=["query", "evidence", "answer"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        self.assertEqual(len(fake.posts("frames")), 2)
        self.assertEqual(len(fake.posts("shapes")), 5)
        frame_titles = [call["json"]["data"]["title"] for call in fake.posts("frames")]
        self.assertEqual(frame_titles, ["DataRoot demo", "Evidence"])

    def test_flow_uses_single_question_retrieval_evidence_answer_chain(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {"id": "n1", "slug": "rows/a", "label": "Candidate", "stage": "cultivar"},
                {"id": "n2", "slug": "rows/b", "label": "Field trial", "stage": "field_trials"},
            ],
            edges=[{"from": "n1", "to": "n2", "label": "validated by"}],
            stages=["cultivar", "field_trials"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board", context_label="CropProtectorAI")

        shapes = fake.posts("shapes")
        question = next(call for call in shapes if "<strong>Question</strong>" in call["json"]["data"]["content"])
        retrieval = next(call for call in shapes if "<strong>GitKB retrieval</strong>" in call["json"]["data"]["content"])
        evidence = next(call for call in shapes if "<strong>Evidence Path</strong>" in call["json"]["data"]["content"])
        answer = next(call for call in shapes if "<strong>Final Answer</strong>" in call["json"]["data"]["content"])

        self.assertLess(question["json"]["position"]["x"], retrieval["json"]["position"]["x"])
        self.assertLess(retrieval["json"]["position"]["x"], evidence["json"]["position"]["x"])
        self.assertEqual(question["json"]["position"]["x"], answer["json"]["position"]["x"])
        self.assertGreater(answer["json"]["position"]["y"], question["json"]["position"]["y"])

        captions = [
            caption["content"]
            for call in fake.posts("connectors")
            for caption in call["json"].get("captions", [])
        ]
        self.assertEqual(captions, ["asks", "retrieves", "answers"])

    def test_shape_content_prioritizes_human_label_over_slug(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {
                    "id": "n1",
                    "slug": "row_groups/registries/cultivar_registry.csv/a-cul-tom-014",
                    "label": "Solara-14",
                    "stage": "cultivar",
                }
            ],
            stages=["cultivar"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        shape_content = "\n".join(call["json"]["data"]["content"] for call in fake.posts("shapes"))
        self.assertIn("Solara-14", shape_content)
        self.assertIn("a-cul-tom-014", shape_content)

    def test_child_item_positions_are_relative_to_parent_frame(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {"id": "n1", "slug": "rows/a", "label": "First", "stage": "cultivar"},
                {"id": "n2", "slug": "rows/b", "label": "Second", "stage": "field_trials"},
            ],
            stages=["cultivar", "field_trials"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        evidence_positions = [
            call["json"]["position"]
            for call in fake.posts("shapes")
            if "First" in call["json"]["data"]["content"] or "Second" in call["json"]["data"]["content"]
        ]
        self.assertEqual(len(evidence_positions), 2)
        self.assertEqual(evidence_positions[0]["x"], 380.0)
        self.assertEqual(evidence_positions[1]["x"], 380.0)
        self.assertGreater(evidence_positions[0]["y"], 0)
        self.assertLess(evidence_positions[0]["y"], 980)

    def test_node_description_and_edge_evidence_create_readable_notes(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {"id": "n1", "slug": "rows/a", "label": "Candidate", "stage": "cultivar", "description": "Strong candidate with both markers."},
                {"id": "n2", "slug": "rows/b", "label": "Field trial", "stage": "field_trials"},
            ],
            edges=[{"from": "n1", "to": "n2", "label": "validated by", "evidence": "Field trial passed in Texas Zone 8."}],
            stages=["cultivar", "field_trials"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        shape_content = "\n".join(call["json"]["data"]["content"] for call in fake.posts("shapes"))
        self.assertIn("Strong candidate with both markers.", shape_content)
        captions = [
            caption["content"]
            for call in fake.posts("connectors")
            for caption in call["json"].get("captions", [])
        ]
        self.assertNotIn("validated by", captions)
        self.assertEqual(captions, ["asks", "retrieves", "answers"])

    def test_light_enrichment_uses_compact_kb_summary_when_trace_is_sparse(self) -> None:
        fake = FakeMiroHTTP()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            store.write(
                DocumentRecord(
                    doc_type="row_group",
                    slug="row_groups/demo.csv/a",
                    title="Demo row",
                    frontmatter={"row_data": {"cultivar_id": "A-CUL-TOM-014", "name": "Solara-14", "status": "released"}},
                )
            )
            trace = _trace(
                nodes=[{"id": "n1", "slug": "row_groups/demo.csv/a", "label": "Solara-14", "stage": "cultivar"}],
                stages=["cultivar"],
            )

            with _miro_env(), patch("requests.Session.request", new=fake):
                render_provenance_to_miro(trace, store=store, board_id="board")

        shape_content = "\n".join(call["json"]["data"]["content"] for call in fake.posts("shapes"))
        self.assertIn("cultivar id: A-CUL-TOM-014", shape_content)
        self.assertIn("name: Solara-14", shape_content)

    def test_header_summary_uses_inquiry_answer_without_provenance_block(self) -> None:
        fake = FakeMiroHTTP()
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            store.write(
                DocumentRecord(
                    doc_type="inquiry",
                    slug="inquiries/demo",
                    title="Demo inquiry",
                    frontmatter={},
                    body="\n".join(
                        [
                            "# Inquiry",
                            "",
                            "## Answer",
                            "",
                            "Question: Do we have a ready candidate?",
                            "Best candidate: A-CUL-TOM-014 / Solara-14",
                            "Answer: yes. The line is ready for spring planting.",
                            "",
                            "<provenance>",
                            '{"nodes": []}',
                            "</provenance>",
                        ]
                    ),
                )
            )
            trace = _trace(stages=["query", "evidence", "answer"])

            with _miro_env(), patch("requests.Session.request", new=fake):
                render_provenance_to_miro(trace, store=store, inquiry_slug="inquiries/demo", board_id="board")

        shape_content = "\n".join(call["json"]["data"]["content"] for call in fake.posts("shapes"))
        self.assertIn("Best candidate: A-CUL-TOM-014", shape_content)
        self.assertIn("Answer: yes.", shape_content)
        self.assertNotIn("&lt;provenance&gt;", shape_content)

    def test_only_fixed_flow_connectors_are_rendered(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {"id": "n1", "slug": "rows/a", "label": "Primary", "stage": "evidence"},
                {"id": "n2", "slug": "rows/b", "label": "Secondary", "stage": "evidence"},
                {"id": "n3", "slug": "rows/c", "label": "Normal", "stage": "evidence"},
            ],
            stages=["evidence"],
            summary={
                "primary_candidate": "Primary",
                "secondary_candidates": ["Secondary"],
                "reasoning": "Primary and secondary are strongest.",
            },
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        captions = [
            caption["content"]
            for call in fake.posts("connectors")
            for caption in call["json"].get("captions", [])
        ]
        self.assertEqual(captions, ["asks", "retrieves", "answers"])

    def test_no_evidence_cards_draws_no_answer_arrows_and_notes_audit(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(nodes=[], stages=["query", "answer"], summary={"reasoning": "No cited evidence."})

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        captions = [
            caption["content"]
            for call in fake.posts("connectors")
            for caption in call["json"].get("captions", [])
        ]
        self.assertEqual(captions, ["asks", "retrieves", "answers"])
        frame_titles = [call["json"]["data"]["title"] for call in fake.posts("frames")]
        self.assertNotIn("Precise Proof", frame_titles)

    def test_include_proof_renders_precise_proof_frame(self) -> None:
        fake = FakeMiroHTTP()
        trace = _trace(
            nodes=[
                {
                    "id": "n1",
                    "slug": "rows/a",
                    "label": "Candidate",
                    "stage": "cultivar",
                    "description": "Strong candidate with both markers.",
                },
                {"id": "n2", "slug": "rows/b", "label": "Field trial", "stage": "field_trials"},
            ],
            edges=[{"from": "n1", "to": "n2", "label": "validated by", "evidence": "Field trial passed in Texas Zone 8."}],
            stages=["cultivar", "field_trials"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board", include_proof=True, provenance_slug="provenance_traces/demo")

        frame_titles = [call["json"]["data"]["title"] for call in fake.posts("frames")]
        proof_text = "\n".join(call["json"]["data"]["content"] for call in fake.posts("texts"))
        self.assertIn("Precise Proof", frame_titles)
        self.assertIn("Strong candidate with both markers.", proof_text)
        self.assertIn("rows/a", proof_text)
        self.assertIn("Field trial passed in Texas Zone 8.", proof_text)

    def test_render_origin_is_below_all_existing_board_items(self) -> None:
        fake = FakeMiroHTTP(existing_items=[{"position": {"y": 500}, "geometry": {"height": 100}}])
        trace = _trace(
            nodes=[{"id": "n1", "slug": "rows/a", "label": "Node", "stage": "evidence"}],
            stages=["evidence"],
        )

        with _miro_env(), patch("requests.Session.request", new=fake):
            render_provenance_to_miro(trace, board_id="board")

        header_frame = fake.posts("frames")[0]["json"]
        self.assertEqual(header_frame["position"]["y"], 1290.0)

    def test_refresh_plan_preserves_header_frame_and_selects_stale_area(self) -> None:
        fake = FakeMiroHTTP(
            existing_frames=[
                {
                    "id": "header-frame",
                    "type": "frame",
                    "data": {"title": "DataRoot Provenance"},
                    "position": {"y": 100},
                    "geometry": {"height": 200},
                },
                {
                    "id": "old-frame",
                    "type": "frame",
                    "data": {"title": "CropProtectorAI"},
                    "position": {"y": 700},
                    "geometry": {"height": 300},
                },
            ],
            existing_items=[
                {
                    "id": "header-child",
                    "type": "shape",
                    "parent": {"id": "header-frame"},
                    "position": {"y": 700},
                    "geometry": {"height": 80},
                },
                {
                    "id": "old-child",
                    "type": "shape",
                    "parent": {"id": "old-frame"},
                    "position": {"y": 80},
                    "geometry": {"height": 40},
                },
                {"id": "loose-note", "type": "sticky_note", "position": {"y": 260}, "geometry": {"height": 50}},
                {"id": "old-connector", "type": "connector", "startItem": {"id": "old-child"}, "endItem": {"id": "loose-note"}},
            ],
        )

        with patch("requests.Session.request", new=fake):
            plan = plan_miro_board_refresh(
                MiroClient("token"),
                board_id="board",
                preserve_title="DataRoot Provenance",
            )

        delete_ids = {item["id"] for item in plan.items_to_delete}
        self.assertEqual(plan.preserved_frame_id, "header-frame")
        self.assertNotIn("header-frame", delete_ids)
        self.assertNotIn("header-child", delete_ids)
        self.assertEqual(delete_ids, {"old-frame", "old-child", "loose-note", "old-connector"})
        self.assertEqual(plan.frame_titles_to_delete, ("CropProtectorAI",))

    def test_delete_board_object_uses_frame_and_typed_delete_endpoints(self) -> None:
        fake = FakeMiroHTTP()

        with patch("requests.Session.request", new=fake):
            client = MiroClient("token")
            client.delete_board_object("board", {"id": "frame-1", "type": "frame"})
            client.delete_board_object("board", {"id": "connector-1", "type": "connector"})

        urls = [call["url"] for call in fake.deletes()]
        self.assertTrue(urls[0].endswith("/boards/board/frames/frame-1"))
        self.assertTrue(urls[1].endswith("/boards/board/connectors/connector-1"))

    def test_live_update_patches_flow_and_replaces_dynamic_evidence_only(self) -> None:
        fake = FakeMiroHTTP(
            existing_frames=[
                {
                    "id": "live-frame",
                    "type": "frame",
                    "data": {"title": "CropProtectorAI - Live Ask"},
                    "position": {"y": 900},
                    "geometry": {"height": 680},
                },
                {
                    "id": "old-stage",
                    "type": "frame",
                    "data": {"title": "Evidence"},
                    "position": {"y": 1800},
                    "geometry": {"height": 980},
                },
                {
                    "id": "old-audit",
                    "type": "frame",
                    "data": {"title": "Full Provenance Audit"},
                    "position": {"y": 2480},
                    "geometry": {"height": 280},
                },
                {
                    "id": "other-frame",
                    "type": "frame",
                    "data": {"title": "BioReactorAI - Live Ask"},
                    "position": {"y": 3300},
                    "geometry": {"height": 680},
                },
            ],
            existing_items=[
                _shape_item("question-shape", "Question", "live-frame"),
                _shape_item("retrieval-shape", "GitKB retrieval", "live-frame"),
                _shape_item("evidence-shape", "Evidence Path", "live-frame"),
                _shape_item("answer-shape", "Final Answer", "live-frame"),
                _shape_item("old-card", "Old evidence", "old-stage"),
                _text_item("audit-text", "Audit", "old-audit"),
                _shape_item("other-card", "Other evidence", "other-frame"),
            ],
            existing_connectors=[
                _connector_item("fixed-1", "question-shape", "retrieval-shape"),
                _connector_item("fixed-2", "retrieval-shape", "evidence-shape"),
                _connector_item("fixed-3", "evidence-shape", "answer-shape"),
                _connector_item("old-support", "old-card", "answer-shape"),
                _connector_item("other-support", "other-card", "other-answer"),
            ],
        )
        trace = _trace(
            nodes=[
                {"id": "n1", "slug": "rows/primary", "label": "Primary", "stage": "evidence"},
                {"id": "n2", "slug": "rows/secondary", "label": "Secondary", "stage": "evidence"},
                {"id": "n3", "slug": "rows/normal", "label": "Normal", "stage": "evidence"},
            ],
            summary={
                "primary_candidate": "Primary",
                "secondary_candidates": ["Secondary"],
                "reasoning": "Updated answer.",
            },
        )

        with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "DATAROOT_USE_MIRO_PLANNER": "0"}, clear=False):
            with patch("requests.Session.request", new=fake):
                render_provenance_to_miro(
                    trace,
                    board_id="board",
                    context_label="CropProtectorAI",
                    section_title="CropProtectorAI - Live Ask",
                    update_existing_section=True,
                    client=MiroClient("token"),
                )

        patched_shape_ids = [call["url"].rsplit("/", 1)[-1] for call in fake.patches("shapes")]
        self.assertEqual(patched_shape_ids, ["question-shape", "retrieval-shape", "evidence-shape", "answer-shape"])
        self.assertEqual(fake.patches("texts"), [])
        self.assertEqual([call["json"]["data"]["title"] for call in fake.posts("frames")], ["Evidence"])
        self.assertEqual(len(fake.posts("shapes")), 3)
        self.assertEqual(fake.posts("connectors"), [])

        deleted_urls = [call["url"] for call in fake.deletes()]
        self.assertTrue(any(url.endswith("/connectors/old-support") for url in deleted_urls))
        self.assertTrue(any(url.endswith("/shapes/old-card") for url in deleted_urls))
        self.assertTrue(any(url.endswith("/frames/old-stage") for url in deleted_urls))
        self.assertTrue(any(url.endswith("/frames/old-audit") for url in deleted_urls))
        self.assertFalse(any(url.endswith("/connectors/fixed-1") for url in deleted_urls))
        self.assertFalse(any(url.endswith("/shapes/other-card") for url in deleted_urls))

    def test_refresh_dry_run_does_not_delete_or_render(self) -> None:
        fake = FakeMiroHTTP(
            existing_frames=[
                {
                    "id": "header-frame",
                    "type": "frame",
                    "data": {"title": "DataRoot Provenance"},
                    "position": {"y": 100},
                    "geometry": {"height": 200},
                },
                {
                    "id": "old-frame",
                    "type": "frame",
                    "data": {"title": "BioReactorAI"},
                    "position": {"y": 600},
                    "geometry": {"height": 250},
                },
            ],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("requests.Session.request", new=fake):
                result = refresh_ask_board(
                    root=Path(temp_dir),
                    board_id="board",
                    preserve_title="DataRoot Provenance",
                    dry_run=True,
                    client=MiroClient("token"),
                )

        self.assertTrue(result.dry_run)
        self.assertEqual(len(result.plan.items_to_delete), 1)
        self.assertEqual(fake.deletes(), [])
        self.assertEqual(fake.posts("frames"), [])

    def test_refresh_live_run_creates_four_demo_sections_with_expected_questions(self) -> None:
        fake = FakeMiroHTTP(
            existing_frames=[
                {
                    "id": "header-frame",
                    "type": "frame",
                    "data": {"title": "DataRoot Provenance"},
                    "position": {"y": 100},
                    "geometry": {"height": 200},
                }
            ],
        )

        def answer_for_question(_store, question: str) -> str:
            trace = {
                "question": question,
                "nodes": [{"id": "n1", "slug": "rows/a", "label": "Evidence", "stage": "evidence"}],
                "edges": [],
                "stages": ["evidence"],
                "provenance_summary": {"reasoning": "Answer."},
            }
            return "\n".join(["Answer.", "<provenance>", json.dumps(trace), "</provenance>"])

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"DATAROOT_USE_TIDBIT_INTERPRETER": "0", "DATAROOT_USE_MIRO_PLANNER": "0"}, clear=False):
                with patch("requests.Session.request", new=fake):
                    with patch("dataroot.render.miro_refresh._workspace_store", return_value=None):
                        with patch("dataroot.render.miro_refresh.answer_question", side_effect=answer_for_question):
                            with patch(
                                "dataroot.render.miro_refresh.persist_answer_artifacts",
                                return_value={"inquiry": "inquiries/demo", "provenance_trace": "provenance_traces/demo"},
                            ):
                                result = refresh_ask_board(
                                    root=Path(temp_dir),
                                    board_id="board",
                                    preserve_title="DataRoot Provenance",
                                    dry_run=False,
                                    client=MiroClient("token"),
                                )

        frame_titles = [call["json"]["data"]["title"] for call in fake.posts("frames")]
        section_titles = [title for title in frame_titles if title.endswith(" Demo") or title.endswith(" Ask")]
        self.assertEqual(
            section_titles,
            [
                "CropProtectorAI - Standard Demo",
                "CropProtectorAI - Live Ask",
                "BioReactorAI - Standard Demo",
                "BioReactorAI - Live Ask",
            ],
        )
        self.assertEqual(frame_titles.count("Evidence"), 4)
        self.assertEqual(frame_titles.count("Precise Proof"), 0)
        self.assertEqual(
            [rendered.question for rendered in result.rendered],
            [
                "Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?",
                "What specific genes make Solara-14 powdery mildew resistant?",
                "Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?",
                "What are the next batches or runs coming out soon?",
            ],
        )

    def test_missing_token_raises_clean_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "MIRO_ACCESS_TOKEN"):
                render_provenance_to_miro(_trace(), board_id="board")

    def test_env_loader_sets_missing_values_without_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                "\n".join(
                    [
                        "MIRO_ACCESS_TOKEN=file-token",
                        "DATAROOT_KB_BACKEND=gitkb",
                        'QUOTED_VALUE="hello world"',
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "real-token"}, clear=True):
                config = load_config(root)
                self.assertEqual(config.kb_backend, "gitkb")
                self.assertEqual(os.environ["MIRO_ACCESS_TOKEN"], "real-token")
                self.assertEqual(os.environ["QUOTED_VALUE"], "hello world")

    def test_cli_reads_fenced_provenance_json_and_prints_board_url(self) -> None:
        fake = FakeMiroHTTP()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = LocalMarkdownStore(root / "kb")
            store.write(
                DocumentRecord(
                    doc_type="provenance_trace",
                    slug="provenance_traces/demo",
                    title="Demo trace",
                    frontmatter={},
                    body="\n".join(["# Provenance", "", "```json", json.dumps(_trace()), "```"]),
                )
            )
            with _cwd(root), _miro_env(), patch("dataroot.cli.make_store", return_value=store), patch("requests.Session.request", new=fake):
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    code = main(["miro", "provenance_traces/demo", "--board-id", "board"])

        self.assertEqual(code, 0)
        self.assertIn("https://miro.com/app/board/board/", buffer.getvalue())

    def test_agent_render_provenance_dispatches_to_miro_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalMarkdownStore(Path(temp_dir) / "kb")
            executor = ToolExecutor(store)
            trace = _trace()
            with patch("dataroot.render.miro.render_provenance_to_miro", return_value="https://miro.com/app/board/board/") as renderer:
                result = executor("render_provenance", {"mode": "miro", "trace": trace})

        self.assertEqual(result["status"], "rendered")
        self.assertEqual(result["url"], "https://miro.com/app/board/board/")
        renderer.assert_called_once()
        self.assertIs(renderer.call_args.args[0], trace)
        self.assertIs(renderer.call_args.kwargs["store"], store)


def _trace(
    nodes: list[dict] | None = None,
    edges: list[dict] | None = None,
    stages: list[str] | None = None,
    summary: dict | str | None = None,
) -> dict:
    return {
        "question": "Do we have a ready candidate?",
        "nodes": nodes if nodes is not None else [{"id": "n1", "slug": "rows/a", "label": "Candidate", "stage": "evidence"}],
        "edges": edges or [],
        "stages": stages or ["evidence"],
        "provenance_summary": summary if summary is not None else {"reasoning": "Candidate has supporting evidence."},
    }


def _shape_item(item_id: str, title: str, parent_id: str) -> dict:
    return {
        "id": item_id,
        "type": "shape",
        "parent": {"id": parent_id},
        "data": {"content": f"<p><strong>{title}</strong></p>"},
    }


def _text_item(item_id: str, title: str, parent_id: str) -> dict:
    return {
        "id": item_id,
        "type": "text",
        "parent": {"id": parent_id},
        "data": {"content": f"<p><strong>{title}</strong></p>"},
    }


def _connector_item(item_id: str, start_id: str, end_id: str) -> dict:
    return {
        "id": item_id,
        "type": "connector",
        "startItem": {"id": start_id},
        "endItem": {"id": end_id},
    }


@contextlib.contextmanager
def _miro_env():
    with patch.dict(os.environ, {"MIRO_ACCESS_TOKEN": "token", "MIRO_BOARD_ID": "board"}, clear=True):
        yield


@contextlib.contextmanager
def _cwd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
