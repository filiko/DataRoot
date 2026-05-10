"""Miro REST renderer for DataRoot provenance traces."""

from __future__ import annotations

import html
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterator

import requests

from dataroot.render.miro_plan import BoardCard, BoardPlan, plan_miro_board


FRAME_W = 800
FRAME_H = 1200
FRAME_GAP = 100
HEADER_H = 160
HEADER_TO_LANES_GAP = 60
GROUP_GAP = 400
SHAPE_W = 300
SHAPE_H = 84
SHAPE_PADDING_TOP = 88
SHAPE_GAP = 28
SHAPE_X_OFFSET = 220
NOTE_X_OFFSET = 310
NOTE_W = 260
MAX_NOTE_CHARS = 260
MAX_EDGE_NOTE_CHARS = 220
STORY_FRAME_W = 3200
STORY_FRAME_GAP = 80
STORY_HEADER_H = 300
STORY_FLOW_H = 360
STORY_LANE_W = 860
STORY_LANE_H = 980
STORY_AUDIT_H = 280
STORY_CARD_W = 640
STORY_CARD_H = 176
STORY_CARD_GAP = 52
DEMO_SECTION_W = 3200
DEMO_SECTION_MIN_H = 2060
DEMO_SECTION_GAP = 140
DEMO_TOP_FRAME_H = 760
DEMO_FLOW_Y = 270
DEMO_QUESTION_X = 390
DEMO_RETRIEVAL_X = 1180
DEMO_EVIDENCE_X = 1970
DEMO_ANSWER_Y = 590
DEMO_FLOW_SHAPE_W = 640
DEMO_FLOW_SHAPE_H = 170
DEMO_ANSWER_SHAPE_H = 300
DEMO_EVIDENCE_CARD_W = 640
DEMO_EVIDENCE_CARD_H = 220
DEMO_EVIDENCE_CARD_GAP_X = 70
DEMO_EVIDENCE_CARD_GAP_Y = 52
DEMO_EVIDENCE_TOP = 500
DEMO_EVIDENCE_LEFT = 1020
DEMO_EVIDENCE_COLUMNS = 3
DEMO_AUDIT_H = 150
DEMO_PROOF_MIN_H = 260
DEMO_PROOF_ROW_H = 84
DEMO_FLOW_FONT_SIZE = 24
DEMO_CARD_FONT_SIZE = 20
DEMO_TEXT_FONT_SIZE = 20
DEMO_TITLE_FONT_SIZE = 30
DEMO_TITLE_X = 960
DEMO_TITLE_Y = 70
DEMO_TITLE_W = 1760
DEMO_SYMBOL_Y = 155
DEMO_SYMBOL_W = 116
DEMO_SYMBOL_H = 82
DEMO_VISUAL_X = 2770
DEMO_VISUAL_Y = 245
DEMO_VISUAL_W = 520
DEMO_VISUAL_H = 245
DEMO_LEGEND_X = 2770
DEMO_LEGEND_Y = 530
DEMO_LEGEND_W = 520
DEMO_LEGEND_H = 145
DEMO_ASK_INPUT_X = DEMO_RETRIEVAL_X
DEMO_ASK_INPUT_Y = DEMO_ANSWER_Y
DEMO_ASK_INPUT_W = DEMO_FLOW_SHAPE_W
DEMO_ASK_INPUT_LABEL = "Type your question here:"
DEMO_ASK_INPUT_DEFAULT_QUESTION = ""
DEMO_ASK_INPUT_HTML = (
    f"<p><strong>{html.escape(DEMO_ASK_INPUT_LABEL)}</strong></p>"
    f"<p>{html.escape(DEMO_ASK_INPUT_DEFAULT_QUESTION)}</p>"
)
DEMO_LIVE_ASK_RUN_X = 2770
DEMO_LIVE_ASK_RUN_Y = 625
DEMO_LIVE_ASK_RUN_W = 520
DEMO_LIVE_ASK_RUN_H = 112
DEMO_LIVE_ASK_RUN_HTML = (
    "<p><strong>DataRoot Run Live Ask</strong></p>"
    "<p><small>Root submit action</small></p>"
)
DEMO_PROOF_FRAME_TITLE = "Sources / Precise Proof"
FIXED_FLOW_TITLES = {
    "question": "Question",
    "retrieval": "GitKB retrieval",
    "evidence": "Evidence Path",
    "answer": "Final Answer",
}
DEMO_FLOW_CONNECTORS = (
    ("question", "answer", "answers", "bottom", "top"),
    ("question", "retrieval", "asks", "right", "left"),
    ("retrieval", "evidence", "retrieves", "right", "left"),
    ("evidence", "answer", "grounds", "bottom", "right"),
)
DEMO_ASK_INPUT_PLACEHOLDERS = {
    "",
    "type your question here",
    "type your question here:",
    "ask your question",
    "enter your question",
    "what specific genes make solara-14 powdery mildew resistant?",
}
STORY_FLOW_CONNECTORS = (
    ("question", "retrieval", "asks", "right", "left"),
    ("retrieval", "evidence", "retrieves", "right", "left"),
    ("evidence", "answer", "answers", "right", "left"),
)

STAGE_COLORS = {
    "query": "#d0e8ff",
    "answer": "#ffd6d6",
    "cultivar": "#d4f5d4",
    "cultivars": "#d4f5d4",
    "strain": "#d4f5d4",
    "greenhouse_trials": "#ffe5b4",
    "fermentation_runs": "#ffe5b4",
    "field_trials": "#fffac8",
    "assays": "#fffac8",
    "inventory": "#e8d4f5",
    "qc": "#e8d4f5",
    "field_readiness": "#ffd6e7",
    "bioreactor": "#ffd6e7",
    "row_group": "#eaeaea",
    "evidence": "#eaeaea",
}

ICONIFY_BASE = "https://api.iconify.design"
FLOW_ICON_URLS = {
    "files": f"{ICONIFY_BASE}/material-symbols/folder-data-rounded.svg?color=%23175cd3",
    "kb":    f"{ICONIFY_BASE}/material-symbols/hub-rounded.svg?color=%236941c6",
    "agent": f"{ICONIFY_BASE}/material-symbols/smart-toy-rounded.svg?color=%23b54708",
    "proof": f"{ICONIFY_BASE}/material-symbols/fact-check-rounded.svg?color=%23027a48",
}
PICTOGRAM_ICON_URLS = {
    "sprout": f"{ICONIFY_BASE}/mdi/sprout.svg?color=%23079455",
    "scope":  f"{ICONIFY_BASE}/mdi/microscope.svg?color=%231570ef",
    "dna":    f"{ICONIFY_BASE}/mdi/dna.svg?color=%237f56d9",
    "flask":  f"{ICONIFY_BASE}/mdi/flask-round-bottom.svg?color=%23026aa2",
    "tube":   f"{ICONIFY_BASE}/mdi/test-tube.svg?color=%23b54708",
    "check":  f"{ICONIFY_BASE}/mdi/check-circle-outline.svg?color=%23027a48",
    "files":  f"{ICONIFY_BASE}/mdi/file-multiple.svg?color=%23175cd3",
    "graph":  f"{ICONIFY_BASE}/mdi/graph.svg?color=%236941c6",
    "cert":   f"{ICONIFY_BASE}/mdi/file-certificate.svg?color=%23027a48",
}

MIRO_ACCESS_TOKEN_PLACEHOLDERS = {
    "optional_miro_token",
    "optional_miro_access_token",
    "your_miro_token",
    "your_miro_token_here",
    "your_miro_access_token",
    "your_miro_access_token_here",
    "your_miro_oauth_access_token_here",
}


@dataclass
class MiroAPIError(RuntimeError):
    """Raised when the Miro REST API rejects a request."""

    status_code: int
    body: str

    def __str__(self) -> str:
        return f"Miro API request failed with status {self.status_code}: {self.body}"


