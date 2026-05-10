"""FastAPI app for the DataRoot Miro board integration."""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from dataroot.agent.tools import ToolExecutor
from dataroot.config import load_config
from dataroot.kb.gitkb_store import GitKBStore
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.query import _extract_provenance, answer_question, persist_answer_artifacts
from dataroot.render.miro import (
    MiroAPIError,
    MiroClient,
    clear_live_ask_section_to_miro,
    extract_live_ask_question_text,
    is_live_ask_question_input,
    miro_access_token_from_env,
    render_provenance_to_miro,
)
from dataroot.server.bootstrap import bootstrap_gitkb_runtime


@dataclass(frozen=True)
class CompanyConfig:
    key: str
    label: str
    raw_path: Path
    board_env: str


@dataclass
class CompanyWorkspace:
    config: CompanyConfig
    store: Any
    record_count: int
    cached: bool
    backend: str = "local"


class AskRenderRequest(BaseModel):
    company: str = Field(default="company_a")
    question: str
    board_id: str | None = None
    use_agent: bool = False
    include_proof: bool = False


class BoardQuestionRequest(BaseModel):
    company: str | None = None
    board_id: str | None = None
    include_proof: bool = False


class LiveAskBoardInputRequest(BaseModel):
    board_id: str | None = None
    input_item_id: str
    question: str = ""
    include_proof: bool = False


class AskRenderResponse(BaseModel):
    answer: str
    question: str
    board_url: str
    company: str
    inquiry: str
    provenance_trace: str
    node_count: int
    edge_count: int
    stages: list[str]
    answer_source: str
    interpreter_source: str
    planner_source: str
    proof_included: bool
    cached_kb: bool
    section_status: str
    trigger_source: str


PROJECT_ROOT = Path(os.environ.get("DATAROOT_ROOT", Path.cwd())).resolve()
COMPANIES = {
    "company_a": CompanyConfig(
        key="company_a",
        label="CropProtectorAI",
        raw_path=Path("ExampleData") / "CompanyA_AgriTrait" / "raw",
        board_env="MIRO_COMPANY_A_ASK_BOARD_ID",
    ),
    "company_b": CompanyConfig(
        key="company_b",
        label="BioReactorAI",
        raw_path=Path("ExampleData") / "CompanyB_Fermentation" / "raw",
        board_env="MIRO_COMPANY_B_ASK_BOARD_ID",
    ),
    "austin_permits": CompanyConfig(
        key="austin_permits",
        label="Austin Permits Explorer",
        raw_path=Path("ExampleData") / "AustinPermits" / "raw",
        board_env="MIRO_AUSTIN_PERMITS_BOARD_ID",
    ),
}
COMPANY_ALIASES = {
    "companya": "company_a",
    "companyaagritrait": "company_a",
    "companyaagri": "company_a",
    "agritrait": "company_a",
    "cropprotectorai": "company_a",
    "cropprotector": "company_a",
    "tomato": "company_a",
    "companyb": "company_b",
    "companybfermentation": "company_b",
    "bioreactorai": "company_b",
    "bioreactor": "company_b",
    "fermentation": "company_b",
    "austin": "austin_permits",
    "austinpermits": "austin_permits",
    "permits": "austin_permits",
    "austinpermitsexplorer": "austin_permits",
    "texas": "austin_permits",
    "opendata": "austin_permits",
}
BOARD_ID_PLACEHOLDERS = {
    "optionalexistingboardid",
    "existingboardid",
    "boardid",
    "currentboardid",
}


app = FastAPI(title="DataRoot Miro Panel")
_workspace_cache: dict[str, CompanyWorkspace] = {}
_cache_lock = threading.Lock()
LIVE_ASK_TOOL_NAMES = {
    "kb_search",
    "kb_semantic",
    "kb_show",
    "kb_list",
    "kb_graph",
    "find_candidate_paths",
    "query_table",
}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "companies": [{"key": company.key, "label": company.label} for company in COMPANIES.values()],
    }


@app.get("/miro/", response_class=HTMLResponse)
def miro_board_only_page() -> HTMLResponse:
    return HTMLResponse(_MIRO_BOARD_ONLY_HTML)


@app.get("/miro/sdk", response_class=HTMLResponse)
def miro_sdk_entrypoint() -> HTMLResponse:
    return HTMLResponse(_MIRO_SDK_HTML)


