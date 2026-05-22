"""
DFDMaker — FastAPI backend (multi-user edition)
"""
from __future__ import annotations

import os
import secrets
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal

from fastapi import Body, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlmodel import Session
from starlette.middleware.sessions import SessionMiddleware

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_ROOT = Path(__file__).resolve().parent
for _import_path in (str(_REPO_ROOT), str(_BACKEND_ROOT)):
    if _import_path not in sys.path:
        sys.path.insert(0, _import_path)

from auth import current_user, optional_user, router as auth_router
from db import get_session, init_db
from generators.diagram_rules import apply_rules_gate
from generators.pen_builder import apply_proposal, build_pen_file
from generators.proposals import generate_erd_m2m_proposals
from generators.sql import export_dbml, export_mermaid, export_sql
from generators.static_analysis import run_full_analysis
from generators.sync_engine import propagate_erd_to_dfd, validate
from llm.mock import mock_chat
from models.db_models import User
from models.pen import DiagramLayout, LayoutEdge, LayoutNode, LayoutPoint, PenFile
from models.source import SourceTableModel
from parsers.csv_parser import parse_csv
from parsers.excel import parse_excel
from repo_cli import analyze_repo
from services.ops_service import OpsService
from services.project_service import ProjectService  # filesystem loaders for bundled fixtures
from services.project_store import ProjectStore       # DB-backed multi-user store
from sharing import require_member, require_owner, router as sharing_router

app = FastAPI(title="DFDMaker API", version="0.2.0")

# ── Middleware ────────────────────────────────────────────────────────────────

_SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
if not os.getenv("SECRET_KEY"):
    print("[dfdmaker] WARN: SECRET_KEY not set — generated ephemeral key (sessions reset on restart)", file=sys.stderr)

# SessionMiddleware first (innermost) so CORS can wrap its responses.
app.add_middleware(
    SessionMiddleware,
    secret_key=_SECRET_KEY,
    session_cookie="dfd_session",
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "0") == "1",
    max_age=60 * 60 * 24 * 14,
)

_FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()
_allow_origins = [_FRONTEND_ORIGIN] if _FRONTEND_ORIGIN else ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(sharing_router)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_upload(file: UploadFile) -> tuple[str, str]:
    suffix = os.path.splitext(file.filename or "upload")[1]
    original = file.filename or "upload"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        return tmp.name, original


def _parse_file(path: str, original_filename: str) -> list[SourceTableModel]:
    ext = os.path.splitext(original_filename)[1].lower()
    if ext in (".xlsx", ".xls"):
        return parse_excel(path, original_filename)
    elif ext == ".csv":
        return [parse_csv(path, original_filename)]
    raise HTTPException(400, f"Unsupported file type: {ext}. Supported: .xlsx, .xls, .csv")


def _persist(pen: PenFile, db: Session, *, owner: User | None = None) -> PenFile:
    """Save a pen to the DB. If owner is provided and project is brand new, create it."""
    if owner is not None:
        return ProjectStore.create(pen, owner, db)
    return ProjectStore.save(pen, db)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest/spreadsheet")
async def ingest_spreadsheet(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
    files: list[UploadFile] = File(...),
    project_name: str = "Untitled Project",
):
    all_tables: list[SourceTableModel] = []
    tmp_paths: list[str] = []
    for file in files:
        tmp_path, original_name = _save_upload(file)
        tmp_paths.append(tmp_path)
        try:
            all_tables.extend(_parse_file(tmp_path, original_name))
        except Exception as e:
            for p in tmp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass
            raise HTTPException(422, f"Failed to parse '{file.filename}': {e}")

    pen = build_pen_file(all_tables, project_name=project_name, source_paths=tmp_paths)
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {
        "project_id": pen.project.id,
        "source_tables": [t.model_dump() for t in all_tables],
        "pen": pen.model_dump(by_alias=True),
    }


@app.post("/schema/blank")
def create_blank_schema(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
    project_name: str = "Untitled Project",
):
    pen = PenFile()
    pen.project.name = project_name
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {"project_id": pen.project.id, "pen": pen.model_dump(by_alias=True)}


