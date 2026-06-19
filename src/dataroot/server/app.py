"""FastAPI app for DataRoot's in-app Ask API."""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from dataroot.agent.tools import ToolExecutor
from dataroot.config import load_config
from dataroot.kb.gitkb_store import GitKBStore
from dataroot.kb.local_store import LocalMarkdownStore
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.query import _extract_provenance, answer_question, persist_answer_artifacts
from dataroot.server.bootstrap import bootstrap_gitkb_runtime


@dataclass(frozen=True)
class CompanyConfig:
    key: str
    label: str
    raw_path: Path


@dataclass
class CompanyWorkspace:
    config: CompanyConfig
    store: Any
    record_count: int
    cached: bool
    backend: str = "local"


class AskRequest(BaseModel):
    company: str = Field(default="company_a")
    question: str
    use_agent: bool = False


class AskResponse(BaseModel):
    answer: str
    question: str
    company: str
    inquiry: str
    provenance_trace: str
    node_count: int
    edge_count: int
    stages: list[str]
    trace: dict[str, Any]
    answer_source: str
    cached_kb: bool
    backend: str


PROJECT_ROOT = Path(os.environ.get("DATAROOT_ROOT", Path.cwd())).resolve()
COMPANIES = {
    "company_a": CompanyConfig(
        key="company_a",
        label="CropProtectorAI",
        raw_path=Path("ExampleData") / "CompanyA_AgriTrait" / "raw",
    ),
    "company_b": CompanyConfig(
        key="company_b",
        label="BioReactorAI",
        raw_path=Path("ExampleData") / "CompanyB_Fermentation" / "raw",
    ),
    "austin_permits": CompanyConfig(
        key="austin_permits",
        label="Austin Permits Explorer",
        raw_path=Path("ExampleData") / "AustinPermits" / "raw",
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


app = FastAPI(title="DataRoot Ask API")
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


@app.get("/")
def index() -> dict[str, Any]:
    return {
        "service": "DataRoot Ask API",
        "rendering": "in_app",
        "workspaces": [{"key": company.key, "label": company.label} for company in COMPANIES.values()],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "rendering": "in_app",
        "companies": [{"key": company.key, "label": company.label} for company in COMPANIES.values()],
    }


@app.get("/api/workspaces")
def list_workspaces() -> dict[str, Any]:
    return {
        "workspaces": [
            {"key": company.key, "label": company.label, "raw_path": company.raw_path.as_posix()}
            for company in COMPANIES.values()
        ]
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    company = _company_config(request.company)
    workspace = _workspace_for(company)
    answer, trace, answer_source = _answer_live_ask(company, workspace, question, use_agent=request.use_agent)
    artifacts = persist_answer_artifacts(workspace.store, question, answer)
    return AskResponse(
        answer=_strip_provenance(answer),
        question=question,
        company=company.key,
        inquiry=artifacts["inquiry"],
        provenance_trace=artifacts["provenance_trace"],
        node_count=len(trace.get("nodes", [])) if isinstance(trace, dict) else 0,
        edge_count=len(trace.get("edges", [])) if isinstance(trace, dict) else 0,
        stages=list(trace.get("stages", [])) if isinstance(trace, dict) else [],
        trace=trace if isinstance(trace, dict) else {},
        answer_source=answer_source,
        cached_kb=workspace.cached,
        backend=workspace.backend,
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


def _answer_live_ask(
    company: CompanyConfig,
    workspace: CompanyWorkspace,
    question: str,
    *,
    use_agent: bool,
) -> tuple[str, dict, str]:
    if use_agent:
        try:
            answer, trace = _answer_with_agent(company, workspace, question)
            return answer, trace, "agent"
        except HTTPException as exc:
            if exc.status_code not in {502, 503}:
                raise

    answer, trace = _answer_with_deterministic_fallback(workspace, question)
    return answer, trace, "deterministic_fallback"


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
            "## Live Ask constraints",
            (
                f"The selected company is {company.label} ({company.key}). "
                f"Use only KB evidence from `{company.raw_path.as_posix()}` or documents that directly cite that company evidence. "
                "Do not call logging or rendering tools. "
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


def _company_config(value: str) -> CompanyConfig:
    normalized = _normalize_key(value)
    key = normalized if normalized in COMPANIES else COMPANY_ALIASES.get(normalized)
    if not key:
        raise HTTPException(status_code=400, detail=f"unknown company: {value}")
    return COMPANIES[key]


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