@app.post("/api/ask-render", response_model=AskRenderResponse)
def ask_render(request: AskRenderRequest) -> AskRenderResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    company = _company_config(request.company)
    load_config(PROJECT_ROOT)
    board_id = _board_id_for(company, request.board_id)
    if not board_id:
        raise HTTPException(
            status_code=400,
            detail=f"board_id is required unless {company.board_env} or MIRO_BOARD_ID is set",
        )

    return _run_live_ask(
        company=company,
        board_id=board_id,
        question=question,
        include_proof=request.include_proof,
        trigger_source="api_submit",
    )


@app.post("/api/ask-render-board-question", response_model=AskRenderResponse)
def ask_render_board_question(request: BoardQuestionRequest) -> AskRenderResponse:
    load_config(PROJECT_ROOT)
    company = _company_config(request.company) if request.company else None
    board_id = _board_id_for(company, request.board_id) if company else _board_id_for_any_company(request.board_id)
    if not board_id:
        raise HTTPException(
            status_code=400,
            detail="board_id is required unless MIRO_BOARD_ID is set",
        )

    if company:
        question = _board_live_ask_question(company, board_id)
    else:
        company, question = _infer_board_live_ask_question(board_id)

    return _run_live_ask(
        company=company,
        board_id=board_id,
        question=question,
        include_proof=request.include_proof,
        trigger_source="board_question_submit",
    )


@app.post("/api/live-ask-board-input", response_model=AskRenderResponse)
def live_ask_board_input(request: LiveAskBoardInputRequest) -> AskRenderResponse:
    load_config(PROJECT_ROOT)
    board_id = _board_id_for_any_company(request.board_id)
    if not board_id:
        raise HTTPException(status_code=400, detail="board_id is required unless MIRO_BOARD_ID is set")

    company, section_title = _live_ask_section_for_input_item(board_id, request.input_item_id)
    question = request.question.strip()
    if not question:
        try:
            board_url = clear_live_ask_section_to_miro(board_id=board_id, section_title=section_title)
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return AskRenderResponse(
            answer="",
            question="",
            board_url=board_url,
            company=company.key,
            inquiry="",
            provenance_trace="",
            node_count=0,
            edge_count=0,
            stages=[],
            answer_source="cleared",
            interpreter_source="cleared",
            planner_source="cleared",
            proof_included=False,
            cached_kb=False,
            section_status="cleared",
            trigger_source="board_input_poll",
        )

    return _run_live_ask(
        company=company,
        board_id=board_id,
        question=question,
        include_proof=request.include_proof,
        trigger_source="board_input_poll",
    )