@app.post("/projects/import")
def import_project(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
    pen_data: dict = Body(...),
):
    try:
        pen = PenFile.model_validate(pen_data)
    except Exception as e:
        raise HTTPException(422, f"Invalid .dfd.json: {e}")
    # Force a fresh project id so imports don't collide with shared ids.
    import uuid as _uuid
    pen.project.id = str(_uuid.uuid4())
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {"project_id": pen.project.id, "pen": pen.model_dump(by_alias=True)}


def _load_bundled_example(path: Path) -> PenFile:
    if not path.exists():
        raise HTTPException(404, f"Example file not found: {path}")
    pen, _ = ProjectService.open(str(path))
    # Re-id so each load creates a new project owned by the loader.
    import uuid as _uuid
    pen.project.id = str(_uuid.uuid4())
    return pen


@app.post("/schema/example")
def create_example_schema(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    pen = _load_bundled_example(_BACKEND_ROOT / "demo_assets" / "austin_permits.dfd.json")
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {"project_id": pen.project.id, "pen": pen.model_dump(by_alias=True)}


@app.post("/schema/nexus-exercise")
def create_nexus_exercise_schema(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    pen = _load_bundled_example(_BACKEND_ROOT / "demo_assets" / "nexus_candidate_exercise.dfd.json")
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {"project_id": pen.project.id, "pen": pen.model_dump(by_alias=True)}


@app.post("/schema/claude-eval")
def create_claude_eval_schema(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    # The original LabTest eval file isn't in the repo; the self-analysis demo
    # stands in for the "Nexus — Claude" button.
    pen = _load_bundled_example(_BACKEND_ROOT / "demo_assets" / "dfdmaker_self.dfd.json")
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {"project_id": pen.project.id, "pen": pen.model_dump(by_alias=True)}


class RepoAnalysisRequest(BaseModel):
    repo_path: str | None = None
    repo: str | None = None
    output_path: str | None = None
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    max_file_size: int = Field(default=2_000_000, gt=0)


@app.post("/schema/repo-analysis")
def create_repo_analysis_schema(
    req: RepoAnalysisRequest | None = Body(default=None),
    user: Annotated[User | None, Depends(optional_user)] = None,
    db: Annotated[Session | None, Depends(get_session)] = None,
):
    req = req or RepoAnalysisRequest()
    repo_value = (req.repo_path or req.repo or str(_REPO_ROOT)).strip()
    if not repo_value:
        raise HTTPException(400, "repo_path is required")

    repo_path = Path(repo_value).expanduser().resolve()
    if not repo_path.exists():
        raise HTTPException(404, f"Repository path not found: {repo_path}")
    if not repo_path.is_dir():
        raise HTTPException(400, f"Repository path must be a directory: {repo_path}")

    output_path = (
        Path(req.output_path).expanduser().resolve()
        if req.output_path
        else repo_path / ".dfdmaker"
    )

    try:
        result = analyze_repo(
            repo=repo_path,
            output=output_path,
            max_file_size=req.max_file_size,
            include_patterns=req.include,
            exclude_patterns=req.exclude,
        )
        pen = PenFile.model_validate_json(Path(result.pen_path).read_text(encoding="utf-8"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(422, f"Repo analysis failed: {e}")

    import uuid as _uuid
    pen.project.id = str(_uuid.uuid4())
    apply_rules_gate(pen)
    if user is not None and db is not None:
        ProjectStore.create(pen, user, db)
    return {
        "project_id": pen.project.id,
        "path": str(repo_path),
        "output_path": str(output_path),
        "analysis": result.model_dump(),
        "pen": pen.model_dump(by_alias=True),
    }


def _safe_repo_upload_path(filename: str) -> Path:
    normalized = filename.replace("\\", "/").lstrip("/")
    rel_path = PurePosixPath(normalized)
    if not normalized or rel_path.is_absolute() or any(part in ("", ".", "..") for part in rel_path.parts):
        raise HTTPException(400, f"Invalid repository file path: {filename}")
    return Path(*rel_path.parts)


@app.post("/schema/repo-analysis/upload")
async def create_uploaded_repo_analysis_schema(
    files: list[UploadFile] = File(...),
    user: Annotated[User | None, Depends(optional_user)] = None,
    db: Annotated[Session | None, Depends(get_session)] = None,
    max_file_size: int = 2_000_000,
):
    if not files:
        raise HTTPException(400, "No repository files were selected")

    with tempfile.TemporaryDirectory(prefix="dfdmaker_repo_") as tmp_dir:
        repo_path = Path(tmp_dir) / "repo"
        repo_path.mkdir(parents=True, exist_ok=True)

        for file in files:
            rel_path = _safe_repo_upload_path(file.filename or "upload")
            target = repo_path / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            size = 0
            with target.open("wb") as out:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_file_size:
                        raise HTTPException(413, f"Repository file is too large: {file.filename}")
                    out.write(chunk)

        output_path = Path(tmp_dir) / ".dfdmaker"
        try:
            result = analyze_repo(
                repo=repo_path,
                output=output_path,
                max_file_size=max_file_size,
            )
            pen = PenFile.model_validate_json(Path(result.pen_path).read_text(encoding="utf-8"))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(422, f"Repo analysis failed: {e}")

    import uuid as _uuid
    pen.project.id = str(_uuid.uuid4())
    apply_rules_gate(pen)
    if user is not None and db is not None:
        ProjectStore.create(pen, user, db)
    return {
        "project_id": pen.project.id,
        "path": files[0].filename.split("/", 1)[0] if files[0].filename else "uploaded repository",
        "output_path": None,
        "analysis": result.model_dump(),
        "pen": pen.model_dump(by_alias=True),
    }


# ── Project list / persistence ────────────────────────────────────────────────

@app.get("/projects")
def list_projects(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
):
    return {"projects": ProjectStore.list_for_user(user, db)}


class OpenProjectRequest(BaseModel):
    path: str


class SaveProjectRequest(BaseModel):
    project_id: str
    path: str | None = None


@app.post("/projects/open")
def open_project(
    user: Annotated[User, Depends(current_user)],
    db: Annotated[Session, Depends(get_session)],
    req: OpenProjectRequest = Body(...),
):
    """Import a .dfd.json from a server-side path (admin/power-user). Creates a new project owned by caller."""
    try:
        pen, resolved_path = ProjectService.open(req.path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    import uuid as _uuid
    pen.project.id = str(_uuid.uuid4())
    apply_rules_gate(pen)
    ProjectStore.create(pen, user, db)
    return {
        "project_id": pen.project.id,
        "path": resolved_path,
        "pen": pen.model_dump(by_alias=True),
    }


@app.post("/projects/save")
def save_project(
    db: Annotated[Session, Depends(get_session)],
    req: SaveProjectRequest = Body(...),
    user: User = Depends(current_user),
):
    """No-op compat: persistence is automatic. Returns the current pen."""
    # Membership check
    require_member(req.project_id, user, db)
    pen = ProjectStore.load(req.project_id, db)
    return {
        "project_id": pen.project.id,
        "path": None,
        "revision": pen.project.revision,
        "pen": pen.model_dump(by_alias=True),
    }


@app.get("/projects/{project_id}")
def get_project(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    return pen.model_dump(by_alias=True)


@app.get("/projects/{project_id}/revision")
def get_project_revision(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    return ProjectStore.get_revision(project_id, db)


@app.delete("/projects/{project_id}")
def delete_project(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_owner)],
):
    ProjectStore.delete(project_id, db)
    return {"deleted": project_id}


# ── Typed Operations ─────────────────────────────────────────────────────────────

class OpsRequest(BaseModel):
    ops: list[dict[str, Any]]
    base_revision: int | None = None
    propagate: bool = True
    do_validate: bool = True
    save: bool = False
    path: str | None = None


class DiagramScopeRequest(BaseModel):
    diagram: Literal["erd", "dfd"]
    level: Literal["root", "process"] = "root"
    process_id: str | None = None


class LayoutNodePatch(BaseModel):
    id: str
    x: float
    y: float
    width: float | None = None
    height: float | None = None


class LayoutEdgePatch(BaseModel):
    id: str
    route: Literal["orthogonal", "straight", "bezier"] | None = None
    source_handle: str | None = None
    target_handle: str | None = None
    points: list[LayoutPoint] | None = None
    label_t: float | None = None
    label_offset: float | None = None


class LayoutPatchRequest(BaseModel):
    base_revision: int | None = None
    scope: DiagramScopeRequest
    nodes: list[LayoutNodePatch] = Field(default_factory=list)
    edges: list[LayoutEdgePatch] = Field(default_factory=list)


def _ops_require_propagation(ops: list[dict[str, Any]]) -> bool:
    for op_item in ops:
        op = str(op_item.get("op", ""))
        if op.startswith("dfd.") or op.startswith("layout.") or op.startswith("postgres."):
            continue
        return True
    return False


def _layout_for_scope(pen: PenFile, scope: DiagramScopeRequest) -> DiagramLayout:
    if scope.diagram == "erd":
        return pen.layout.erd
    if scope.level == "root":
        return pen.layout.dfd
    if not scope.process_id:
        raise HTTPException(400, "Level 1 DFD layout requires process_id")
    process = next((p for p in pen.dfd.processes if p.id == scope.process_id), None)
    if not process:
        raise HTTPException(400, f"Process not found for Level 1 DFD: {scope.process_id}")
    if process.level_1_diagram is None:
        raise HTTPException(400, f"Process has no Level 1 DFD: {scope.process_id}")
    return pen.layout.dfd_level_1.setdefault(scope.process_id, DiagramLayout())


def _layout_node_ids(pen: PenFile, scope: DiagramScopeRequest) -> set[str]:
    if scope.diagram == "erd":
        return {entity.id for entity in pen.erd.entities if entity.review_status != "rejected"}
    if scope.level == "root":
        dfd = pen.dfd
    else:
        if not scope.process_id:
            raise HTTPException(400, "Level 1 DFD layout requires process_id")
        process = next((p for p in pen.dfd.processes if p.id == scope.process_id), None)
        if not process or process.level_1_diagram is None:
            raise HTTPException(400, f"Process has no Level 1 DFD: {scope.process_id}")
        dfd = process.level_1_diagram
    ids: set[str] = set()
    ids.update(node.id for node in dfd.external_entities)
    ids.update(node.id for node in dfd.processes)
    ids.update(node.id for node in dfd.data_stores)
    return ids


def _layout_edge_ids(pen: PenFile, scope: DiagramScopeRequest) -> set[str]:
    if scope.diagram == "erd":
        return {rel.id for rel in pen.erd.relationships if rel.review_status != "rejected"}
    if scope.level == "root":
        dfd = pen.dfd
    else:
        if not scope.process_id:
            raise HTTPException(400, "Level 1 DFD layout requires process_id")
        process = next((p for p in pen.dfd.processes if p.id == scope.process_id), None)
        if not process or process.level_1_diagram is None:
            raise HTTPException(400, f"Process has no Level 1 DFD: {scope.process_id}")
        dfd = process.level_1_diagram
    return {flow.id for flow in dfd.data_flows}


def _validate_handle(handle: str | None, expected_type: str) -> None:
    if handle is not None and not handle.startswith(f"{expected_type}-"):
        raise HTTPException(400, f"{expected_type}_handle has invalid id: {handle}")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _merge_layout_patch(pen: PenFile, req: LayoutPatchRequest) -> PenFile:
    layout = _layout_for_scope(pen, req.scope)
    node_ids = _layout_node_ids(pen, req.scope)
    edge_ids = _layout_edge_ids(pen, req.scope)

    for patch in req.nodes:
        if patch.id not in node_ids:
            raise HTTPException(400, f"Layout node not found in scope: {patch.id}")
    for patch in req.edges:
        if patch.id not in edge_ids:
            raise HTTPException(400, f"Layout edge not found in scope: {patch.id}")
        _validate_handle(patch.source_handle, "source")
        _validate_handle(patch.target_handle, "target")

    for patch in req.nodes:
        existing = next((node for node in layout.nodes if node.id == patch.id), None)
        if existing is None:
            layout.nodes.append(LayoutNode(
                id=patch.id, x=patch.x, y=patch.y,
                width=patch.width or 280.0, height=patch.height or 180.0,
            ))
        else:
            existing.x = patch.x
            existing.y = patch.y
            if patch.width is not None:
                existing.width = patch.width
            if patch.height is not None:
                existing.height = patch.height

    for patch in req.edges:
        existing = next((edge for edge in layout.edges if edge.id == patch.id), None)
        if existing is None:
            layout.edges.append(LayoutEdge(
                id=patch.id,
                route=patch.route or "orthogonal",
                source_handle=patch.source_handle,
                target_handle=patch.target_handle,
                points=patch.points or [],
                label_t=_clamp(patch.label_t, 0.0, 1.0) if patch.label_t is not None else None,
                label_offset=_clamp(patch.label_offset, -80.0, 80.0) if patch.label_offset is not None else None,
            ))
        else:
            if patch.route is not None:
                existing.route = patch.route
            if "source_handle" in patch.model_fields_set:
                existing.source_handle = patch.source_handle
            if "target_handle" in patch.model_fields_set:
                existing.target_handle = patch.target_handle
            if "points" in patch.model_fields_set:
                existing.points = patch.points or []
            if "label_t" in patch.model_fields_set:
                existing.label_t = _clamp(patch.label_t, 0.0, 1.0) if patch.label_t is not None else None
            if "label_offset" in patch.model_fields_set:
                existing.label_offset = _clamp(patch.label_offset, -80.0, 80.0) if patch.label_offset is not None else None

    return pen


@app.post("/projects/{project_id}/ops")
def apply_ops(
    project_id: str,
    req: OpsRequest,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    current = ProjectStore.load(project_id, db)
    if req.base_revision is not None and current.project.revision != req.base_revision:
        raise HTTPException(409, {
            "message": f"Revision mismatch: expected {req.base_revision}, found {current.project.revision}",
            "current_revision": current.project.revision,
        })

    applied = []
    pen = current
    try:
        for op_item in req.ops:
            op = op_item["op"]
            payload = op_item.get("payload", {})
            pen = OpsService.apply_op(pen, op, payload)
            applied.append({"op": op, "payload": payload})
    except ValueError as e:
        raise HTTPException(400, str(e))

    if req.propagate and _ops_require_propagation(req.ops):
        propagate_erd_to_dfd(pen)

    if req.do_validate:
        conflicts = validate(pen)
        blocking = [c for c in conflicts if c.severity == "blocking"]
        if blocking:
            raise HTTPException(409, {
                "conflicts": [c.to_dict() for c in conflicts],
                "applied": applied,
            })

    pen.project.revision += 1
    ProjectStore.save(pen, db)

    return {
        "project_id": project_id,
        "revision": pen.project.revision,
        "applied": applied,
        "conflicts": [],
        "warnings": [],
        "pen": pen.model_dump(by_alias=True),
    }


@app.patch("/schema/{project_id}/layout")
def patch_layout(
    project_id: str,
    req: LayoutPatchRequest,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    current = ProjectStore.load(project_id, db)
    if req.base_revision is not None and current.project.revision != req.base_revision:
        raise HTTPException(409, {
            "message": f"Revision mismatch: expected {req.base_revision}, found {current.project.revision}",
            "current_revision": current.project.revision,
        })

    updated = _merge_layout_patch(current, req)
    updated.project.revision = (current.project.revision or 0) + 1
    ProjectStore.save(updated, db)
    return updated.model_dump(by_alias=True)


@app.get("/schema/{project_id}")
def get_schema(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    return pen.model_dump(by_alias=True)


class ApplyProposalRequest(BaseModel):
    proposal_id: str
    answer_index: int


@app.post("/schema/{project_id}/apply-proposal")
def apply_proposal_route(
    project_id: str,
    req: ApplyProposalRequest,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    try:
        pen = apply_proposal(pen, req.proposal_id, req.answer_index)
    except ValueError as e:
        raise HTTPException(400, str(e))
    apply_rules_gate(pen)
    pen.project.revision += 1
    ProjectStore.save(pen, db)
    return pen.model_dump(by_alias=True)


@app.patch("/schema/{project_id}/pen")
def update_pen(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
    pen_data: dict = Body(...),
):
    current = ProjectStore.load(project_id, db)
    try:
        updated = PenFile.model_validate(pen_data)
    except Exception as e:
        raise HTTPException(422, f"Invalid pen data: {e}")

    new_m2m = generate_erd_m2m_proposals(updated)
    if new_m2m:
        updated.review.proposals.extend(new_m2m)

    apply_rules_gate(updated)
    # apply_rules_gate already ran validate() internally; reuse its results
    # via review.warnings instead of paying for another full validate pass.
    blocking = [w for w in updated.review.warnings if w.severity == "blocking"]
    if blocking:
        raise HTTPException(409, {"conflicts": [w.model_dump() for w in blocking]})

    updated.project.id = current.project.id
    updated.project.revision = (current.project.revision or 0) + 1
    ProjectStore.save(updated, db)
    return updated.model_dump(by_alias=True)


@app.post("/schema/{project_id}/validate")
def validate_schema(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    conflicts = validate(pen)
    return {
        "valid": len(conflicts) == 0,
        "conflicts": [c.to_dict() for c in conflicts],
    }


@app.delete("/schema/{project_id}/entity/{entity_id}")
def delete_entity(
    project_id: str,
    entity_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
    force: bool = False,
):
    pen = ProjectStore.load(project_id, db)

    entity = next((e for e in pen.erd.entities if e.id == entity_id), None)
    if not entity:
        raise HTTPException(404, f"Entity '{entity_id}' not found")

    cascade_rels = [
        r for r in pen.erd.relationships
        if r.from_.entity_id == entity_id or r.to.entity_id == entity_id
    ]
    cascade_rel_ids = {r.id for r in cascade_rels}

    stores_to_remove = [s for s in pen.dfd.data_stores if s.mapped_erd_entity == entity_id]
    procs_to_remove = [p for p in pen.dfd.processes if p.mapped_relationship_id in cascade_rel_ids]

    if not force:
        user_modified_objects = [
            {"type": "DataStore", "id": s.id, "name": s.name}
            for s in stores_to_remove if s.user_modified
        ] + [
            {"type": "Process", "id": p.id, "name": p.name}
            for p in procs_to_remove if p.user_modified
        ]
        if user_modified_objects:
            raise HTTPException(409, {
                "message": "Cannot delete entity: user-modified DFD objects would be removed.",
                "would_remove": user_modified_objects,
            })

    pen.erd.entities = [e for e in pen.erd.entities if e.id != entity_id]
    pen.erd.relationships = [r for r in pen.erd.relationships if r.id not in cascade_rel_ids]
    store_ids_removed = {s.id for s in stores_to_remove}
    proc_ids_removed = {p.id for p in procs_to_remove}
    pen.dfd.data_stores = [s for s in pen.dfd.data_stores if s.id not in store_ids_removed]
    pen.dfd.processes = [p for p in pen.dfd.processes if p.id not in proc_ids_removed]
    pen.dfd.data_flows = [f for f in pen.dfd.data_flows if f.mapped_relationship_id not in cascade_rel_ids]

    propagate_erd_to_dfd(pen)
    pen.project.revision += 1
    ProjectStore.save(pen, db)
    return pen.model_dump(by_alias=True)


@app.delete("/schema/{project_id}/relationship/{rel_id}")
def delete_relationship(
    project_id: str,
    rel_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    rel = next((r for r in pen.erd.relationships if r.id == rel_id), None)
    if not rel:
        raise HTTPException(404, f"Relationship '{rel_id}' not found")

    proc = next((p for p in pen.dfd.processes if p.mapped_relationship_id == rel_id), None)
    if proc and proc.user_modified:
        raise HTTPException(409, {
            "message": (
                f"Cannot delete relationship: Process '{proc.name}' "
                f"was manually modified. Delete or re-map the Process first."
            ),
            "process_id": proc.id,
        })

    pen.erd.relationships = [r for r in pen.erd.relationships if r.id != rel_id]
    if proc:
        pen.dfd.processes = [p for p in pen.dfd.processes if p.id != proc.id]
    pen.dfd.data_flows = [f for f in pen.dfd.data_flows if f.mapped_relationship_id != rel_id]

    propagate_erd_to_dfd(pen)
    pen.project.revision += 1
    ProjectStore.save(pen, db)
    return pen.model_dump(by_alias=True)


class AnalyzeResponse(BaseModel):
    valid: bool
    blocking_count: int
    warning_count: int
    static_issue_count: int
    conflicts: list[dict]
    static_issues: list[dict]


@app.get("/schema/{project_id}/analyze")
def analyze_schema(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    conflicts, issues = run_full_analysis(pen)
    blocking = [c for c in conflicts if c.severity == "blocking"]
    warnings = [c for c in conflicts if c.severity == "warning"]
    return {
        "valid": len(blocking) == 0,
        "blocking_count": len(blocking),
        "warning_count": len(warnings) + sum(1 for i in issues if i.severity == "warning"),
        "static_issue_count": len(issues),
        "conflicts": [c.to_dict() for c in conflicts],
        "static_issues": [i.to_dict() for i in issues],
    }


class ChatRequest(BaseModel):
    message: str
    context: Literal["erd", "dfd", "both"] = "both"


class FixSuggestionResponse(BaseModel):
    op: str
    payload: dict
    label: str
    reason: str


class ChatResponse(BaseModel):
    message: str
    suggestions: list[FixSuggestionResponse] = []


@app.post("/llm/chat")
def chat_route(
    project_id: str,
    req: ChatRequest,
    db: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(current_user)],
):
    require_member(project_id, user, db)
    pen = ProjectStore.load(project_id, db)
    reply = mock_chat(req.message, pen)
    return ChatResponse(
        message=reply.message,
        suggestions=[
            FixSuggestionResponse(op=s.op, payload=s.payload, label=s.label, reason=s.reason)
            for s in reply.suggestions
        ],
    )


@app.get("/schema/{project_id}/export/sql", response_class=PlainTextResponse)
def export_sql_route(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    return export_sql(ProjectStore.load(project_id, db))


@app.get("/schema/{project_id}/export/mermaid", response_class=PlainTextResponse)
def export_mermaid_route(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    return export_mermaid(ProjectStore.load(project_id, db))


@app.get("/schema/{project_id}/export/dbml", response_class=PlainTextResponse)
def export_dbml_route(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    return export_dbml(ProjectStore.load(project_id, db))


@app.get("/schema/{project_id}/export/pen", response_class=PlainTextResponse)
def export_pen_route(
    project_id: str,
    db: Annotated[Session, Depends(get_session)],
    _: Annotated[User, Depends(require_member)],
):
    pen = ProjectStore.load(project_id, db)
    return PlainTextResponse(
        content=pen.model_dump_json(by_alias=True, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{pen.project.name}.pen.json"'},
    )


class WaitlistEntry(BaseModel):
    name: str
    email: str
    project_url: str = ""
    message: str = ""


@app.post("/waitlist")
def join_waitlist(entry: WaitlistEntry, db: Annotated[Session, Depends(get_session)]):
    from models.db_models import WaitlistSubmission
    row = WaitlistSubmission(
        name=entry.name,
        email=entry.email,
        project_url=entry.project_url,
        message=entry.message,
    )
    db.add(row)
    db.commit()
    return {"status": "ok"}


# ── SPA static serving ────────────────────────────────────────────────────────
# Mounted last so all API routes win first.

_DIST = _REPO_ROOT / "frontend" / "dist"
if _DIST.exists():
    _ASSETS = _DIST / "assets"
    if _ASSETS.exists():
        app.mount("/assets", StaticFiles(directory=str(_ASSETS)), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Serve any matching file in dist (favicon, vite.svg, etc.)
        if full_path:
            candidate = _DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
        index = _DIST / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(404, "Not found")
