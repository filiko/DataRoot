"""FastAPI app for the DataRoot Miro panel."""

from __future__ import annotations

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
from dataroot.render.miro import render_provenance_to_miro
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


class AskRenderResponse(BaseModel):
    answer: str
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


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "companies": [{"key": company.key, "label": company.label} for company in COMPANIES.values()],
    }


@app.get("/miro/", response_class=HTMLResponse)
def miro_panel() -> HTMLResponse:
    return HTMLResponse(_MIRO_PANEL_HTML)


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

    workspace = _workspace_for(company)
    answer, answer_source = _answer_with_optional_agent(workspace.store, question, use_agent=request.use_agent)
    artifacts = persist_answer_artifacts(workspace.store, question, answer)
    trace = _extract_provenance(answer)

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
            include_proof=request.include_proof,
            render_metadata=render_metadata,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return AskRenderResponse(
        answer=_strip_provenance(answer),
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
        proof_included=request.include_proof,
        cached_kb=workspace.cached,
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


def _answer_with_optional_agent(store, question: str, *, use_agent: bool) -> tuple[str, str]:
    model_requested = use_agent or os.environ.get("DATAROOT_USE_MODEL_ASK") == "1"
    if model_requested and os.environ.get("OPENAI_API_KEY"):
        try:
            from dataroot.agent.runner import Runner
            from dataroot.agent.tool_sets import get_tools

            prompt_path = Path(__file__).resolve().parents[1] / "agent" / "prompts" / "query_agent.md"
            system_prompt = prompt_path.read_text(encoding="utf-8")
            result = Runner().run(
                system_prompt,
                get_tools("query_agent"),
                [{"role": "user", "content": question}],
                ToolExecutor(store),
                temperature=0.2,
            )
            if result.final_output and "<provenance>" in result.final_output:
                return result.final_output, "agent"
        except Exception:
            pass

    return answer_question(store, question), "deterministic"


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


_MIRO_PANEL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DataRoot</title>
  <script src="https://miro.com/app/static/sdk/v2/miro.js"></script>
  <style>
    :root {
      color-scheme: light;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172033;
      background: #f7f8fb;
    }
    body {
      margin: 0;
      min-height: 100vh;
      background: #f7f8fb;
    }
    main {
      width: min(760px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 24px 16px 32px;
    }
    h1 {
      margin: 0 0 16px;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    label {
      display: block;
      margin: 14px 0 6px;
      font-size: 13px;
      font-weight: 650;
      color: #33415f;
    }
    select,
    input,
    textarea {
      box-sizing: border-box;
      width: 100%;
      border: 1px solid #c9d1df;
      border-radius: 8px;
      padding: 10px 11px;
      font: inherit;
      background: #ffffff;
      color: #172033;
    }
    textarea {
      min-height: 132px;
      resize: vertical;
      line-height: 1.45;
    }
    .option-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      font-size: 13px;
      font-weight: 600;
      color: #33415f;
    }
    .option-row input {
      width: auto;
      margin: 0;
    }
    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 42px;
      margin-top: 16px;
      border: 0;
      border-radius: 8px;
      padding: 0 16px;
      font: inherit;
      font-weight: 700;
      color: #ffffff;
      background: #0d6efd;
      cursor: pointer;
    }
    button:disabled {
      cursor: wait;
      background: #8392aa;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .status {
      margin-top: 16px;
      min-height: 20px;
      font-size: 13px;
      color: #50607c;
    }
    .result {
      margin-top: 16px;
      border-top: 1px solid #d8deea;
      padding-top: 16px;
      white-space: pre-wrap;
      line-height: 1.48;
    }
    .meta {
      margin-top: 12px;
      display: grid;
      gap: 6px;
      font-size: 13px;
      color: #50607c;
    }
    a {
      color: #0b5ed7;
      overflow-wrap: anywhere;
    }
    @media (max-width: 620px) {
      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>DataRoot</h1>
    <div class="grid">
      <div>
        <label for="company">Company</label>
        <select id="company">
          <option value="company_a">CropProtectorAI</option>
          <option value="company_b">BioReactorAI</option>
        </select>
      </div>
      <div>
        <label for="board">Board ID</label>
        <input id="board" autocomplete="off" placeholder="Current board auto-detected">
      </div>
    </div>
    <label for="question">Question</label>
    <textarea id="question">What specific genes make Solara-14 powdery mildew resistant?</textarea>
    <label class="option-row" for="include-proof">
      <input id="include-proof" type="checkbox">
      Include precise proof frame
    </label>
    <button id="submit" type="button">Ask DataRoot</button>
    <div id="status" class="status"></div>
    <section id="result" class="result" hidden></section>
    <section id="meta" class="meta" hidden></section>
  </main>
  <script>
    const statusEl = document.getElementById("status");
    const resultEl = document.getElementById("result");
    const metaEl = document.getElementById("meta");
    const boardEl = document.getElementById("board");
    const submitEl = document.getElementById("submit");
    const includeProofEl = document.getElementById("include-proof");

    async function hydrateBoardId() {
      try {
        if (window.miro && miro.board && miro.board.getInfo) {
          const info = await miro.board.getInfo();
          if (info && info.id) {
            boardEl.value = info.id;
            statusEl.textContent = "Ready.";
          }
        } else {
          statusEl.textContent = "Open this panel from the Miro app icon to auto-detect the board.";
        }
      } catch (error) {
        statusEl.textContent = "Could not read the current board. Enter the board ID or use the hosted default.";
      }
    }

    async function ask() {
      submitEl.disabled = true;
      statusEl.textContent = "Profiling, answering, and rendering...";
      resultEl.hidden = true;
      metaEl.hidden = true;
      try {
        const requestBody = {
          company: document.getElementById("company").value,
          question: document.getElementById("question").value,
          include_proof: includeProofEl.checked
        };
        const boardId = boardEl.value.trim();
        if (boardId) requestBody.board_id = boardId;
        const response = await fetch("/api/ask-render", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(requestBody)
        });
        const responseText = await response.text();
        let payload = {};
        try {
          payload = responseText ? JSON.parse(responseText) : {};
        } catch (error) {
          payload = {detail: responseText};
        }
        if (!response.ok) {
          throw new Error(payload.detail || "Request failed");
        }
        resultEl.textContent = payload.answer;
        resultEl.hidden = false;
        metaEl.innerHTML = `
          <div>Rendered ${payload.node_count} nodes and ${payload.edge_count} edges from ${payload.answer_source} answer.</div>
          <div>Interpreter: ${payload.interpreter_source}; Miro planner: ${payload.planner_source}; proof frame: ${payload.proof_included ? "included" : "not included"}.</div>
          <div>Provenance: ${payload.provenance_trace}</div>
          <div><a href="${payload.board_url}" target="_blank" rel="noreferrer">Open Miro board</a></div>
        `;
        metaEl.hidden = false;
        statusEl.textContent = "Rendered to Miro.";
      } catch (error) {
        statusEl.textContent = error.message;
      } finally {
        submitEl.disabled = false;
      }
    }

    submitEl.addEventListener("click", ask);
    hydrateBoardId();
  </script>
</body>
</html>
"""


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
    async function openDataRootPanel() {
      await miro.board.ui.openPanel({url: "/miro/"});
    }

    miro.board.ui.on("icon:click", openDataRootPanel);
  </script>
</body>
</html>
"""