def _run_live_ask(
    *,
    company: CompanyConfig,
    board_id: str,
    question: str,
    include_proof: bool,
    trigger_source: str,
) -> AskRenderResponse:
    workspace = _workspace_for(company)
    answer, trace, answer_source = _answer_live_ask(company, workspace, question)
    artifacts = persist_answer_artifacts(workspace.store, question, answer)

    render_metadata: dict[str, str] = {}
    try:
        board_url = render_provenance_to_miro(
            trace,
            store=workspace.store,
            inquiry_slug=artifacts["inquiry"],
            board_id=board_id,
            provenance_slug=artifacts["provenance_trace"],
            context_label=company.label,
            section_title=f"{company.label} - Live Ask",
            update_existing_section=True,
            include_proof=include_proof,
            render_metadata=render_metadata,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AskRenderResponse(
        answer=_strip_provenance(answer),
        question=question,
        board_url=board_url,
        company=company.key,
        inquiry=artifacts["inquiry"],
        provenance_trace=artifacts["provenance_trace"],
        node_count=len(trace.get("nodes", [])) if isinstance(trace, dict) else 0,
        edge_count=len(trace.get("edges", [])) if isinstance(trace, dict) else 0,
        stages=list(trace.get("stages", [])) if isinstance(trace, dict) else [],
        answer_source=answer_source,
        interpreter_source=render_metadata.get("interpreter_source") or "deterministic_fallback",
        planner_source=render_metadata.get("planner_source") or "deterministic_fallback",
        proof_included=include_proof,
        cached_kb=workspace.cached,
        section_status=render_metadata.get("section_status") or "updated",
        trigger_source=trigger_source,
    )


def _workspace_for(company: CompanyConfig) -> CompanyWorkspace:
    with _cache_lock:
        cached = _workspace_cache.get(company.key)
        if cached:
            return cached

        load_config(PROJECT_ROOT)
        raw_path = (PROJECT_ROOT / company.raw_path).resolve()
        if not raw_path.exists():
            raise HTTPException(status_code=500, detail=f"company raw data not found: {raw_path}")

        if _use_gitkb_server_store():
            try:
                bootstrap_gitkb_runtime(PROJECT_ROOT)
                store = GitKBStore(PROJECT_ROOT)
                records = store.list()
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            workspace = CompanyWorkspace(
                config=company,
                store=store,
                record_count=len(records),
                cached=bool(records),
                backend="gitkb",
            )
            _workspace_cache[company.key] = workspace
            return workspace

        kb_root = PROJECT_ROOT / ".dataroot" / "server_cache" / company.key / "kb"
        store = LocalMarkdownStore(kb_root)
        existing_records = store.list()
        was_cached = bool(existing_records)
        if not existing_records:
            profile_workspace(raw_path, store)
            link_workspace(store)
        elif not any(record.doc_type == "relationship" for record in existing_records):
            link_workspace(store)

        workspace = CompanyWorkspace(
            config=company,
            store=store,
            record_count=len(store.list()),
            cached=was_cached,
            backend="local",
        )
        _workspace_cache[company.key] = workspace
        return workspace


def _answer_with_agent(company: CompanyConfig, workspace: CompanyWorkspace, question: str) -> tuple[str, dict]:
    if not (os.environ.get("OPENAI_API_KEY") or os.environ.get("MINIMAX_API_KEY")):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY or MINIMAX_API_KEY is required for live ask.")

    try:
        from dataroot.agent.runner import Runner
        from dataroot.agent.tool_sets import get_tools

        result = Runner().run(
            _query_agent_prompt(company),
            _live_ask_tools(get_tools("query_agent")),
            [{"role": "user", "content": question}],
            _LiveAskToolExecutor(workspace.store, company, scope_enabled=workspace.backend == "gitkb"),
            temperature=0.2,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"live ask agent failed: {exc}") from exc

    if result.error:
        raise HTTPException(status_code=502, detail=f"live ask agent failed: {result.error}")

    answer = (result.final_output or "").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="live ask agent returned no answer.")

    trace = _validated_agent_trace(answer)
    return answer, trace


def _answer_live_ask(company: CompanyConfig, workspace: CompanyWorkspace, question: str) -> tuple[str, dict, str]:
    try:
        answer, trace = _answer_with_agent(company, workspace, question)
        return answer, trace, "agent"
    except HTTPException as exc:
        if exc.status_code not in {502, 503}:
            raise

    answer, trace = _answer_with_deterministic_fallback(workspace, question)
    return answer, trace, "deterministic_fallback"


def _answer_with_deterministic_fallback(workspace: CompanyWorkspace, question: str) -> tuple[str, dict]:
    answer = answer_question(workspace.store, question).strip()
    if not answer:
        answer = f"Question: {question}\n\nNo matching KB documents were found."

    trace = _extract_provenance(answer)
    if not _is_valid_trace(trace):
        trace = {"question": question, "nodes": [], "edges": [], "stages": ["query", "search", "answer"]}
        answer = "\n".join([_strip_provenance(answer), "", "<provenance>", json.dumps(trace, indent=2), "</provenance>"])
    return answer, trace


def _is_valid_trace(trace: Any) -> bool:
    return (
        isinstance(trace, dict)
        and "raw" not in trace
        and isinstance(trace.get("nodes"), list)
        and isinstance(trace.get("edges"), list)
        and isinstance(trace.get("stages"), list)
    )


def _query_agent_prompt(company: CompanyConfig) -> str:
    prompt_path = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "query_agent.md"
    base_prompt = prompt_path.read_text(encoding="utf-8")
    return "\n\n".join(
        [
            base_prompt,
            "## Live Ask demo constraints",
            (
                f"The selected company is {company.label} ({company.key}). "
                f"Use only KB evidence from `{company.raw_path.as_posix()}` or documents that directly cite that company evidence. "
                "Do not cite another demo company. Do not call logging or rendering tools. "
                "Return a natural-language answer followed by exactly one valid `<provenance>` JSON block."
            ),
        ]
    )


