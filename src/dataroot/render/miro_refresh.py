"""Refresh helpers for the shared DataRoot Miro demo board."""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path

from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.query import _extract_provenance, answer_question, persist_answer_artifacts
from dataroot.render.miro import (
    DEMO_SECTION_GAP,
    DEMO_SECTION_MIN_H,
    GROUP_GAP,
    MiroAPIError,
    MiroClient,
    miro_access_token_from_env,
    render_provenance_to_miro,
)


@dataclass(frozen=True)
class AskBoardDemo:
    company_key: str
    label: str
    section_kind: str
    raw_path: Path
    question: str
    trace_path: Path | None = None
    answer_path: Path | None = None

    @property
    def section_title(self) -> str:
        return f"{self.label} - {self.section_kind}"


@dataclass(frozen=True)
class RenderedDemo:
    label: str
    question: str
    board_url: str
    inquiry_slug: str
    provenance_slug: str


@dataclass(frozen=True)
class BoardRefreshPlan:
    board_id: str
    preserve_title: str
    preserved_frame: dict
    items_to_delete: tuple[dict, ...]

    @property
    def preserved_frame_id(self) -> str:
        return _item_id(self.preserved_frame)

    @property
    def preserved_frame_title(self) -> str:
        return _item_title(self.preserved_frame)

    @property
    def frame_titles_to_delete(self) -> tuple[str, ...]:
        frames = [item for item in self.items_to_delete if _item_type(item) == "frame"]
        frames.sort(key=lambda item: (_item_top(item), _item_id(item)))
        return tuple(_item_title(item) or _item_id(item) for item in frames)

    def deletion_order(self) -> list[dict]:
        return sorted(
            self.items_to_delete,
            key=lambda item: (_delete_priority(item), -_item_bottom(item), _item_id(item)),
        )


@dataclass(frozen=True)
class BoardRefreshResult:
    plan: BoardRefreshPlan
    dry_run: bool
    deleted_count: int = 0
    rendered: tuple[RenderedDemo, ...] = ()


DEFAULT_ASK_BOARD_DEMOS = (
    AskBoardDemo(
        company_key="company_a",
        label="CropProtectorAI",
        section_kind="Standard Demo",
        raw_path=Path("ExampleData") / "CompanyA_AgriTrait" / "raw",
        question="Do we have a tomato line that is drought tolerant and powdery mildew resistant, and is it ready for spring planting?",
        trace_path=Path("ExampleData") / "CompanyA_AgriTrait" / "provenance_targets" / "A-INQ-001_trace.json",
        answer_path=Path("ExampleData") / "CompanyA_AgriTrait" / "expected_answers" / "A-INQ-001_expected_answer.md",
    ),
    AskBoardDemo(
        company_key="company_a",
        label="CropProtectorAI",
        section_kind="Live Ask",
        raw_path=Path("ExampleData") / "CompanyA_AgriTrait" / "raw",
        question="What specific genes make Solara-14 powdery mildew resistant?",
    ),
    AskBoardDemo(
        company_key="company_b",
        label="BioReactorAI",
        section_kind="Standard Demo",
        raw_path=Path("ExampleData") / "CompanyB_Fermentation" / "raw",
        question="Which microbial strain can produce a fruit-forward citrus-like ester profile under low-temperature fermentation, and can we scale it soon?",
        trace_path=Path("ExampleData") / "CompanyB_Fermentation" / "provenance_targets" / "B-INQ-001_trace.json",
        answer_path=Path("ExampleData") / "CompanyB_Fermentation" / "expected_answers" / "B-INQ-001_expected_answer.md",
    ),
    AskBoardDemo(
        company_key="company_b",
        label="BioReactorAI",
        section_kind="Live Ask",
        raw_path=Path("ExampleData") / "CompanyB_Fermentation" / "raw",
        question="What are the next batches or runs coming out soon?",
    ),
)


