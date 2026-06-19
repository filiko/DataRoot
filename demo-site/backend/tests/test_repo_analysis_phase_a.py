from __future__ import annotations

from pathlib import Path
import json

from fastapi.testclient import TestClient

from generators.diagram_rules import apply_rules_gate
from models.pen import BusinessRule, Connector, PenFile
from repo_analysis.compiler import compile_pen_from_facts
from repo_analysis.fastapi_provider import (
    auto_accept_phase_a_facts,
    collect_fastapi_routes,
    route_evidence_to_facts,
)
from repo_analysis.gitkb_provider import collect_gitkb_evidence, gitkb_evidence_to_facts
from repo_analysis.inventory import build_inventory
from repo_analysis.model_provider import collect_model_evidence, model_evidence_to_facts
from repo_cli import analyze_repo


def test_inventory_excludes_generated_dirs(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.py").write_text("print('skip')\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "ignored.pyc").write_bytes(b"skip")

    inventory = build_inventory(tmp_path)

    paths = {item.path for item in inventory.files}
    assert "app/main.py" in paths
    assert "node_modules/ignored.py" not in paths
    assert "__pycache__/ignored.pyc" not in paths


def test_inventory_honors_include_exclude_globs(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "app" / "skip.py").write_text("print('skip')\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")

    inventory = build_inventory(
        tmp_path,
        include_patterns=["app/*.py"],
        exclude_patterns=["*/skip.py"],
    )

    assert {item.path for item in inventory.files} == {"app/main.py"}


def test_fastapi_provider_detects_routes(tmp_path: Path) -> None:
    app_file = tmp_path / "main.py"
    app_file.write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "",
            "@app.post('/items')",
            "async def create_item():",
            "    return {'ok': True}",
            "",
            "@app.get('/items/{item_id}')",
            "def get_item(item_id: str):",
            "    return {'id': item_id}",
        ]),
        encoding="utf-8",
    )

    inventory = build_inventory(tmp_path)
    evidence = collect_fastapi_routes(tmp_path, inventory)

    routes = {
        (record.attributes["method"], record.attributes["route_path"], record.attributes["handler"])
        for record in evidence
    }
    assert ("POST", "/items", "create_item") in routes
    assert ("GET", "/items/{item_id}", "get_item") in routes


def test_fastapi_provider_detects_router_prefixes(tmp_path: Path) -> None:
    app_file = tmp_path / "routes.py"
    app_file.write_text(
        "\n".join([
            "from fastapi import APIRouter",
            "api_router = APIRouter(prefix='/api')",
            "",
            "@api_router.get(path='/items')",
            "def list_items():",
            "    return []",
        ]),
        encoding="utf-8",
    )

    evidence = collect_fastapi_routes(tmp_path, build_inventory(tmp_path))

    assert {
        (record.attributes["method"], record.attributes["route_path"], record.attributes["handler"])
        for record in evidence
    } == {("GET", "/api/items", "list_items")}


def test_process_fact_ids_are_unique_per_route(tmp_path: Path) -> None:
    app_file = tmp_path / "main.py"
    app_file.write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "@app.get('/items')",
            "@app.post('/items')",
            "def items():",
            "    return []",
        ]),
        encoding="utf-8",
    )

    evidence = collect_fastapi_routes(tmp_path, build_inventory(tmp_path))
    facts = route_evidence_to_facts(evidence)

    assert len(facts) == len({fact.id for fact in facts})
    assert {
        fact.subject
        for fact in facts
        if fact.type == "flow.process"
    } == {"process:fastapi:GET:/items", "process:fastapi:POST:/items"}


def test_compiler_emits_valid_penfile(tmp_path: Path) -> None:
    app_file = tmp_path / "main.py"
    app_file.write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "@app.get('/health')",
            "def health():",
            "    return {'status': 'ok'}",
        ]),
        encoding="utf-8",
    )

    inventory = build_inventory(tmp_path)
    evidence = collect_fastapi_routes(tmp_path, inventory)
    facts = auto_accept_phase_a_facts(route_evidence_to_facts(evidence))
    pen = compile_pen_from_facts(facts, "Fixture Repo Analysis", tmp_path)

    validated = PenFile.model_validate(pen.model_dump(by_alias=True))
    assert validated.project.name == "Fixture Repo Analysis"
    assert len(validated.dfd.external_entities) == 1
    assert len(validated.dfd.processes) == 1
    assert len(validated.dfd.data_flows) == 2
    assert validated.dfd.processes[0].source_evidence
    assert validated.dfd.processes[0].source_facts
    assert validated.dfd.data_flows[0].source_evidence
    assert validated.layout.dfd.nodes


def test_rules_gate_preserves_dfd_behavioral_metadata() -> None:
    pen = PenFile()
    pen.dfd.business_rules.append(
        BusinessRule(
            id="rule_batch_release",
            title="Only released batches can ship",
            statement="A batch must be released before it can enter fulfillment.",
        )
    )
    pen.dfd.connectors.append(
        Connector(
            id="conn_batch_release",
            name="Batch release fan-out",
            trigger="batch.status changes to released",
            effect="downstream modules can allocate inventory",
            from_context="quality",
            to_contexts=["sales", "finance"],
        )
    )

    apply_rules_gate(pen)

    assert [rule.id for rule in pen.dfd.business_rules] == ["rule_batch_release"]
    assert [connector.id for connector in pen.dfd.connectors] == ["conn_batch_release"]