def _live_ask_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        tool
        for tool in tools
        if str((tool.get("function") or {}).get("name") or "") in LIVE_ASK_TOOL_NAMES
    ]


def _validated_agent_trace(answer: str) -> dict:
    trace = _extract_provenance(answer)
    if not isinstance(trace, dict) or "raw" in trace:
        raise HTTPException(status_code=502, detail="live ask agent did not return valid provenance JSON.")
    for key in ("nodes", "edges", "stages"):
        if not isinstance(trace.get(key), list):
            raise HTTPException(status_code=502, detail=f"live ask provenance must include a {key} array.")
    return trace


class _LiveAskToolExecutor:
    def __init__(self, store, company: CompanyConfig, *, scope_enabled: bool):
        self._executor = ToolExecutor(store)
        self._company = company
        self._scope_enabled = scope_enabled

    def __call__(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        if tool_name not in LIVE_ASK_TOOL_NAMES:
            raise ValueError(f"Tool is not allowed for live ask: {tool_name}")

        if self._scope_enabled and not self._tool_args_in_scope(tool_name, tool_args):
            return {"error": f"{tool_name} target is outside selected company scope."}

        result = self._executor(tool_name, tool_args)
        if not self._scope_enabled:
            return result
        return _filter_scoped_tool_result(result, self._company)

    def _tool_args_in_scope(self, tool_name: str, tool_args: dict[str, Any]) -> bool:
        if tool_name in {"kb_show", "kb_graph"}:
            return _slug_in_company_scope(str(tool_args.get("slug") or ""), self._company)
        if tool_name == "query_table":
            return _slug_in_company_scope(str(tool_args.get("table_slug") or ""), self._company)
        return True


def _filter_scoped_tool_result(value: Any, company: CompanyConfig) -> Any:
    if isinstance(value, list):
        return [item for item in value if _tool_result_item_in_scope(item, company)]
    if isinstance(value, dict) and isinstance(value.get("nodes"), dict):
        nodes = {
            slug: node
            for slug, node in value["nodes"].items()
            if _slug_in_company_scope(str(slug), company)
        }
        edges = [
            edge
            for edge in value.get("edges", [])
            if _slug_in_company_scope(str(edge.get("source") or ""), company)
            and _slug_in_company_scope(str(edge.get("target") or ""), company)
        ]
        filtered = dict(value)
        filtered["nodes"] = nodes
        filtered["edges"] = edges
        return filtered
    return value


def _tool_result_item_in_scope(item: Any, company: CompanyConfig) -> bool:
    if not isinstance(item, dict):
        return False
    if isinstance(item.get("path"), list):
        return all(_slug_in_company_scope(str(slug), company) for slug in item["path"])
    for key in ("slug", "row_slug", "table_slug", "start", "target"):
        value = item.get(key)
        if value and _slug_in_company_scope(str(value), company):
            return True
    return False


def _slug_in_company_scope(slug: str, company: CompanyConfig) -> bool:
    normalized = slug.replace("\\", "/").strip("/").lower()
    if not normalized:
        return False
    if normalized.startswith(("domain_specs/", "workspaces/", "inquiries/", "provenance_traces/")):
        return True

    scope_terms = _company_scope_terms(company)
    if any(term in normalized for term in scope_terms):
        return True

    id_prefix = "a-" if company.key == "company_a" else "b-"
    return normalized.startswith(f"relationships/{id_prefix}") or f"/{id_prefix}" in normalized


def _company_scope_terms(company: CompanyConfig) -> tuple[str, ...]:
    parts = [part for part in company.raw_path.parts if part.lower() != "exampledata"]
    company_root = parts[0] if parts else company.key
    raw_path = "/".join(parts)
    return tuple(
        item
        for item in {
            _scope_slug(company_root),
            _scope_slug(raw_path),
            company.key.lower(),
            company.label.lower(),
        }
        if item
    )


def _scope_slug(value: str) -> str:
    value = value.replace("\\", "/").strip().strip("/").lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9._/\-]+", "_", value)
    value = re.sub(r"/+", "/", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_")


def _board_live_ask_question(company: CompanyConfig, board_id: str) -> str:
    frames, items = _board_frames_and_items(board_id)
    return _live_ask_question_from_items(company, frames, items)


def _infer_board_live_ask_question(board_id: str) -> tuple[CompanyConfig, str]:
    frames, items = _board_frames_and_items(board_id)
    matches: list[tuple[CompanyConfig, str]] = []
    for company in COMPANIES.values():
        question = _live_ask_question_from_items(company, frames, items, missing_ok=True)
        if question:
            matches.append((company, question))

    if not matches:
        raise HTTPException(status_code=400, detail="Type a question in one Live Ask board text box before clicking the DataRoot app icon.")
    if len(matches) > 1:
        labels = ", ".join(company.label for company, _question in matches)
        raise HTTPException(status_code=400, detail=f"Only one Live Ask question can be active at a time. Clear one of: {labels}.")
    return matches[0]


def _live_ask_section_for_input_item(board_id: str, input_item_id: str) -> tuple[CompanyConfig, str]:
    cleaned_id = input_item_id.strip()
    if not cleaned_id:
        raise HTTPException(status_code=400, detail="input_item_id is required")

    frames, items = _board_frames_and_items(board_id)
    item = next((candidate for candidate in items if _server_item_id(candidate) == cleaned_id), None)
    if not item:
        raise HTTPException(status_code=400, detail="Live Ask input item was not found on this board.")

    parent_id = _server_parent_id(item)
    section = next((frame for frame in frames if _server_item_id(frame) == parent_id), None)
    section_title = _server_item_title(section or {})
    if not section_title.endswith(" - Live Ask"):
        raise HTTPException(status_code=400, detail="Live Ask input item must belong to a Live Ask section.")

    company = _company_for_live_ask_section_title(section_title)
    if not company:
        raise HTTPException(status_code=400, detail=f'Unknown Live Ask section: "{section_title}"')
    return company, section_title


def _board_frames_and_items(board_id: str) -> tuple[list[dict], list[dict]]:
    token = miro_access_token_from_env()
    if not token:
        raise HTTPException(status_code=502, detail="MIRO_ACCESS_TOKEN is required to read the board question.")

    client = MiroClient(token)
    try:
        return list(client.list_frames(board_id)), list(client.list_items(board_id))
    except MiroAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _live_ask_question_from_items(
    company: CompanyConfig,
    frames: list[dict],
    items: list[dict],
    *,
    missing_ok: bool = False,
) -> str:
    section_title = f"{company.label} - Live Ask"
    section = _find_board_frame(frames, section_title)
    if not section:
        if missing_ok:
            return ""
        raise HTTPException(status_code=400, detail=f'Live Ask section not found: "{section_title}"')

    section_id = _server_item_id(section)
    children = [item for item in items if _server_parent_id(item) == section_id]
    inputs = [item for item in children if is_live_ask_question_input(item)]
    if not inputs:
        if missing_ok:
            return ""
        raise HTTPException(
            status_code=400,
            detail="Live Ask question input not found. Refresh the demo board before submitting.",
        )

    for item in inputs:
        question = extract_live_ask_question_text(item).strip()
        if question:
            return question

    if missing_ok:
        return ""
    raise HTTPException(status_code=400, detail="Type a question in the Live Ask board text box before submitting.")


def _find_board_frame(frames: list[dict], title: str) -> dict | None:
    matches = [frame for frame in frames if _server_item_title(frame) == title]
    matches.sort(key=lambda frame: str(_server_item_id(frame)))
    return matches[0] if matches else None


def _server_item_id(item: dict) -> str:
    value = item.get("id") or (item.get("data") or {}).get("id")
    return str(value) if value else ""


def _server_item_title(item: dict) -> str:
    data = item.get("data") or {}
    return str(item.get("title") or data.get("title") or "").strip()


def _server_parent_id(item: dict) -> str:
    parent = item.get("parent") or {}
    value = parent.get("id") or item.get("parentId") or item.get("parent_id")
    return str(value) if value else ""


def _company_for_live_ask_section_title(title: str) -> CompanyConfig | None:
    for company in COMPANIES.values():
        if title == f"{company.label} - Live Ask":
            return company
    return None


def _company_config(value: str) -> CompanyConfig:
    normalized = _normalize_key(value)
    key = normalized if normalized in COMPANIES else COMPANY_ALIASES.get(normalized)
    if not key:
        raise HTTPException(status_code=400, detail=f"unknown company: {value}")
    return COMPANIES[key]


def _board_id_for(company: CompanyConfig, explicit: str | None) -> str | None:
    return (
        _usable_board_id(explicit)
        or _usable_board_id(os.environ.get(company.board_env))
        or _usable_board_id(os.environ.get("MIRO_BOARD_ID"))
    )


def _board_id_for_any_company(explicit: str | None) -> str | None:
    return _usable_board_id(explicit) or _usable_board_id(os.environ.get("MIRO_BOARD_ID"))


def _usable_board_id(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    normalized = _normalize_key(cleaned)
    if normalized in BOARD_ID_PLACEHOLDERS or normalized.startswith("optional"):
        return None
    return cleaned


def _use_gitkb_server_store() -> bool:
    backend = os.environ.get("DATAROOT_SERVER_KB_BACKEND")
    if backend:
        return backend.lower() == "gitkb"
    if os.environ.get("RAILWAY_ENVIRONMENT"):
        return True
    return os.environ.get("DATAROOT_KB_BACKEND", "").lower() == "gitkb" and GitKBStore.is_available()


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _strip_provenance(answer: str) -> str:
    return re.sub(r"\n?<provenance>\s*.*?\s*</provenance>\s*", "", answer, flags=re.DOTALL).strip()


_MIRO_BOARD_ONLY_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DataRoot</title>
</head>
<body>
  <main>
    <h1>DataRoot runs from the Miro board.</h1>
    <p>Type into the Live Ask text box on the board, then click the DataRoot app icon.</p>
  </main>
</body>
</html>
"""


_MIRO_PANEL_HTML = _MIRO_BOARD_ONLY_HTML


_MIRO_SDK_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DataRoot Miro SDK</title>
  <script src="https://miro.com/app/static/sdk/v2/miro.js"></script>
</head>
<body>
  <script>
    const LIVE_ASK_INPUT_LABEL = "Type your question here:";
    const LIVE_ASK_POLL_MS = 5000;
    const LIVE_ASK_PLACEHOLDERS = new Set([
      "",
      "type your question here",
      "type your question here:",
      "ask your question",
      "enter your question"
    ]);
    let liveAskRunning = false;
    let liveAskPrimed = false;
    let lastSubmittedLiveAskKey = "";
    const observedLiveAskInputs = new Map();

    async function notify(message) {
      try {
        if (miro.board.notifications && miro.board.notifications.show) {
          await miro.board.notifications.show(message);
        }
      } catch (error) {
        console.warn(error);
      }
    }

    function itemId(item) {
      return String((item && (item.id || (item.data && item.data.id))) || "");
    }

    function itemContent(item) {
      return String((item && (item.content || (item.data && item.data.content))) || "");
    }

    function htmlToText(value) {
      const node = document.createElement("div");
      node.innerHTML = value || "";
      return (node.textContent || node.innerText || "").replace(/\\s+/g, " ").trim();
    }

    function plainItemText(item) {
      return htmlToText(itemContent(item));
    }

    function isLiveAskInput(item) {
      return plainItemText(item).toLowerCase().includes(LIVE_ASK_INPUT_LABEL.toLowerCase());
    }

    function extractLiveAskQuestion(item) {
      let text = plainItemText(item);
      const labelIndex = text.toLowerCase().indexOf(LIVE_ASK_INPUT_LABEL.toLowerCase());
      if (labelIndex >= 0) {
        text = text.slice(labelIndex + LIVE_ASK_INPUT_LABEL.length);
      }
      const question = text.replace(/^[\\s:-]+|[\\s:-]+$/g, "");
      return LIVE_ASK_PLACEHOLDERS.has(question.toLowerCase()) ? "" : question;
    }

    function liveAskSubmitKey(inputItemId, question) {
      return `${inputItemId}\\n${question}`;
    }

    async function submitLiveAskInput(item, question) {
      if (liveAskRunning) {
        return;
      }
      const inputItemId = itemId(item);
      if (!inputItemId) {
        return;
      }
      liveAskRunning = true;
      const emptyQuestion = question.trim() === "";
      await notify(emptyQuestion ? "DataRoot is clearing the Live Ask section." : "DataRoot is answering the Live Ask question.");
      try {
        const info = await miro.board.getInfo();
        const response = await fetch("/api/live-ask-board-input", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({board_id: info.id, input_item_id: inputItemId, question})
        });
        const responseText = await response.text();
        let payload = {};
        try {
          payload = responseText ? JSON.parse(responseText) : {};
        } catch (error) {
          payload = {detail: responseText};
        }
        if (!response.ok) {
          throw new Error(payload.detail || "DataRoot live ask failed.");
        }
        lastSubmittedLiveAskKey = liveAskSubmitKey(inputItemId, question);
        await notify(emptyQuestion ? "DataRoot cleared the Live Ask section." : "DataRoot updated the Live Ask section.");
      } catch (error) {
        await notify(error.message || "DataRoot live ask failed.");
        throw error;
      } finally {
        liveAskRunning = false;
      }
    }

    async function pollLiveAskInputs() {
      if (liveAskRunning) {
        return;
      }
      let inputs = [];
      try {
        const textItems = await miro.board.get({type: ["text"]});
        inputs = textItems.filter((item) => isLiveAskInput(item) || observedLiveAskInputs.has(itemId(item)));
      } catch (error) {
        console.warn("DataRoot Live Ask poll failed", error);
        return;
      }

      const now = Date.now();
      if (!liveAskPrimed) {
        for (const item of inputs) {
          observedLiveAskInputs.set(itemId(item), {question: extractLiveAskQuestion(item), stableSince: now});
        }
        liveAskPrimed = true;
        return;
      }

      for (const item of inputs) {
        const inputItemId = itemId(item);
        if (!inputItemId) {
          continue;
        }
        const question = extractLiveAskQuestion(item);
        const observed = observedLiveAskInputs.get(inputItemId);
        if (!observed || observed.question !== question) {
          observedLiveAskInputs.set(inputItemId, {question, stableSince: now});
          continue;
        }
        if (now - observed.stableSince < LIVE_ASK_POLL_MS) {
          continue;
        }
        if (lastSubmittedLiveAskKey === liveAskSubmitKey(inputItemId, question)) {
          continue;
        }
        await submitLiveAskInput(item, question);
        break;
      }
    }

    async function runDataRootLiveAsk() {
      if (liveAskRunning) {
        await notify("DataRoot Live Ask is already running.");
        return;
      }
      liveAskRunning = true;
      await notify("DataRoot is reading the Live Ask question from the board.");
      try {
        const info = await miro.board.getInfo();
        const response = await fetch("/api/ask-render-board-question", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({board_id: info.id})
        });
        const responseText = await response.text();
        let payload = {};
        try {
          payload = responseText ? JSON.parse(responseText) : {};
        } catch (error) {
          payload = {detail: responseText};
        }
        if (!response.ok) {
          throw new Error(payload.detail || "DataRoot live ask failed.");
        }
        await notify("DataRoot updated the Live Ask section.");
      } catch (error) {
        await notify(error.message || "DataRoot live ask failed.");
        throw error;
      } finally {
        liveAskRunning = false;
      }
    }

    async function registerDataRootActions() {
      await miro.board.ui.on("icon:click", runDataRootLiveAsk);

      try {
        await miro.board.ui.on("custom:run-live-ask", runDataRootLiveAsk);
        if (miro.board.experimental && miro.board.experimental.action) {
          await miro.board.experimental.action.register({
            event: "run-live-ask",
            ui: {
              label: {en: "Run DataRoot"},
              icon: "chat-two",
              description: "Run Live Ask from the board question."
            },
            scope: "local",
            selection: "single",
            predicate: {
              $or: [
                {type: "shape"},
                {type: "text"},
                {type: "sticky_note"}
              ]
            },
            contexts: {item: {}}
          });
        }
      } catch (error) {
        console.warn("DataRoot custom action unavailable", error);
      }
    }

    async function startDataRootLiveAskWatcher() {
      await registerDataRootActions();
      await pollLiveAskInputs();
      setInterval(pollLiveAskInputs, LIVE_ASK_POLL_MS);
    }

    startDataRootLiveAskWatcher();
  </script>
</body>
</html>
"""