def refresh_ask_board(
    *,
    root: Path,
    board_id: str,
    preserve_title: str = "DataRoot Provenance",
    dry_run: bool = False,
    client: MiroClient | None = None,
) -> BoardRefreshResult:
    token = miro_access_token_from_env()
    if client is None and not token:
        raise RuntimeError("MIRO_ACCESS_TOKEN is required to refresh a Miro board.")

    client = client or MiroClient(token=token or "")
    plan = plan_miro_board_refresh(client, board_id=board_id, preserve_title=preserve_title)
    if dry_run:
        return BoardRefreshResult(plan=plan, dry_run=True)

    deleted_count = 0
    for item in plan.deletion_order():
        client.delete_board_object(board_id, item)
        deleted_count += 1

    rendered = []
    section_top = _item_bottom(plan.preserved_frame) + GROUP_GAP
    for demo in DEFAULT_ASK_BOARD_DEMOS:
        store = _workspace_store(root, demo)
        answer, trace = _answer_and_trace_for_demo(root, store, demo)
        artifacts = persist_answer_artifacts(store, demo.question, answer)
        board_url = render_provenance_to_miro(
            trace,
            store=store,
            inquiry_slug=artifacts["inquiry"],
            board_id=board_id,
            provenance_slug=artifacts["provenance_trace"],
            context_label=demo.label,
            section_title=demo.section_title,
            section_top=section_top,
            client=client,
        )
        rendered.append(
            RenderedDemo(
                label=demo.section_title,
                question=demo.question,
                board_url=board_url,
                inquiry_slug=artifacts["inquiry"],
                provenance_slug=artifacts["provenance_trace"],
            )
        )
        section_top += DEMO_SECTION_MIN_H + DEMO_SECTION_GAP

    return BoardRefreshResult(
        plan=plan,
        dry_run=False,
        deleted_count=deleted_count,
        rendered=tuple(rendered),
    )


def _answer_and_trace_for_demo(root: Path, store: LocalMarkdownStore, demo: AskBoardDemo) -> tuple[str, dict]:
    if demo.trace_path:
        trace_file = root / demo.trace_path
        if trace_file.exists():
            trace = json.loads(trace_file.read_text(encoding="utf-8"))
            answer = _canonical_answer_text(root, demo, trace)
            return answer, trace

    answer = answer_question(store, demo.question)
    return answer, _extract_provenance(answer)


def _canonical_answer_text(root: Path, demo: AskBoardDemo, trace: dict) -> str:
    answer_body = ""
    if demo.answer_path:
        answer_file = root / demo.answer_path
        if answer_file.exists():
            answer_body = answer_file.read_text(encoding="utf-8").strip()
    if not answer_body:
        summary = trace.get("provenance_summary") if isinstance(trace.get("provenance_summary"), dict) else {}
        answer_body = "\n".join(
            [
                f"Question: {demo.question}",
                "",
                str(summary.get("reasoning") or "DataRoot found a cited evidence path for this standard demo."),
            ]
        )
    return "\n".join(
        [
            answer_body,
            "",
            "<provenance>",
            json.dumps(trace, indent=2),
            "</provenance>",
        ]
    )


def plan_miro_board_refresh(client: MiroClient, *, board_id: str, preserve_title: str) -> BoardRefreshPlan:
    objects = _list_board_objects(client, board_id)
    preserved_frame = _find_preserved_frame(objects, preserve_title)
    protected_ids = _protected_ids(objects, _item_id(preserved_frame))
    cutoff_y = _item_bottom(preserved_frame)

    selected_ids = {
        _item_id(item)
        for item in objects
        if _item_id(item) not in protected_ids and _is_below_cutoff(item, cutoff_y)
    }
    selected_ids.discard("")

    changed = True
    while changed:
        changed = False
        for item in objects:
            item_id = _item_id(item)
            if not item_id or item_id in protected_ids or item_id in selected_ids:
                continue
            parent_id = _parent_id(item)
            endpoint_ids = _connector_endpoint_ids(item)
            if parent_id in selected_ids or any(endpoint_id in selected_ids for endpoint_id in endpoint_ids):
                selected_ids.add(item_id)
                changed = True

    items_to_delete = tuple(item for item in objects if _item_id(item) in selected_ids)
    return BoardRefreshPlan(
        board_id=board_id,
        preserve_title=preserve_title,
        preserved_frame=preserved_frame,
        items_to_delete=items_to_delete,
    )