def test_compiler_ignores_candidate_and_rejected_facts(tmp_path: Path) -> None:
    app_file = tmp_path / "main.py"
    app_file.write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "@app.get('/health')",
            "def health():",
            "    return {'status': 'ok'}",
        ]),
        encoding="utf-8",
    )

    evidence = collect_fastapi_routes(tmp_path, build_inventory(tmp_path))
    candidate_facts = route_evidence_to_facts(evidence)
    candidate_pen = compile_pen_from_facts(candidate_facts, "Candidate Repo Analysis", tmp_path)
    assert candidate_pen.dfd.processes == []

    accepted_facts = auto_accept_phase_a_facts(candidate_facts)
    accepted_facts[0].status = "rejected"
    rejected_pen = compile_pen_from_facts(accepted_facts, "Rejected Repo Analysis", tmp_path)
    assert rejected_pen.dfd.processes == []


def test_model_provider_populates_erd_entities_and_relationships(tmp_path: Path) -> None:
    app_file = tmp_path / "models.py"
    app_file.write_text(
        "\n".join([
            "from pydantic import BaseModel",
            "",
            "class Customer(BaseModel):",
            "    id: str",
            "    email: str",
            "",
            "class Order(BaseModel):",
            "    id: str",
            "    customer: Customer",
            "    total: float",
        ]),
        encoding="utf-8",
    )

    evidence = collect_model_evidence(tmp_path, build_inventory(tmp_path))
    facts = auto_accept_phase_a_facts(model_evidence_to_facts(evidence))
    pen = compile_pen_from_facts(facts, "Model Repo Analysis", tmp_path)

    assert {entity.name for entity in pen.erd.entities} == {"customer", "order"}
    assert len(pen.erd.relationships) == 1
    assert {store.name for store in pen.dfd.data_stores} == {"Customer", "Order"}


def test_gitkb_provider_reads_symbol_and_call_artifacts(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "gitkb"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "summary.txt").write_text("index: exit 0\n", encoding="utf-8")
    (artifact_dir / "symbols_python.txt").write_text(
        "\n".join([
            "Python symbols (1 total)",
            "",
            "function     build_dfd_from_erd                      backend/generators/dfd_builder.py:143",
        ]),
        encoding="utf-8",
    )
    (artifact_dir / "symbols_typescript.txt").write_text("", encoding="utf-8")
    (artifact_dir / "callees_propagate_erd_to_dfd.txt").write_text(
        "\n".join([
            "Callees of propagate_erd_to_dfd (1)",
            "",
            "  calls: build_dfd_from_erd",
        ]),
        encoding="utf-8",
    )

    evidence = collect_gitkb_evidence(tmp_path, artifact_dir)
    facts = auto_accept_phase_a_facts(gitkb_evidence_to_facts(evidence))

    assert any(record.type == "code_symbol" for record in evidence)
    assert any(record.type == "code_call_edge" for record in evidence)
    assert {"code.symbol", "code.call_edge"}.issubset({fact.type for fact in facts})


def test_analyze_repo_writes_outputs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "@app.post('/upload')",
            "def upload():",
            "    return {'ok': True}",
        ]),
        encoding="utf-8",
    )
    output = tmp_path / "out"

    result = analyze_repo(repo=repo, output=output)

    assert result.route_count == 1
    assert Path(result.project_config_path).exists()
    assert Path(result.inventory_path).exists()
    assert Path(result.evidence_path).exists()
    assert Path(result.facts_path).exists()
    assert Path(result.decisions_path).exists()
    assert Path(result.run_log_path).exists()
    assert Path(result.pen_path).exists()
    PenFile.model_validate_json(Path(result.pen_path).read_text(encoding="utf-8"))

    facts = [
        json.loads(line)
        for line in Path(result.facts_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {fact["status"] for fact in facts} == {"accepted"}

    run_logs = [
        json.loads(line)
        for line in Path(result.run_log_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert {record["provider"] for record in run_logs} == {
        "inventory",
        "fastapi_ast",
        "model_ast",
        "gitkb_artifacts",
        "fact_generation",
        "pen_compiler",
    }


def test_repo_analysis_api_accepts_arbitrary_repo_path(tmp_path: Path) -> None:
    from main import RepoAnalysisRequest, create_repo_analysis_schema

    repo = tmp_path / "other_repo"
    repo.mkdir()
    (repo / "service.py").write_text(
        "\n".join([
            "from fastapi import FastAPI",
            "app = FastAPI()",
            "@app.get('/status')",
            "def status():",
            "    return {'ok': True}",
        ]),
        encoding="utf-8",
    )
    output = tmp_path / "analysis_out"

    response = create_repo_analysis_schema(
        RepoAnalysisRequest(repo_path=str(repo), output_path=str(output))
    )

    assert response["path"] == str(repo.resolve())
    assert response["output_path"] == str(output.resolve())
    assert response["analysis"]["route_count"] == 1
    assert response["analysis"]["process_count"] == 1
    assert response["pen"]["project"]["name"] == "other_repo Repo Analysis"


def test_repo_analysis_upload_accepts_folder_picker_files() -> None:
    from main import app

    client = TestClient(app)
    response = client.post(
        "/schema/repo-analysis/upload",
        files=[
            (
                "files",
                (
                    "picked_repo/main.py",
                    "\n".join([
                        "from fastapi import FastAPI",
                        "app = FastAPI()",
                        "@app.get('/picked')",
                        "def picked():",
                        "    return {'ok': True}",
                    ]),
                    "text/x-python",
                ),
            )
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "picked_repo"
    assert payload["analysis"]["route_count"] == 1
    assert payload["analysis"]["process_count"] == 1
    assert payload["pen"]["dfd"]["processes"][0]["name"] == "Picked"