class MiroClient:
    """Thin wrapper around the Miro REST API v2."""

    BASE = "https://api.miro.com/v2"

    def __init__(self, token: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def list_items(self, board_id: str) -> Iterator[dict]:
        yield from self._paginated("GET", f"/boards/{board_id}/items")

    def list_frames(self, board_id: str) -> Iterator[dict]:
        yield from self._paginated("GET", f"/boards/{board_id}/frames")

    def list_connectors(self, board_id: str) -> Iterator[dict]:
        yield from self._paginated("GET", f"/boards/{board_id}/connectors")

    def create_frame(self, board_id: str, *, title: str, x: float, y: float, w: float, h: float) -> str:
        payload = {
            "data": {"title": title, "format": "custom", "type": "freeform"},
            "style": {"fillColor": "#ffffff"},
            "geometry": {"width": w, "height": h},
            "position": {"x": x, "y": y, "origin": "center"},
        }
        return self._created_id(self._request("POST", f"/boards/{board_id}/frames", json=payload))

    def create_shape(
        self,
        board_id: str,
        *,
        content: str,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_color: str,
        parent_id: str,
        border_color: str = "#1a1a1a",
        border_width: int = 2,
        font_size: int = 14,
        shape: str = "rectangle",
        text_align: str = "center",
        text_align_vertical: str = "middle",
        text_color: str = "#1a1a1a",
    ) -> str:
        payload = {
            "data": {"shape": shape, "content": content},
            "style": {
                "fillColor": fill_color,
                "borderColor": border_color,
                "borderWidth": border_width,
                "fontSize": font_size,
                "textAlign": text_align,
                "textAlignVertical": text_align_vertical,
                "color": text_color,
            },
            "geometry": {"width": w, "height": h},
            "position": {"x": x, "y": y, "origin": "center"},
            "parent": {"id": parent_id},
        }
        return self._created_id(self._request("POST", f"/boards/{board_id}/shapes", json=payload))

    def create_image(
        self,
        board_id: str,
        *,
        image_url: str,
        title: str,
        x: float,
        y: float,
        w: float,
        h: float,
        parent_id: str,
    ) -> str:
        payload = {
            "data": {"url": image_url, "title": title},
            "geometry": {"width": w},
            "position": {"x": x, "y": y, "origin": "center"},
            "parent": {"id": parent_id},
        }
        return self._created_id(self._request("POST", f"/boards/{board_id}/images", json=payload))

    def create_sticky(
        self,
        board_id: str,
        *,
        content: str,
        x: float,
        y: float,
        width: float = NOTE_W,
        parent_id: str | None = None,
        fill_color: str = "light_yellow",
    ) -> str:
        payload: dict[str, Any] = {
            "data": {"content": content, "shape": "square"},
            "style": {"fillColor": fill_color, "textAlign": "left"},
            "geometry": {"width": width},
            "position": {"x": x, "y": y, "origin": "center"},
        }
        if parent_id:
            payload["parent"] = {"id": parent_id}
        return self._created_id(self._request("POST", f"/boards/{board_id}/sticky_notes", json=payload))

    def create_text(
        self,
        board_id: str,
        *,
        content: str,
        x: float,
        y: float,
        w: float,
        parent_id: str,
        font_size: int = 14,
        color: str = "#1a1a1a",
        text_align: str = "left",
    ) -> str:
        payload = {
            "data": {"content": content},
            "style": {"color": color, "fontSize": font_size, "textAlign": text_align},
            "geometry": {"width": w},
            "position": {"x": x, "y": y, "origin": "center"},
            "parent": {"id": parent_id},
        }
        return self._created_id(self._request("POST", f"/boards/{board_id}/texts", json=payload))

    def create_connector(
        self,
        board_id: str,
        *,
        start_id: str,
        end_id: str,
        caption: str,
        shape: str = "elbowed",
        start_snap_to: str = "auto",
        end_snap_to: str = "auto",
    ) -> str:
        payload = {
            "startItem": {"id": start_id, "snapTo": start_snap_to},
            "endItem": {"id": end_id, "snapTo": end_snap_to},
            "shape": shape,
            "captions": [{"content": caption}] if caption else [],
            "style": {"strokeColor": "#1a1a1a", "strokeWidth": 2, "endStrokeCap": "arrow"},
        }
        return self._created_id(self._request("POST", f"/boards/{board_id}/connectors", json=payload))

    def update_shape(self, board_id: str, shape_id: str, *, content: str | None = None) -> None:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["data"] = {"content": content}
        if payload:
            self._request("PATCH", f"/boards/{board_id}/shapes/{shape_id}", json=payload)

    def update_text(self, board_id: str, text_id: str, *, content: str | None = None) -> None:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["data"] = {"content": content}
        if payload:
            self._request("PATCH", f"/boards/{board_id}/texts/{text_id}", json=payload)

    def update_connector(
        self,
        board_id: str,
        connector_id: str,
        *,
        caption: str | None = None,
        shape: str | None = None,
        start_id: str | None = None,
        end_id: str | None = None,
        start_snap_to: str | None = None,
        end_snap_to: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {}
        if caption is not None:
            payload["captions"] = [{"content": caption}] if caption else []
        if shape is not None:
            payload["shape"] = shape
        if start_id is not None:
            payload["startItem"] = _connector_endpoint_payload(start_id, start_snap_to)
        if end_id is not None:
            payload["endItem"] = _connector_endpoint_payload(end_id, end_snap_to)
        if payload:
            self._request("PATCH", f"/boards/{board_id}/connectors/{connector_id}", json=payload)

    def delete_frame(self, board_id: str, frame_id: str) -> None:
        self._request("DELETE", f"/boards/{board_id}/frames/{frame_id}")

    def delete_item(self, board_id: str, item_id: str, item_type: str | None = None) -> None:
        paths = _delete_paths(board_id, item_id, item_type)
        last_error: MiroAPIError | None = None
        for path in paths:
            try:
                self._request("DELETE", path)
                return
            except MiroAPIError as exc:
                if exc.status_code not in {404, 405}:
                    raise
                last_error = exc
        if last_error:
            raise last_error

    def delete_board_object(self, board_id: str, item: dict) -> None:
        item_id = _item_id(item)
        if not item_id:
            raise RuntimeError(f"Miro item is missing an id: {item}")
        item_type = _item_type(item)
        if item_type == "frame":
            self.delete_frame(board_id, item_id)
        else:
            self.delete_item(board_id, item_id, item_type=item_type)

    def _paginated(self, method: str, path: str) -> Iterator[dict]:
        cursor = None
        while True:
            params = {"limit": 50}
            if cursor:
                params["cursor"] = cursor
            payload = self._request(method, path, params=params)
            for item in payload.get("data", []):
                yield item
            cursor = payload.get("cursor") or payload.get("nextCursor")
            if not cursor:
                break

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            response = self.session.request(
                method,
                f"{self.BASE}{path}",
                headers=self.headers,
                timeout=30,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Miro API request failed: {exc}") from exc
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = getattr(response, "text", "")
            print(f"Miro API error {response.status_code}: {body}", file=sys.stderr)
            raise MiroAPIError(response.status_code, body) from exc
        if not getattr(response, "content", b""):
            return {}
        return response.json()

    @staticmethod
    def _created_id(payload: dict) -> str:
        item_id = payload.get("id") or payload.get("data", {}).get("id")
        if not item_id:
            raise RuntimeError(f"Miro response did not include an item id: {payload}")
        return str(item_id)


def miro_access_token_from_env() -> str | None:
    token = (os.environ.get("MIRO_ACCESS_TOKEN") or "").strip()
    normalized = token.lower()
    if not token or normalized in MIRO_ACCESS_TOKEN_PLACEHOLDERS or normalized.startswith("optional_"):
        return None
    return token


def _delete_paths(board_id: str, item_id: str, item_type: str | None) -> list[str]:
    typed_endpoint = {
        "app_card": "app_cards",
        "card": "cards",
        "connector": "connectors",
        "document": "documents",
        "embed": "embeds",
        "image": "images",
        "shape": "shapes",
        "sticky_note": "sticky_notes",
        "text": "texts",
    }.get(item_type or "")
    paths = []
    if typed_endpoint:
        paths.append(f"/boards/{board_id}/{typed_endpoint}/{item_id}")
    paths.append(f"/boards/{board_id}/items/{item_id}")
    return list(dict.fromkeys(paths))


def _item_id(item: dict) -> str | None:
    value = item.get("id") or item.get("data", {}).get("id")
    return str(value) if value else None


def _item_type(item: dict) -> str:
    return str(item.get("type") or item.get("data", {}).get("type") or "").strip()


def _item_title(item: dict) -> str:
    data = item.get("data") or {}
    return str(item.get("title") or data.get("title") or "").strip()


def _parent_id(item: dict) -> str:
    parent = item.get("parent") or {}
    value = parent.get("id") or item.get("parentId") or item.get("parent_id")
    return str(value) if value else ""


def _item_content(item: dict) -> str:
    data = item.get("data") or {}
    return str(data.get("content") or item.get("content") or "")


def plain_miro_item_text(item: dict) -> str:
    """Return readable text from a Miro item content payload."""

    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(_item_content(item))).split())


def is_live_ask_question_input(item: dict) -> bool:
    return DEMO_ASK_INPUT_LABEL.lower() in plain_miro_item_text(item).lower()


def extract_live_ask_question_text(item: dict) -> str:
    text = plain_miro_item_text(item).strip()
    if not text:
        return ""

    label_match = re.search(re.escape(DEMO_ASK_INPUT_LABEL), text, flags=re.IGNORECASE)
    if label_match:
        text = text[label_match.end() :]

    question = text.strip(" \t\r\n:-")
    if question.lower() in DEMO_ASK_INPUT_PLACEHOLDERS:
        return ""
    return question


def _connector_endpoint_ids(item: dict) -> tuple[str, str]:
    endpoints = []
    for key in ("startItem", "endItem"):
        endpoint = item.get(key) or {}
        endpoints.append(str(endpoint.get("id") or ""))
    return (endpoints[0], endpoints[1])


def _connector_endpoint_payload(item_id: str, snap_to: str | None) -> dict[str, str]:
    payload = {"id": item_id}
    if snap_to is not None:
        payload["snapTo"] = snap_to
    return payload


def render_provenance_to_miro(
    trace: dict,
    *,
    store=None,
    inquiry_slug: str | None = None,
    board_id: str | None = None,
    provenance_slug: str | None = None,
    context_label: str | None = None,
    client: MiroClient | None = None,
    section_title: str | None = None,
    section_top: float | None = None,
    update_existing_section: bool = False,
    include_proof: bool = False,
    plan: BoardPlan | None = None,
    render_metadata: dict[str, str] | None = None,
) -> str:
    """Render a saved DataRoot provenance trace to Miro and return the board URL."""

    if not isinstance(trace, dict):
        raise TypeError("trace must be a dict")

    token = miro_access_token_from_env()
    if client is None and not token:
        raise RuntimeError("MIRO_ACCESS_TOKEN is required to render provenance to Miro.")

    board_id = board_id or os.environ.get("MIRO_BOARD_ID")
    if not board_id:
        raise RuntimeError("MIRO_BOARD_ID is required unless --board-id is provided.")

    client = client or MiroClient(token=token or "")
    plan = plan or plan_miro_board(trace, store=store, inquiry_slug=inquiry_slug, context_label=context_label)
    if render_metadata is not None:
        render_metadata["interpreter_source"] = plan.interpreter_source
        render_metadata["planner_source"] = plan.planner_source
        render_metadata["proof_included"] = "true" if include_proof else "false"
    title = section_title or plan.context_label
    if update_existing_section:
        section_status = _update_demo_section(
            client,
            board_id,
            plan,
            trace=trace,
            section_title=title,
            provenance_slug=provenance_slug,
            include_proof=include_proof,
        )
    else:
        group_top = _next_group_top(client, board_id) if section_top is None else section_top
        _render_demo_section(
            client,
            board_id,
            plan,
            trace=trace,
            section_title=title,
            group_top=group_top,
            provenance_slug=provenance_slug,
            include_proof=include_proof,
        )
        section_status = "created"
    if render_metadata is not None:
        render_metadata["section_status"] = section_status
    return f"https://miro.com/app/board/{board_id}/"


def clear_live_ask_section_to_miro(
    *,
    board_id: str | None = None,
    section_title: str,
    client: MiroClient | None = None,
) -> str:
    """Clear the visible Live Ask answer state while preserving the board input."""

    token = miro_access_token_from_env()
    if client is None and not token:
        raise RuntimeError("MIRO_ACCESS_TOKEN is required to clear Live Ask state.")

    board_id = board_id or os.environ.get("MIRO_BOARD_ID")
    if not board_id:
        raise RuntimeError("MIRO_BOARD_ID is required unless --board-id is provided.")

    client = client or MiroClient(token=token or "")
    section = _find_section_frame(client, board_id, section_title)
    section_id = _item_id(section)
    items = list(client.list_items(board_id))
    frames = list(client.list_frames(board_id))
    connectors = _list_connectors_or_empty(client, board_id)
    children = [item for item in items if _parent_id(item) == section_id]
    flow_ids = _fixed_flow_shape_ids(children)
    missing = [FIXED_FLOW_TITLES[key] for key in ("question", "retrieval", "evidence", "answer") if key not in flow_ids]
    if missing:
        raise RuntimeError(f"Live Ask section is missing fixed board state cards: {', '.join(missing)}")

    for key in ("question", "retrieval", "evidence", "answer"):
        client.update_shape(board_id, flow_ids[key], content=_flow_html(FIXED_FLOW_TITLES[key], ""))

    _delete_dynamic_section_area(
        client,
        board_id,
        section=section,
        frames=frames,
        items=items,
        connectors=connectors,
    )
    return f"https://miro.com/app/board/{board_id}/"


def _render_demo_section(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    trace: dict,
    section_title: str,
    group_top: float,
    provenance_slug: str | None,
    include_proof: bool,
) -> None:
    total_width = _demo_section_width(plan)
    section_id = client.create_frame(
        board_id,
        title=section_title,
        x=total_width / 2,
        y=group_top + DEMO_TOP_FRAME_H / 2,
        w=total_width,
        h=DEMO_TOP_FRAME_H,
    )
    selected_support_cards = _selected_answer_support_cards(plan)
    _record_answer_support_audit(plan, selected_support_cards)
    top_x_offset = _demo_top_x_offset(total_width)
    flow_ids = _render_demo_skeleton(client, board_id, plan, section_id, x_offset=top_x_offset)
    _ensure_demo_story_items(
        client,
        board_id,
        plan,
        section_title=section_title,
        section_id=section_id,
        children=[],
        x_offset=top_x_offset,
    )
    _ensure_live_ask_question_input(
        client,
        board_id,
        section_title=section_title,
        section_id=section_id,
        children=[],
        x_offset=top_x_offset,
    )
    evidence_shape_ids = _render_demo_segments(
        client,
        board_id,
        plan,
        group_top=group_top,
        total_width=total_width,
    )
    _render_answer_support_connectors(
        client,
        board_id,
        evidence_shape_ids=evidence_shape_ids,
        selected_support_cards=selected_support_cards,
        answer_shape_id=flow_ids["answer"],
    )
    if include_proof:
        _render_precise_proof_frame(
            client,
            board_id,
            plan,
            trace=trace,
            provenance_slug=provenance_slug,
            group_top=group_top,
            total_width=total_width,
        )


def _update_demo_section(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    trace: dict,
    section_title: str,
    provenance_slug: str | None,
    include_proof: bool,
) -> str:
    section = _find_section_frame_or_none(client, board_id, section_title)
    if section is None:
        group_top = _next_group_top(client, board_id)
        _render_demo_section(
            client,
            board_id,
            plan,
            trace=trace,
            section_title=section_title,
            group_top=group_top,
            provenance_slug=provenance_slug,
            include_proof=include_proof,
        )
        return "created"

    section_id = _item_id(section)
    items = list(client.list_items(board_id))
    frames = list(client.list_frames(board_id))
    connectors = _list_connectors_or_empty(client, board_id)
    children = [item for item in items if _parent_id(item) == section_id]
    flow_ids = _fixed_flow_shape_ids(children)
    missing = [FIXED_FLOW_TITLES[key] for key in ("question", "retrieval", "evidence", "answer") if key not in flow_ids]
    if missing:
        section_top = _item_top_global(section)
        _delete_demo_section_area(
            client,
            board_id,
            section=section,
            frames=frames,
            items=items,
            connectors=connectors,
        )
        _render_demo_section(
            client,
            board_id,
            plan,
            trace=trace,
            section_title=section_title,
            group_top=section_top,
            provenance_slug=provenance_slug,
            include_proof=include_proof,
        )
        return "repaired"

    selected_support_cards = _selected_answer_support_cards(plan)
    _record_answer_support_audit(plan, selected_support_cards)
    total_width = _demo_section_width(plan)
    top_x_offset = _demo_top_x_offset(total_width)
    client.update_shape(board_id, flow_ids["question"], content=_demo_question_html(plan))
    client.update_shape(board_id, flow_ids["retrieval"], content=_demo_retrieval_html(plan))
    client.update_shape(board_id, flow_ids["evidence"], content=_demo_evidence_html(plan))
    client.update_shape(board_id, flow_ids["answer"], content=_demo_answer_html(plan))
    _ensure_demo_story_items(
        client,
        board_id,
        plan,
        section_title=section_title,
        section_id=section_id,
        children=children,
        x_offset=top_x_offset,
    )
    _ensure_live_ask_question_input(
        client,
        board_id,
        section_title=section_title,
        section_id=section_id,
        children=children,
        x_offset=top_x_offset,
    )
    _normalize_demo_flow_connectors(client, board_id, flow_ids, connectors)

    _delete_dynamic_section_area(
        client,
        board_id,
        section=section,
        frames=frames,
        items=items,
        connectors=connectors,
    )
    section_top = _item_top_global(section)
    evidence_shape_ids = _render_demo_segments(
        client,
        board_id,
        plan,
        group_top=section_top,
        total_width=total_width,
    )
    _render_answer_support_connectors(
        client,
        board_id,
        evidence_shape_ids=evidence_shape_ids,
        selected_support_cards=selected_support_cards,
        answer_shape_id=flow_ids["answer"],
    )
    if include_proof:
        _render_precise_proof_frame(
            client,
            board_id,
            plan,
            trace=trace,
            provenance_slug=provenance_slug,
            group_top=section_top,
            total_width=total_width,
        )
    return "updated"


def _render_demo_skeleton(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    section_id: str,
    *,
    x_offset: float = 0,
) -> dict[str, str]:
    ids = {
        "question": client.create_shape(
            board_id,
            content=_demo_question_html(plan),
            x=x_offset + DEMO_QUESTION_X,
            y=DEMO_FLOW_Y,
            w=DEMO_FLOW_SHAPE_W,
            h=DEMO_FLOW_SHAPE_H,
            fill_color="#d0e8ff",
            parent_id=section_id,
            border_color="#33415f",
            border_width=3,
            font_size=DEMO_FLOW_FONT_SIZE,
            shape="round_rectangle",
            text_align="left",
        ),
        "retrieval": client.create_shape(
            board_id,
            content=_demo_retrieval_html(plan),
            x=x_offset + DEMO_RETRIEVAL_X,
            y=DEMO_FLOW_Y,
            w=DEMO_FLOW_SHAPE_W,
            h=DEMO_FLOW_SHAPE_H,
            fill_color="#e8d4f5",
            parent_id=section_id,
            border_color="#33415f",
            border_width=3,
            font_size=DEMO_FLOW_FONT_SIZE,
            shape="round_rectangle",
            text_align="left",
        ),
        "evidence": client.create_shape(
            board_id,
            content=_demo_evidence_html(plan),
            x=x_offset + DEMO_EVIDENCE_X,
            y=DEMO_FLOW_Y,
            w=DEMO_FLOW_SHAPE_W,
            h=DEMO_FLOW_SHAPE_H,
            fill_color="#fffac8",
            parent_id=section_id,
            border_color="#33415f",
            border_width=3,
            font_size=DEMO_FLOW_FONT_SIZE,
            shape="round_rectangle",
            text_align="left",
        ),
        "answer": client.create_shape(
            board_id,
            content=_demo_answer_html(plan),
            x=x_offset + DEMO_QUESTION_X,
            y=DEMO_ANSWER_Y,
            w=DEMO_FLOW_SHAPE_W,
            h=DEMO_ANSWER_SHAPE_H,
            fill_color="#d4f5d4",
            parent_id=section_id,
            border_color="#33415f",
            border_width=3,
            font_size=DEMO_FLOW_FONT_SIZE,
            shape="round_rectangle",
            text_align="left",
        ),
    }
    _render_demo_flow_connectors(client, board_id, ids)
    return ids


def _ensure_demo_story_items(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    section_title: str,
    section_id: str | None,
    children: list[dict],
    x_offset: float = 0,
) -> None:
    if not section_id:
        return
    if not any(_is_demo_title_item(item) for item in children):
        client.create_text(
            board_id,
            content=_demo_title_html(plan, section_title=section_title),
            x=x_offset + DEMO_TITLE_X,
            y=DEMO_TITLE_Y,
            w=DEMO_TITLE_W,
            parent_id=section_id,
            font_size=DEMO_TITLE_FONT_SIZE,
        )
    if not any(_is_demo_flow_symbol(item) for item in children):
        _render_demo_flow_symbols(client, board_id, section_id, x_offset=x_offset)
    if not any(_is_demo_visual_item(item) for item in children):
        _render_demo_visual(client, board_id, plan, section_id, x_offset=x_offset)
    if not any(_is_demo_legend_item(item) for item in children):
        client.create_shape(
            board_id,
            content=_demo_legend_html(),
            x=x_offset + DEMO_LEGEND_X,
            y=DEMO_LEGEND_Y,
            w=DEMO_LEGEND_W,
            h=DEMO_LEGEND_H,
            fill_color="#f6f7fb",
            parent_id=section_id,
            border_color="#667085",
            border_width=2,
            font_size=18,
            shape="round_rectangle",
            text_align="left",
        )


def _demo_title_html(plan: BoardPlan, *, section_title: str) -> str:
    section = section_title.replace(" - ", " / ")
    return (
        f"<p><strong>DataRoot</strong> | {html.escape(_truncate(section, 90))}</p>"
        "<p>Turns messy research folders into a cited decision board.</p>"
    )


def _demo_legend_html() -> str:
    return (
        "<p><strong>Source key</strong></p>"
        "<p>S1/S2 badges keep citations out of the main cards.</p>"
        f"<p>Exact rows live in {html.escape(DEMO_PROOF_FRAME_TITLE)}.</p>"
    )


def _render_image_symbol(
    client: MiroClient,
    board_id: str,
    section_id: str,
    *,
    icon_url: str,
    label: str,
    detail: str,
    x: float,
    y: float,
    icon_w: float = 64,
    icon_h: float = 64,
    fallback_shape: str = "rectangle",
    fallback_fill: str = "#f0f0f0",
    fallback_border: str = "#1a1a1a",
    font_size: int = 13,
) -> None:
    try:
        client.create_image(
            board_id,
            image_url=icon_url,
            title=label,
            x=x,
            y=y,
            w=icon_w,
            h=icon_h,
            parent_id=section_id,
        )
    except MiroAPIError:
        client.create_shape(
            board_id,
            content=(
                f"<p><strong>{html.escape(label)}</strong></p>"
                f"<p><small>{html.escape(detail)}</small></p>"
            ),
            x=x,
            y=y,
            w=icon_w,
            h=icon_h,
            fill_color=fallback_fill,
            parent_id=section_id,
            border_color=fallback_border,
            border_width=2,
            font_size=font_size,
            shape=fallback_shape,
            text_align="center",
        )
        return
    client.create_text(
        board_id,
        content=(
            f"<p><strong>{html.escape(label)}</strong></p>"
            f"<p><small>{html.escape(detail)}</small></p>"
        ),
        x=x,
        y=y + icon_h / 2 + 18,
        w=icon_w + 20,
        parent_id=section_id,
        font_size=font_size,
        text_align="center",
    )


def _render_demo_flow_symbols(client: MiroClient, board_id: str, section_id: str, *, x_offset: float = 0) -> None:
    symbols = [
        (DEMO_QUESTION_X, DEMO_SYMBOL_Y,       "files", "Files", "source files",   "#eff8ff", "#175cd3"),
        (DEMO_RETRIEVAL_X, DEMO_SYMBOL_Y,      "kb",    "KB",    "GitKB index",     "#f4ebff", "#6941c6"),
        (DEMO_EVIDENCE_X, DEMO_SYMBOL_Y,       "agent", "Agent", "reasoning cloud", "#fffaeb", "#b54708"),
        (DEMO_QUESTION_X, DEMO_ANSWER_Y - 145, "proof", "Proof", "cited proof",     "#ecfdf3", "#027a48"),
    ]
    for x, y, key, label, detail, fallback_fill, fallback_border in symbols:
        _render_image_symbol(
            client, board_id, section_id,
            icon_url=FLOW_ICON_URLS[key],
            label=label,
            detail=detail,
            x=x_offset + x,
            y=y,
            icon_w=72,
            icon_h=72,
            fallback_shape="rectangle",
            fallback_fill=fallback_fill,
            fallback_border=fallback_border,
            font_size=14,
        )


def _render_demo_visual(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    section_id: str,
    *,
    x_offset: float = 0,
) -> None:
    image_url = _demo_visual_url(plan.context_label)
    title = f"DataRoot visual - {plan.context_label}"
    if image_url:
        try:
            client.create_image(
                board_id,
                image_url=image_url,
                title=title,
                x=x_offset + DEMO_VISUAL_X,
                y=DEMO_VISUAL_Y,
                w=DEMO_VISUAL_W,
                h=DEMO_VISUAL_H,
                parent_id=section_id,
            )
            return
        except MiroAPIError as exc:
            plan.audit_notes.append(f"Miro image fallback for {plan.context_label}: {exc.status_code}.")

    _render_demo_visual_pictogram(client, board_id, plan, section_id, x_offset=x_offset)


def _render_demo_visual_pictogram(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    section_id: str,
    *,
    x_offset: float = 0,
) -> None:
    label, detail = _demo_visual_fallback(plan.context_label)
    x = x_offset + DEMO_VISUAL_X
    client.create_shape(
        board_id,
        content=(
            f"<p><strong>{html.escape(label)}</strong></p>"
            f"<p>{html.escape(detail)}</p>"
        ),
        x=x,
        y=DEMO_VISUAL_Y,
        w=DEMO_VISUAL_W,
        h=DEMO_VISUAL_H,
        fill_color="#ecfdf3",
        parent_id=section_id,
        border_color="#027a48",
        border_width=3,
        font_size=22,
        shape="round_rectangle",
        text_align="center",
    )
    normalized = plan.context_label.lower()
    if "bio" in normalized or "ferment" in normalized:
        _render_bioreactor_pictogram(client, board_id, section_id, x=x, y=DEMO_VISUAL_Y)
    elif "crop" in normalized or "agri" in normalized:
        _render_crop_lab_pictogram(client, board_id, section_id, x=x, y=DEMO_VISUAL_Y)
    else:
        _render_generic_lab_pictogram(client, board_id, section_id, x=x, y=DEMO_VISUAL_Y)


def _render_crop_lab_pictogram(client: MiroClient, board_id: str, section_id: str, *, x: float, y: float) -> None:
    pieces = [
        (x - 150, y + 55, "sprout", "FIELD", "greenhouse rows", "#dcfae6", "#079455"),
        (x + 12,  y + 55, "scope",  "LAB",   "assay bench",     "#d1e9ff", "#1570ef"),
        (x + 165, y + 55, "dna",    "GENE",  "marker",          "#f4ebff", "#7f56d9"),
    ]
    for px, py, key, label, detail, fallback_fill, fallback_border in pieces:
        _render_image_symbol(
            client, board_id, section_id,
            icon_url=PICTOGRAM_ICON_URLS[key],
            label=label, detail=detail,
            x=px, y=py, icon_w=64, icon_h=64,
            fallback_shape="rectangle",
            fallback_fill=fallback_fill, fallback_border=fallback_border,
        )


def _render_bioreactor_pictogram(client: MiroClient, board_id: str, section_id: str, *, x: float, y: float) -> None:
    pieces = [
        (x - 150, y + 55, "flask", "TANK",  "bioreactor", "#e0f2fe", "#026aa2"),
        (x + 5,   y + 55, "tube",  "ASSAY", "lab test",   "#fffaeb", "#b54708"),
        (x + 165, y + 55, "check", "QC",    "release",    "#ecfdf3", "#027a48"),
    ]
    for px, py, key, label, detail, fallback_fill, fallback_border in pieces:
        _render_image_symbol(
            client, board_id, section_id,
            icon_url=PICTOGRAM_ICON_URLS[key],
            label=label, detail=detail,
            x=px, y=py, icon_w=64, icon_h=64,
            fallback_shape="rectangle",
            fallback_fill=fallback_fill, fallback_border=fallback_border,
        )


def _render_generic_lab_pictogram(client: MiroClient, board_id: str, section_id: str, *, x: float, y: float) -> None:
    pieces = [
        (x - 150, y + 55, "files", "FILES",  "raw data",    "#eff8ff", "#175cd3"),
        (x + 5,   y + 55, "graph", "KB",     "linked graph", "#f4ebff", "#6941c6"),
        (x + 165, y + 55, "cert",  "ANSWER", "proof",        "#ecfdf3", "#027a48"),
    ]
    for px, py, key, label, detail, fallback_fill, fallback_border in pieces:
        _render_image_symbol(
            client, board_id, section_id,
            icon_url=PICTOGRAM_ICON_URLS[key],
            label=label, detail=detail,
            x=px, y=py, icon_w=64, icon_h=64,
            fallback_shape="rectangle",
            fallback_fill=fallback_fill, fallback_border=fallback_border,
        )


def _demo_visual_url(context_label: str) -> str | None:
    normalized = context_label.lower()
    env_names = []
    if "bio" in normalized or "ferment" in normalized:
        env_names.append("DATAROOT_MIRO_BIOREACTOR_IMAGE_URL")
    if "crop" in normalized or "agri" in normalized:
        env_names.append("DATAROOT_MIRO_FIELD_IMAGE_URL")
    env_names.extend(["DATAROOT_MIRO_LAB_IMAGE_URL", "DATAROOT_MIRO_IMAGE_URL"])
    for env_name in env_names:
        value = (os.environ.get(env_name) or "").strip()
        if value:
            return value
    return None


def _demo_visual_fallback(context_label: str) -> tuple[str, str]:
    normalized = context_label.lower()
    if "bio" in normalized or "ferment" in normalized:
        return ("BIOREACTOR", "Strains, assays, QC, and scale-up readiness.")
    if "crop" in normalized or "agri" in normalized:
        return ("FIELD + LAB", "Cultivars, genes, trials, inventory, and readiness.")
    return ("LAB WORKSPACE", "Source files, linked evidence, and cited answer flow.")


def _is_demo_title_item(item: dict) -> bool:
    text = _plain_item_text(item).lower()
    return "dataroot" in text and "cited decision board" in text


def _is_demo_legend_item(item: dict) -> bool:
    text = _plain_item_text(item).lower()
    return "source key" in text and "badges keep citations" in text


def _is_demo_flow_symbol(item: dict) -> bool:
    text = _plain_item_text(item).lower()
    return "cited proof" in text and "proof" in text


def _is_demo_visual_item(item: dict) -> bool:
    title = _item_title(item).lower()
    text = _plain_item_text(item).lower()
    return title.startswith("dataroot visual") or "field + lab" in text or "strains, assays" in text or "lab workspace" in text


def _render_demo_flow_connectors(client: MiroClient, board_id: str, ids: dict[str, str]) -> None:
    for source, target, label, start_snap_to, end_snap_to in DEMO_FLOW_CONNECTORS:
        client.create_connector(
            board_id,
            start_id=ids[source],
            end_id=ids[target],
            caption=label,
            start_snap_to=start_snap_to,
            end_snap_to=end_snap_to,
        )


def _ensure_live_ask_question_input(
    client: MiroClient,
    board_id: str,
    *,
    section_title: str,
    section_id: str | None,
    children: list[dict],
    x_offset: float = 0,
) -> None:
    if not section_id or not _is_live_ask_section_title(section_title):
        return

    for item in children:
        if _is_legacy_live_ask_affordance(item):
            _delete_item_if_exists(client, board_id, _item_id(item) or "", item_type=_item_type(item))

    if not any(_is_live_ask_run_affordance(item) for item in children):
        _render_live_ask_run_affordance(client, board_id, section_id, x_offset=x_offset)

    for item in children:
        if is_live_ask_question_input(item):
            if not extract_live_ask_question_text(item):
                item_id = _item_id(item)
                if item_id:
                    client.update_text(board_id, item_id, content=DEMO_ASK_INPUT_HTML)
            return
    client.create_text(
        board_id,
        content=DEMO_ASK_INPUT_HTML,
        x=x_offset + DEMO_ASK_INPUT_X,
        y=DEMO_ASK_INPUT_Y,
        w=DEMO_ASK_INPUT_W,
        parent_id=section_id,
        font_size=DEMO_TEXT_FONT_SIZE,
        color="#172033",
        text_align="left",
    )


def _render_live_ask_run_affordance(
    client: MiroClient,
    board_id: str,
    section_id: str,
    *,
    x_offset: float = 0,
) -> None:
    x = x_offset + DEMO_LIVE_ASK_RUN_X
    client.create_shape(
        board_id,
        content=DEMO_LIVE_ASK_RUN_HTML,
        x=x,
        y=DEMO_LIVE_ASK_RUN_Y,
        w=DEMO_LIVE_ASK_RUN_W,
        h=DEMO_LIVE_ASK_RUN_H,
        fill_color="#d1fae5",
        parent_id=section_id,
        border_color="#047857",
        border_width=4,
        font_size=22,
        shape="round_rectangle",
        text_align="center",
        text_color="#064e3b",
    )
    root_id = client.create_shape(
        board_id,
        content="<p><strong>ROOT</strong></p>",
        x=x - 178,
        y=DEMO_LIVE_ASK_RUN_Y,
        w=86,
        h=86,
        fill_color="#ecfdf3",
        parent_id=section_id,
        border_color="#047857",
        border_width=3,
        font_size=16,
        shape="circle",
        text_align="center",
        text_color="#064e3b",
    )
    branch_ids = []
    for dx, dy in ((-62, -36), (-48, 38), (52, 0)):
        branch_ids.append(
            client.create_shape(
                board_id,
                content="",
                x=x - 178 + dx,
                y=DEMO_LIVE_ASK_RUN_Y + dy,
                w=34,
                h=34,
                fill_color="#ffffff",
                parent_id=section_id,
                border_color="#047857",
                border_width=3,
                font_size=10,
                shape="circle",
                text_align="center",
                text_color="#064e3b",
            )
        )
    for branch_id in branch_ids:
        client.create_connector(board_id, start_id=root_id, end_id=branch_id, caption="")


def _is_live_ask_run_affordance(item: dict) -> bool:
    text = _plain_item_text(item).lower()
    return "dataroot run live ask" in text and "root submit action" in text


def _is_live_ask_section_title(title: str) -> bool:
    return title.strip().endswith(" - Live Ask")


def _is_legacy_live_ask_affordance(item: dict) -> bool:
    text = _plain_item_text(item).lower()
    return "ask your question" in text and "dataroot panel" in text


def _plain_item_text(item: dict) -> str:
    return plain_miro_item_text(item)


def _normalize_demo_flow_connectors(
    client: MiroClient,
    board_id: str,
    flow_ids: dict[str, str],
    connectors: list[dict],
) -> None:
    connectors_by_endpoints: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for connector in connectors:
        connectors_by_endpoints[_connector_endpoint_ids(connector)].append(connector)
    expected_endpoints = {
        (flow_ids[source], flow_ids[target])
        for source, target, _label, _start_snap_to, _end_snap_to in DEMO_FLOW_CONNECTORS
    }
    normalized_connector_ids: set[str] = set()
    for source, target, label, start_snap_to, end_snap_to in DEMO_FLOW_CONNECTORS:
        start_id = flow_ids[source]
        end_id = flow_ids[target]
        endpoint_matches = connectors_by_endpoints.get((start_id, end_id), [])
        connector = endpoint_matches[0] if endpoint_matches else None
        connector_id = _item_id(connector or {})
        if connector_id:
            normalized_connector_ids.add(connector_id)
            client.update_connector(
                board_id,
                connector_id,
                caption=label,
                shape="elbowed",
                start_id=start_id,
                end_id=end_id,
                start_snap_to=start_snap_to,
                end_snap_to=end_snap_to,
            )
        else:
            client.create_connector(
                board_id,
                start_id=start_id,
                end_id=end_id,
                caption=label,
                start_snap_to=start_snap_to,
                end_snap_to=end_snap_to,
            )

    flow_item_ids = set(flow_ids.values())
    for connector in connectors:
        connector_id = _item_id(connector)
        endpoints = _connector_endpoint_ids(connector)
        if (
            connector_id
            and endpoints[0] in flow_item_ids
            and endpoints[1] in flow_item_ids
            and (endpoints not in expected_endpoints or connector_id not in normalized_connector_ids)
        ):
            _delete_item_if_exists(client, board_id, connector_id, item_type="connector")


def _render_demo_segments(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    group_top: float,
    total_width: float,
) -> dict[str, str]:
    stages = _story_stages(plan)
    cards_by_stage: dict[str, list[BoardCard]] = defaultdict(list)
    for card in plan.evidence_cards:
        cards_by_stage[card.stage].append(card)
    source_badges = _source_badges(plan)

    shape_ids = {}
    lanes_top = group_top + DEMO_TOP_FRAME_H + HEADER_TO_LANES_GAP
    for stage_index, stage in enumerate(stages):
        cards = cards_by_stage.get(stage, [])
        lane_h = _demo_lane_height(cards)
        frame_id = client.create_frame(
            board_id,
            title=_humanize(stage),
            x=stage_index * (STORY_LANE_W + STORY_FRAME_GAP) + STORY_LANE_W / 2,
            y=lanes_top + lane_h / 2,
            w=STORY_LANE_W,
            h=lane_h,
        )
        if not cards:
            client.create_text(
                board_id,
                content="<p>No cited evidence cards returned.</p>",
                x=STORY_LANE_W / 2,
                y=150,
                w=STORY_LANE_W - 120,
                parent_id=frame_id,
                font_size=DEMO_TEXT_FONT_SIZE,
            )
            continue
        for index, card in enumerate(cards):
            y = 96 + index * (DEMO_EVIDENCE_CARD_H + DEMO_EVIDENCE_CARD_GAP_Y) + DEMO_EVIDENCE_CARD_H / 2
            shape_ids[card.id] = client.create_shape(
                board_id,
                content=_card_html(card, source_badge=source_badges.get(card.id)),
                x=STORY_LANE_W / 2,
                y=y,
                w=DEMO_EVIDENCE_CARD_W,
                h=DEMO_EVIDENCE_CARD_H,
                fill_color=_card_color(card),
                parent_id=frame_id,
                border_color=_card_border(card),
                border_width=3 if card.emphasis in {"primary", "rejected"} else 2,
                font_size=DEMO_CARD_FONT_SIZE,
                shape="round_rectangle",
                text_align="left",
            )
    return shape_ids


def _render_answer_support_connectors(
    client: MiroClient,
    board_id: str,
    *,
    evidence_shape_ids: dict[str, str],
    selected_support_cards: list[BoardCard],
    answer_shape_id: str,
) -> None:
    for index, card in enumerate(selected_support_cards[:2]):
        shape_id = evidence_shape_ids.get(card.id)
        if not shape_id:
            continue
        start_snap_to, end_snap_to = _answer_support_snap_pair(index)
        client.create_connector(
            board_id,
            start_id=shape_id,
            end_id=answer_shape_id,
            caption="",
            start_snap_to=start_snap_to,
            end_snap_to=end_snap_to,
        )


def _answer_support_snap_pair(index: int) -> tuple[str, str]:
    return ("left", "bottom") if index == 0 else ("left", "left")


def _render_precise_proof_frame(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    trace: dict,
    provenance_slug: str | None,
    group_top: float,
    total_width: float,
) -> None:
    proof_top = group_top + DEMO_TOP_FRAME_H + HEADER_TO_LANES_GAP + _demo_max_lane_height(plan) + HEADER_TO_LANES_GAP
    proof_h = _demo_proof_height(plan)
    proof_frame_id = client.create_frame(
        board_id,
        title=DEMO_PROOF_FRAME_TITLE,
        x=total_width / 2,
        y=proof_top + proof_h / 2,
        w=total_width,
        h=proof_h,
    )
    client.create_text(
        board_id,
        content=_demo_proof_html(plan, trace=trace, provenance_slug=provenance_slug),
        x=total_width / 2,
        y=proof_h / 2,
        w=total_width - 120,
        parent_id=proof_frame_id,
        font_size=18,
    )


def _delete_dynamic_section_area(
    client: MiroClient,
    board_id: str,
    *,
    section: dict,
    frames: list[dict],
    items: list[dict],
    connectors: list[dict],
) -> None:
    section_id = _item_id(section)
    section_top = _item_top_global(section)
    dynamic_top = _item_bottom(section) - 1
    section_bottom = _next_section_top(frames, section_top) or (section_top + _demo_section_height(None))
    dynamic_frame_ids = {
        _item_id(frame)
        for frame in frames
        if _item_id(frame) != section_id
        and dynamic_top <= _item_top_global(frame) < section_bottom
    }
    selected_ids = set(dynamic_frame_ids)
    changed = True
    while changed:
        changed = False
        for item in items:
            item_id = _item_id(item)
            if item_id and item_id not in selected_ids and _parent_id(item) in selected_ids:
                selected_ids.add(item_id)
                changed = True

    for connector in connectors:
        start_id, end_id = _connector_endpoint_ids(connector)
        if start_id in selected_ids or end_id in selected_ids:
            _delete_item_if_exists(client, board_id, _item_id(connector), item_type="connector")
    for item in items:
        item_id = _item_id(item)
        if item_id in selected_ids:
            _delete_item_if_exists(client, board_id, item_id, item_type=_item_type(item))
    for frame in sorted(
        (frame for frame in frames if _item_id(frame) in dynamic_frame_ids),
        key=lambda item: (_item_top_global(item), _item_id(item)),
        reverse=True,
    ):
        _delete_frame_if_exists(client, board_id, _item_id(frame))


def _delete_demo_section_area(
    client: MiroClient,
    board_id: str,
    *,
    section: dict,
    frames: list[dict],
    items: list[dict],
    connectors: list[dict],
) -> None:
    section_id = _item_id(section)
    if not section_id:
        return
    section_top = _item_top_global(section)
    dynamic_top = _item_bottom(section) - 1
    section_bottom = _next_section_top(frames, section_top) or (section_top + _demo_section_height(None))
    frame_ids = {
        _item_id(frame)
        for frame in frames
        if _item_id(frame)
        and (_item_id(frame) == section_id or dynamic_top <= _item_top_global(frame) < section_bottom)
    }
    selected_ids = set(frame_ids)
    changed = True
    while changed:
        changed = False
        for item in items:
            item_id = _item_id(item)
            if item_id and item_id not in selected_ids and _parent_id(item) in selected_ids:
                selected_ids.add(item_id)
                changed = True

    for connector in connectors:
        start_id, end_id = _connector_endpoint_ids(connector)
        if start_id in selected_ids or end_id in selected_ids:
            _delete_item_if_exists(client, board_id, _item_id(connector), item_type="connector")
    for item in items:
        item_id = _item_id(item)
        if item_id in selected_ids and _item_type(item) != "frame":
            _delete_item_if_exists(client, board_id, item_id, item_type=_item_type(item))
    for frame in sorted(
        (frame for frame in frames if _item_id(frame) in frame_ids),
        key=lambda item: (_item_top_global(item), _item_id(item)),
        reverse=True,
    ):
        _delete_frame_if_exists(client, board_id, _item_id(frame))


def _delete_item_if_exists(client: MiroClient, board_id: str, item_id: str, *, item_type: str | None = None) -> None:
    if not item_id:
        return
    try:
        client.delete_item(board_id, item_id, item_type=item_type)
    except MiroAPIError as exc:
        if exc.status_code != 404:
            raise


def _delete_frame_if_exists(client: MiroClient, board_id: str, frame_id: str) -> None:
    if not frame_id:
        return
    try:
        client.delete_frame(board_id, frame_id)
    except MiroAPIError as exc:
        if exc.status_code != 404:
            raise


def _find_section_frame(client: MiroClient, board_id: str, section_title: str) -> dict:
    match = _find_section_frame_or_none(client, board_id, section_title)
    if match is None:
        raise RuntimeError(f'No Miro section titled "{section_title}" was found. Run dataroot miro-refresh-board first.')
    return match


def _find_section_frame_or_none(client: MiroClient, board_id: str, section_title: str) -> dict | None:
    matches = [
        frame
        for frame in client.list_frames(board_id)
        if _item_title(frame).strip() == section_title
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (_item_position_y(item), _item_id(item)))
    return matches[0]


def _fixed_flow_shape_ids(children: list[dict]) -> dict[str, str]:
    ids = {}
    for item in children:
        if _item_type(item) != "shape":
            continue
        role = _fixed_flow_role(item)
        if role and role not in ids:
            ids[role] = _item_id(item)
    return ids


def _fixed_flow_role(item: dict) -> str | None:
    content = _item_content(item)
    compact = " ".join(re.sub(r"<[^>]+>", " ", html.unescape(content)).split()).lower()
    for key, title in FIXED_FLOW_TITLES.items():
        if f"<strong>{title}</strong>" in content or compact.startswith(title.lower()):
            return key
    return None


def _list_connectors_or_empty(client: MiroClient, board_id: str) -> list[dict]:
    try:
        return list(client.list_connectors(board_id))
    except MiroAPIError as exc:
        if exc.status_code in {404, 405}:
            return []
        raise


def _demo_section_width(plan: BoardPlan) -> float:
    lane_count = max(1, len(_story_stages(plan)))
    evidence_width = lane_count * STORY_LANE_W + max(0, lane_count - 1) * STORY_FRAME_GAP
    return max(DEMO_SECTION_W, evidence_width)


def _demo_top_x_offset(total_width: float) -> float:
    return max(0.0, (total_width - DEMO_SECTION_W) / 2)


def _demo_section_height(plan: BoardPlan | None) -> float:
    return max(DEMO_SECTION_MIN_H, DEMO_TOP_FRAME_H + HEADER_TO_LANES_GAP + _demo_max_lane_height(plan) + HEADER_TO_LANES_GAP + DEMO_AUDIT_H)


def _demo_max_lane_height(plan: BoardPlan | None) -> float:
    if plan is None:
        return STORY_LANE_H
    cards_by_stage: dict[str, list[BoardCard]] = defaultdict(list)
    for card in plan.evidence_cards:
        cards_by_stage[card.stage].append(card)
    return max((_demo_lane_height(cards_by_stage.get(stage, [])) for stage in _story_stages(plan)), default=STORY_LANE_H)


def _demo_lane_height(cards: list[BoardCard]) -> float:
    if not cards:
        return STORY_LANE_H
    content_bottom = 96 + len(cards) * DEMO_EVIDENCE_CARD_H + max(0, len(cards) - 1) * DEMO_EVIDENCE_CARD_GAP_Y + 96
    return max(STORY_LANE_H, content_bottom)


def _demo_question_html(plan: BoardPlan) -> str:
    return _flow_html(FIXED_FLOW_TITLES["question"], _truncate(plan.question, 190))


def _demo_retrieval_html(plan: BoardPlan) -> str:
    return _flow_html(FIXED_FLOW_TITLES["retrieval"], _truncate(plan.retrieval_summary, 190))


def _demo_evidence_html(plan: BoardPlan) -> str:
    evidence_count = len(plan.evidence_cards)
    support_count = len(_selected_answer_support_cards(plan))
    if evidence_count == 0:
        detail = "No cited records were returned for this answer."
    else:
        evidence_plural = "" if evidence_count == 1 else "s"
        support_plural = "" if support_count == 1 else "s"
        detail = (
            f"{evidence_count} interpreted evidence claim{evidence_plural}; "
            f"{support_count} connected support arrow{support_plural}."
        )
    return _flow_html(FIXED_FLOW_TITLES["evidence"], detail)


def _demo_answer_html(plan: BoardPlan) -> str:
    return _flow_html(FIXED_FLOW_TITLES["answer"], _truncate(plan.answer, 360))


def _source_badges(plan: BoardPlan) -> dict[str, str]:
    key_badges: dict[str, str] = {}
    card_badges: dict[str, str] = {}
    for card in plan.evidence_cards:
        key = _source_key(card)
        if key not in key_badges:
            key_badges[key] = f"S{len(key_badges) + 1}"
        card_badges[card.id] = key_badges[key]
    return card_badges


def _source_reference_rows(plan: BoardPlan) -> list[tuple[str, str, str]]:
    badges = _source_badges(plan)
    rows: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for card in plan.evidence_cards:
        key = _source_key(card)
        if key in seen:
            continue
        seen.add(key)
        rows.append((badges.get(card.id, f"S{len(rows) + 1}"), card.title, _source_display(card)))
    return rows


def _source_key(card: BoardCard) -> str:
    return card.citation or card.source or card.id


def _source_display(card: BoardCard) -> str:
    source_label = card.source
    if card.citation and card.citation != card.source:
        citation_label = _short_slug(card.citation)
        source_label = f"{source_label} | {citation_label}" if source_label else citation_label
    return source_label or card.citation or card.id


def _selected_answer_support_cards(plan: BoardPlan) -> list[BoardCard]:
    selected: list[BoardCard] = []
    seen: set[str] = set()
    for emphasis in ("primary", "secondary", "normal"):
        for card in plan.evidence_cards:
            if card.id in seen:
                continue
            if _answer_support_bucket(card) != emphasis:
                continue
            selected.append(card)
            seen.add(card.id)
            if len(selected) >= 2:
                return selected
    return selected


def _answer_support_bucket(card: BoardCard) -> str | None:
    emphasis = (card.emphasis or "normal").strip().lower()
    if emphasis in {"primary", "secondary"}:
        return emphasis
    if emphasis in {"rejected", "gap"}:
        return None
    return "normal"


def _record_answer_support_audit(plan: BoardPlan, selected_support_cards: list[BoardCard]) -> None:
    prefix = "Evidence-to-answer arrows:"
    plan.audit_notes = [note for note in plan.audit_notes if not note.startswith(prefix)]
    if not plan.evidence_cards:
        plan.audit_notes.append(f"{prefix} none rendered because no evidence cards were available.")
    elif selected_support_cards:
        selected_ids = ", ".join(card.id for card in selected_support_cards[:2])
        plan.audit_notes.append(f"{prefix} {len(selected_support_cards[:2])} rendered from {selected_ids}.")
    else:
        plan.audit_notes.append(f"{prefix} none rendered because no primary, secondary, or normal evidence card was available.")


def _demo_proof_height(plan: BoardPlan) -> float:
    visible_rows = max(1, min(len(_source_reference_rows(plan)), 8) + min(len(plan.proof_rows), 8))
    return max(DEMO_PROOF_MIN_H, 140 + visible_rows * DEMO_PROOF_ROW_H)


def _demo_proof_html(plan: BoardPlan, *, trace: dict, provenance_slug: str | None) -> str:
    parts = [f"<p><strong>{html.escape(DEMO_PROOF_FRAME_TITLE)}</strong></p>"]
    if provenance_slug:
        parts.append(f"<p><small>Provenance trace: {html.escape(provenance_slug)}</small></p>")
    source_rows = _source_reference_rows(plan)
    if source_rows:
        parts.append("<p><strong>Source key</strong></p>")
        for badge, title, source in source_rows[:12]:
            parts.append(
                "<p>"
                f"<strong>{html.escape(badge)}</strong> {html.escape(_truncate(title, 90))}<br>"
                f"<small>{html.escape(_truncate(source, 180))}</small>"
                "</p>"
            )
    if not plan.proof_rows:
        parts.append("<p>No exact proof rows were available beyond the source key above.</p>")
    else:
        parts.append("<p><strong>Exact proof rows</strong></p>")
    for row in plan.proof_rows[:10]:
        detail = row.raw_detail or row.detail
        source = " | ".join(part for part in [row.source_label, _humanize(row.stage)] if part)
        parts.append(
            "<p>"
            f"<strong>{html.escape(_truncate(row.title, 90))}</strong><br>"
            f"{html.escape(_truncate(detail, 260))}<br>"
            f"<small>{html.escape(_truncate(source, 120))} | {html.escape(_truncate(row.evidence_ref, 140))}</small>"
            "</p>"
        )
    if len(plan.proof_rows) > 10:
        parts.append(f"<p><small>...and {len(plan.proof_rows) - 10} more proof rows in GitKB.</small></p>")
    edge_notes = [
        _truncate(str(edge.get("evidence") or edge.get("description")), 220)
        for edge in trace.get("edges") or []
        if isinstance(edge, dict) and (edge.get("evidence") or edge.get("description"))
    ]
    if edge_notes:
        parts.append("<p><strong>Edge evidence</strong></p>")
        parts.extend(f"<p>{html.escape(note)}</p>" for note in edge_notes[:4])
    if plan.audit_notes:
        parts.append("<p><strong>Render metadata</strong></p>")
        parts.append(_audit_html(plan.audit_notes[:6]))
    return "".join(parts)


def _item_position_y(item: dict) -> float:
    return _number((item.get("position") or {}).get("y"))


def _item_top_global(item: dict) -> float:
    geometry = item.get("geometry") or {}
    return _item_position_y(item) - _number(geometry.get("height")) / 2


def _item_bottom(item: dict) -> float:
    geometry = item.get("geometry") or {}
    return _item_position_y(item) + _number(geometry.get("height")) / 2


def _next_section_top(frames: list[dict], section_top: float) -> float | None:
    candidates = [
        _item_top_global(frame)
        for frame in frames
        if _is_demo_section_frame(frame) and _item_top_global(frame) > section_top + 1
    ]
    return min(candidates) if candidates else None


def _is_demo_section_frame(frame: dict) -> bool:
    title = _item_title(frame)
    return title.endswith(" - Standard Demo") or title.endswith(" - Live Ask")


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_story_plan(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    trace: dict,
    group_top: float,
    provenance_slug: str | None,
) -> None:
    stages = _story_stages(plan)
    lane_count = max(1, len(stages))
    evidence_width = lane_count * STORY_LANE_W + max(0, lane_count - 1) * STORY_FRAME_GAP
    total_width = max(STORY_FRAME_W, evidence_width)

    header_frame_id = client.create_frame(
        board_id,
        title=plan.context_label,
        x=total_width / 2,
        y=group_top + STORY_HEADER_H / 2,
        w=total_width,
        h=STORY_HEADER_H,
    )
    client.create_text(
        board_id,
        content=_decision_html(plan, provenance_slug=provenance_slug),
        x=total_width / 2,
        y=STORY_HEADER_H / 2,
        w=max(600, total_width - 80),
        parent_id=header_frame_id,
    )

    flow_top = group_top + STORY_HEADER_H + HEADER_TO_LANES_GAP
    flow_frame_id = client.create_frame(
        board_id,
        title="Retrieval Flow",
        x=total_width / 2,
        y=flow_top + STORY_FLOW_H / 2,
        w=total_width,
        h=STORY_FLOW_H,
    )
    flow_shape_ids = _render_flow(client, board_id, plan, flow_frame_id, total_width)

    lanes_top = flow_top + STORY_FLOW_H + HEADER_TO_LANES_GAP
    frame_ids: dict[str, str] = {}
    for stage in stages:
        stage_index = stages.index(stage)
        frame_ids[stage] = client.create_frame(
            board_id,
            title=_humanize(stage),
            x=stage_index * (STORY_LANE_W + STORY_FRAME_GAP) + STORY_LANE_W / 2,
            y=lanes_top + STORY_LANE_H / 2,
            w=STORY_LANE_W,
            h=STORY_LANE_H,
        )

    shape_ids, node_positions = _render_evidence_cards(client, board_id, plan, stages, frame_ids)
    _render_story_connections(client, board_id, plan, shape_ids, node_positions)

    bottom_top = lanes_top + STORY_LANE_H + HEADER_TO_LANES_GAP
    _render_alternatives_and_audit(
        client,
        board_id,
        plan,
        trace=trace,
        top=bottom_top,
        total_width=total_width,
        provenance_slug=provenance_slug,
    )


def _story_stages(plan: BoardPlan) -> list[str]:
    stages = []
    for card in plan.evidence_cards:
        if card.stage not in stages:
            stages.append(card.stage)
    return stages or ["evidence"]


def _decision_html(plan: BoardPlan, *, provenance_slug: str | None) -> str:
    parts = [
        f"<p><strong>Demo dataset</strong>: {html.escape(_truncate(plan.context_label, 160))}</p>",
        f"<p><strong>Question</strong>: {html.escape(_truncate(plan.question, 360))}</p>",
        f"<p><strong>Answer</strong>: {html.escape(_truncate(plan.answer, 560))}</p>",
        f"<p><strong>Recommendation</strong>: {html.escape(_truncate(plan.recommendation, 240))} "
        f"<small>Confidence: {html.escape(_truncate(plan.confidence, 80))}</small></p>",
        f"<p><small>{html.escape(_truncate(plan.retrieval_summary, 300))}</small></p>",
    ]
    if provenance_slug:
        parts.append(f"<p><small>Audit trace: {html.escape(provenance_slug)}</small></p>")
    return "".join(parts)


def _render_flow(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    parent_id: str,
    total_width: float,
) -> dict[str, str]:
    step_w = min(520, max(360, (total_width - 540) / 4))
    gap = max(100, (total_width - 240 - step_w * 4) / 3)
    x_positions = [120 + step_w / 2 + index * (step_w + gap) for index in range(4)]
    y = STORY_FLOW_H / 2
    steps = [
        ("question", "Question", _truncate(plan.question, 120), "#d0e8ff", x_positions[0], y),
        ("retrieval", "GitKB retrieval", _truncate(plan.retrieval_summary, 130), "#e8d4f5", x_positions[1], y),
        ("evidence", "Evidence path", f"{len(plan.evidence_cards)} cited records grouped by source.", "#fffac8", x_positions[2], y),
        ("answer", "Final answer", _truncate(plan.answer, 140), "#d4f5d4", x_positions[3], y),
    ]
    ids = {}
    for key, title, detail, color, x, y in steps:
        ids[key] = client.create_shape(
            board_id,
            content=_flow_html(title, detail),
            x=x,
            y=y,
            w=step_w,
            h=142,
            fill_color=color,
            parent_id=parent_id,
            border_color="#33415f",
            border_width=3,
            font_size=20,
            shape="round_rectangle",
            text_align="left",
        )
    for source, target, label, start_snap_to, end_snap_to in STORY_FLOW_CONNECTORS:
        client.create_connector(
            board_id,
            start_id=ids[source],
            end_id=ids[target],
            caption=label,
            start_snap_to=start_snap_to,
            end_snap_to=end_snap_to,
        )
    return ids


def _render_evidence_cards(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    stages: list[str],
    frame_ids: dict[str, str],
) -> tuple[dict[str, str], dict[str, tuple[float, float, str]]]:
    shape_ids = {}
    node_positions = {}
    cards_by_stage: dict[str, list[BoardCard]] = defaultdict(list)
    for card in plan.evidence_cards:
        cards_by_stage[card.stage].append(card)

    for stage in stages:
        for index, card in enumerate(cards_by_stage.get(stage, [])):
            y = 96 + index * (STORY_CARD_H + STORY_CARD_GAP) + STORY_CARD_H / 2
            x = STORY_LANE_W / 2 - 70
            shape_ids[card.id] = client.create_shape(
                board_id,
                content=_card_html(card),
                x=x,
                y=y,
                w=STORY_CARD_W,
                h=STORY_CARD_H,
                fill_color=_card_color(card),
                parent_id=frame_ids[stage],
                border_color=_card_border(card),
                border_width=3 if card.emphasis in {"primary", "rejected"} else 2,
                font_size=18,
                shape="round_rectangle",
                text_align="left",
            )
            node_positions[card.id] = (x, y, frame_ids[stage])
            note = _card_note(card)
            if note:
                client.create_sticky(
                    board_id,
                    content=note,
                    x=x + STORY_CARD_W / 2 + 82,
                    y=y,
                    width=250,
                    parent_id=frame_ids[stage],
                    fill_color=_note_color(card),
                )
    return shape_ids, node_positions


def _render_story_connections(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    shape_ids: dict[str, str],
    node_positions: dict[str, tuple[float, float, str]],
) -> None:
    diagnostics = []
    note_offsets: dict[str, int] = defaultdict(int)
    for connection in plan.connections:
        start_id = shape_ids.get(connection.source)
        end_id = shape_ids.get(connection.target)
        if not start_id or not end_id:
            diagnostics.append(
                f"Skipped edge {connection.source or '?'} -> {connection.target or '?'}: missing rendered endpoint."
            )
            continue
        if connection.evidence and connection.source in node_positions:
            sx, sy, parent_id = node_positions[connection.source]
            offset = note_offsets[connection.source] * 46
            note_offsets[connection.source] += 1
            client.create_sticky(
                board_id,
                content=_truncate(connection.evidence, MAX_EDGE_NOTE_CHARS),
                x=sx + STORY_CARD_W / 2 + 82,
                y=sy + offset,
                width=250,
                parent_id=parent_id,
                fill_color="light_yellow",
            )
    plan.audit_notes.extend(diagnostics)


def _render_alternatives_and_audit(
    client: MiroClient,
    board_id: str,
    plan: BoardPlan,
    *,
    trace: dict,
    top: float,
    total_width: float,
    provenance_slug: str | None,
) -> None:
    if plan.alternatives:
        alt_w = max(900, total_width * 0.55)
        audit_w = max(700, total_width - alt_w - STORY_FRAME_GAP)
        alt_frame_id = client.create_frame(
            board_id,
            title="Alternatives And Gaps",
            x=alt_w / 2,
            y=top + STORY_AUDIT_H / 2,
            w=alt_w,
            h=STORY_AUDIT_H,
        )
        for index, card in enumerate(plan.alternatives[:4]):
            client.create_shape(
                board_id,
                content=_card_html(card),
                x=170 + index * 290,
                y=STORY_AUDIT_H / 2,
                w=260,
                h=150,
                fill_color=_card_color(card),
                parent_id=alt_frame_id,
                border_color=_card_border(card),
                font_size=16,
                shape="round_rectangle",
                text_align="left",
            )
        audit_x = alt_w + STORY_FRAME_GAP + audit_w / 2
    else:
        audit_w = total_width
        audit_x = audit_w / 2

    audit_frame_id = client.create_frame(
        board_id,
        title="Full Provenance Audit",
        x=audit_x,
        y=top + STORY_AUDIT_H / 2,
        w=audit_w,
        h=STORY_AUDIT_H,
    )
    audit_notes = list(plan.audit_notes)
    if provenance_slug:
        audit_notes.append(f"Provenance trace: {provenance_slug}")
    audit_notes.extend(
        [
            f"Rendered evidence cards: {len(plan.evidence_cards)}",
            f"Raw trace stages: {', '.join(trace.get('stages') or [])}",
        ]
    )
    client.create_text(
        board_id,
        content=_audit_html(audit_notes),
        x=audit_w / 2,
        y=STORY_AUDIT_H / 2,
        w=max(600, audit_w - 80),
        parent_id=audit_frame_id,
    )


def _flow_html(title: str, detail: str, *, footer: str = "") -> str:
    return f"<p><strong>{html.escape(title)}</strong></p><p>{html.escape(detail)}</p>{footer}"


def _card_html(card: BoardCard, *, source_badge: str | None = None) -> str:
    source = _proof_footer_html(card, source_badge=source_badge)
    return (
        f"<p><strong>{html.escape(_truncate(card.title, 72))}</strong></p>"
        f"<p>{html.escape(_truncate(card.detail, 190))}</p>"
        f"{source}"
    )


def _proof_footer_html(card: BoardCard, *, source_badge: str | None = None) -> str:
    if not (source_badge or card.source or card.citation):
        return ""

    pieces = []
    if card.source:
        pieces.append(f"Dataset/store: {_truncate(card.source, 56)}")
    if card.citation:
        pieces.append(f"File/path: {_truncate(_short_slug(card.citation), 56)}")
    citation_id = card.citation or card.id
    if citation_id:
        pieces.append(f"Citation/id: {_truncate(_short_slug(citation_id), 56)}")

    label = f"{source_badge} proof" if source_badge else "Proof"
    return (
        "<p><small>"
        f"<strong>{html.escape(label)}</strong>: {html.escape('; '.join(pieces))}"
        "</small></p>"
    )


def _card_note(card: BoardCard) -> str:
    parts = []
    if card.detail:
        parts.append(_truncate(card.detail, MAX_NOTE_CHARS))
    if card.source:
        parts.append(f"Source: {card.source}")
    if card.citation:
        parts.append(f"Citation: {card.citation}")
    return "\n".join(parts)


def _audit_html(notes: list[str]) -> str:
    lines = [f"<p>{html.escape(_truncate(note, 260))}</p>" for note in notes if note]
    return "".join(lines)


def _card_color(card: BoardCard) -> str:
    if card.emphasis == "primary":
        return "#d4f5d4"
    if card.emphasis == "secondary":
        return "#fffac8"
    if card.emphasis == "rejected":
        return "#ffd6d6"
    if card.emphasis == "gap":
        return "#ffe5b4"
    return STAGE_COLORS.get(card.stage, "#f0f0f0")


def _card_border(card: BoardCard) -> str:
    if card.emphasis == "primary":
        return "#1f7a3a"
    if card.emphasis == "rejected":
        return "#b42318"
    if card.emphasis == "secondary":
        return "#996f00"
    return "#33415f"


def _note_color(card: BoardCard) -> str:
    if card.emphasis == "primary":
        return "light_green"
    if card.emphasis == "rejected":
        return "light_pink"
    if card.emphasis == "secondary":
        return "light_yellow"
    return "gray"


def _stage_order(trace: dict) -> list[str]:
    stages = []
    for stage in trace.get("stages") or []:
        normalized = str(stage or "").strip()
        if normalized and normalized not in stages:
            stages.append(normalized)
    for node in trace.get("nodes") or []:
        stage = str(node.get("stage") or "evidence").strip() or "evidence"
        if stage not in stages:
            stages.append(stage)
    return stages


def _display_nodes(trace: dict, nodes: list[dict], stages: list[str], answer_summary: str) -> list[dict]:
    display_nodes = [dict(node) for node in nodes]
    stages_with_nodes = {str(node.get("stage") or "evidence") for node in nodes}
    if "query" in stages and "query" not in stages_with_nodes:
        display_nodes.append(
            {
                "id": "__visual_query",
                "label": "Question",
                "slug": "visual/query",
                "stage": "query",
                "description": trace.get("question", ""),
                "visual_only": True,
            }
        )
    if "answer" in stages and "answer" not in stages_with_nodes:
        display_nodes.append(
            {
                "id": "__visual_answer",
                "label": "Answer",
                "slug": "visual/answer",
                "stage": "answer",
                "description": answer_summary or _summary_from_trace(trace),
                "visual_only": True,
            }
        )
    return display_nodes


def _nodes_by_stage(nodes: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        stage = str(node.get("stage") or "evidence").strip() or "evidence"
        grouped[stage].append(node)
    return grouped


def _next_group_top(client: MiroClient, board_id: str) -> float:
    max_bottom = None
    for iterator in (client.list_frames(board_id), client.list_items(board_id)):
        for item in iterator:
            position = item.get("position") or {}
            if "y" not in position:
                continue
            bottom = _item_bottom(item)
            max_bottom = bottom if max_bottom is None else max(max_bottom, bottom)
    if max_bottom is None:
        return 0
    return max_bottom + GROUP_GAP


def _answer_summary(trace: dict, *, store=None, inquiry_slug: str | None = None) -> str:
    if store and inquiry_slug:
        try:
            record = store.read(inquiry_slug)
            extracted = _extract_answer_summary(record.body)
            if extracted:
                return extracted
        except Exception:
            pass
    return _summary_from_trace(trace)


def _extract_answer_summary(body: str) -> str:
    lines = body.splitlines()
    in_answer = False
    collected = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == "## answer":
            in_answer = True
            continue
        if not in_answer:
            continue
        if stripped.startswith("## ") or stripped.startswith("<provenance>") or stripped.startswith("Provenance:"):
            break
        if stripped.startswith("Question:") or stripped in {"Evidence:", "Top matching evidence:", "ID-centered graph context:"}:
            continue
        if stripped:
            collected.append(stripped)
        if len(collected) >= 3:
            break
    return _truncate(" ".join(collected), 320)


def _summary_from_trace(trace: dict) -> str:
    summary = trace.get("provenance_summary")
    if isinstance(summary, dict):
        for key in ["reasoning", "summary", "primary_candidate", "confidence"]:
            value = summary.get(key)
            if value:
                return _truncate(str(value), 320)
    if isinstance(summary, str):
        return _truncate(summary, 320)
    return ""


def _node_note(node: dict, *, store=None, diagnostics: list[str] | None = None) -> str:
    for key in ["citation_snippet", "citation", "description", "detail"]:
        value = node.get(key)
        if value:
            return _truncate(str(value), MAX_NOTE_CHARS)
    if store and node.get("slug") and not node.get("visual_only"):
        try:
            record = store.read(str(node["slug"]))
            summary = _record_summary(record)
            if summary:
                return summary
        except Exception:
            if diagnostics is not None:
                diagnostics.append(f"Could not read KB doc for node {node.get('id')}: {node.get('slug')}")
    return ""


def _record_summary(record) -> str:
    row_data = record.frontmatter.get("row_data")
    if isinstance(row_data, dict) and row_data:
        pieces = []
        for key, value in row_data.items():
            if value is None or value == "":
                continue
            pieces.append(f"{key}: {value}")
            if len(pieces) >= 5:
                break
        return _truncate("; ".join(pieces), MAX_NOTE_CHARS)

    frontmatter_pieces = []
    for key, value in record.frontmatter.items():
        if key in {"type", "slug", "title", "row_data"} or value is None or value == "":
            continue
        frontmatter_pieces.append(f"{key}: {value}")
        if len(frontmatter_pieces) >= 4:
            break
    if frontmatter_pieces:
        return _truncate("; ".join(frontmatter_pieces), MAX_NOTE_CHARS)

    for line in record.body.splitlines():
        stripped = line.strip().strip("#").strip()
        if stripped:
            return _truncate(stripped, MAX_NOTE_CHARS)
    return _truncate(record.title, MAX_NOTE_CHARS)


def _edge_evidence(edge: dict) -> str:
    evidence = edge.get("evidence") or edge.get("description")
    if not evidence:
        return ""
    return _truncate(str(evidence), MAX_EDGE_NOTE_CHARS)


def _shape_html(node: dict) -> str:
    label = str(node.get("label") or node.get("id") or "Node")
    slug = _short_slug(str(node.get("slug") or "visual"))
    if node.get("visual_only"):
        slug = "visual anchor"
    return (
        f"<p><strong>{html.escape(_truncate(label, 54))}</strong></p>"
        f"<p><small>{html.escape(slug)}</small></p>"
    )


def _header_html(trace: dict, *, answer_summary: str, provenance_slug: str | None) -> str:
    question = _truncate(str(trace.get("question") or "Provenance trace"), 420)
    parts = [f"<p><strong>Inquiry</strong>: {html.escape(question)}</p>"]
    if answer_summary:
        parts.append(f"<p><strong>Answer</strong>: {html.escape(answer_summary)}</p>")
    if provenance_slug:
        parts.append(f"<p><small>{html.escape(provenance_slug)}</small></p>")
    return "".join(parts)


def _diagnostics_note(diagnostics: list[str]) -> str:
    visible = diagnostics[:6]
    suffix = "" if len(diagnostics) <= 6 else f"\n...and {len(diagnostics) - 6} more"
    return "Render diagnostics\n" + "\n".join(f"- {item}" for item in visible) + suffix


def _humanize(value: str) -> str:
    return " ".join(part.capitalize() for part in value.replace("-", "_").split("_") if part)


def _short_slug(slug: str) -> str:
    if len(slug) <= 44:
        return slug
    tail = slug.rsplit("/", 1)[-1]
    if len(tail) <= 36:
        return f".../{tail}"
    return "..." + tail[-36:]


def _truncate(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."