def _workspace_store(root: Path, demo: AskBoardDemo) -> LocalMarkdownStore:
    store = LocalMarkdownStore(root / ".dataroot" / "server_cache" / demo.company_key / "kb")
    raw_path = (root / demo.raw_path).resolve()
    existing_records = store.list()
    if not existing_records:
        profile_workspace(raw_path, store)
        link_workspace(store)
    elif not any(record.doc_type == "relationship" for record in existing_records):
        link_workspace(store)
    return store


def _list_board_objects(client: MiroClient, board_id: str) -> list[dict]:
    objects: list[dict] = []
    seen: set[str] = set()

    for frame in client.list_frames(board_id):
        normalized = dict(frame)
        normalized.setdefault("type", "frame")
        item_id = _item_id(normalized)
        if item_id and item_id not in seen:
            objects.append(normalized)
            seen.add(item_id)

    for item in client.list_items(board_id):
        item_id = _item_id(item)
        if item_id and item_id not in seen:
            objects.append(item)
            seen.add(item_id)

    for connector in _optional_connectors(client, board_id):
        normalized = dict(connector)
        normalized.setdefault("type", "connector")
        item_id = _item_id(normalized)
        if item_id and item_id not in seen:
            objects.append(normalized)
            seen.add(item_id)

    return objects


def _optional_connectors(client: MiroClient, board_id: str):
    try:
        yield from client.list_connectors(board_id)
    except MiroAPIError as exc:
        if exc.status_code not in {404, 405}:
            raise


def _find_preserved_frame(objects: list[dict], preserve_title: str) -> dict:
    matches = [
        item
        for item in objects
        if _item_type(item) == "frame" and _item_title(item).strip() == preserve_title
    ]
    if not matches:
        raise RuntimeError(f'No frame titled "{preserve_title}" was found on the Miro board.')
    matches.sort(key=lambda item: (_item_top(item), _item_id(item)))
    return matches[0]


def _protected_ids(objects: list[dict], preserved_frame_id: str) -> set[str]:
    protected = {preserved_frame_id}
    changed = True
    while changed:
        changed = False
        for item in objects:
            item_id = _item_id(item)
            if not item_id or item_id in protected:
                continue
            if _parent_id(item) in protected:
                protected.add(item_id)
                changed = True
    return protected


def _is_below_cutoff(item: dict, cutoff_y: float) -> bool:
    if _item_type(item) == "connector" and not _has_position(item):
        return False
    return _item_top(item) >= cutoff_y


def _has_position(item: dict) -> bool:
    return "y" in (item.get("position") or {})


def _delete_priority(item: dict) -> int:
    item_type = _item_type(item)
    if item_type == "connector":
        return 0
    if item_type == "frame":
        return 2
    return 1


def _item_id(item: dict) -> str:
    value = item.get("id") or item.get("data", {}).get("id")
    return str(value) if value else ""


def _item_type(item: dict) -> str:
    return str(item.get("type") or item.get("data", {}).get("type") or "").strip()


def _item_title(item: dict) -> str:
    data = item.get("data") or {}
    return str(item.get("title") or data.get("title") or "").strip()


def _parent_id(item: dict) -> str:
    parent = item.get("parent") or {}
    value = parent.get("id") or item.get("parentId") or item.get("parent_id")
    return str(value) if value else ""


def _connector_endpoint_ids(item: dict) -> tuple[str, ...]:
    endpoints = []
    for key in ("startItem", "endItem"):
        endpoint = item.get(key) or {}
        value = endpoint.get("id")
        if value:
            endpoints.append(str(value))
    return tuple(endpoints)


def _item_top(item: dict) -> float:
    return _item_y(item) - _item_height(item) / 2


def _item_bottom(item: dict) -> float:
    return _item_y(item) + _item_height(item) / 2


def _item_y(item: dict) -> float:
    position = item.get("position") or {}
    return _float(position.get("y"))


def _item_height(item: dict) -> float:
    geometry = item.get("geometry") or {}
    return _float(geometry.get("height"))


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
