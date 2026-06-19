from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from models.pen import PenFile
from repo_analysis.compiler import compile_pen_from_facts
from repo_analysis.systemmap_to_pen import synthesize_behavioral_layer
from repo_analysis.evidence_store import write_evidence_jsonl
from repo_analysis.fact_store import write_facts_jsonl
from repo_analysis.fastapi_provider import (
    auto_accept_phase_a_facts,
    collect_fastapi_routes,
    route_evidence_to_facts,
)
from repo_analysis.gitkb_provider import (
    collect_gitkb_evidence,
    gitkb_artifact_status,
    gitkb_evidence_to_facts,
)
from repo_analysis.inventory import build_inventory
from repo_analysis.model_provider import collect_model_evidence, model_evidence_to_facts
from repo_analysis.models import AnalyzeResult, utc_now_iso


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _git_output(repo: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _git_default_branch(repo: Path) -> str | None:
    origin_head = _git_output(repo, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    if origin_head:
        return origin_head.removeprefix("origin/")
    return _git_output(repo, ["branch", "--show-current"])


def _provider_timer() -> tuple[str, float]:
    return utc_now_iso(), time.perf_counter()


def _provider_log(
    run_id: str,
    provider: str,
    started_at: str,
    started_perf: float,
    records: int,
    status: str = "ok",
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "provider": provider,
        "status": status,
        "started_at": started_at,
        "duration_ms": int((time.perf_counter() - started_perf) * 1000),
        "records": records,
    }


def analyze_repo(
    repo: Path,
    output: Path,
    max_file_size: int = 2_000_000,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    use_gitkb: str = "auto",
    gitkb_artifacts: Path | None = None,
) -> AnalyzeResult:
    repo = repo.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    include_patterns = include_patterns or []
    exclude_patterns = exclude_patterns or []
    if use_gitkb not in {"auto", "on", "off"}:
        raise ValueError("use_gitkb must be one of: auto, on, off")
    gitkb_artifacts = gitkb_artifacts or (repo / "artifacts" / "gitkb")
    if not gitkb_artifacts.is_absolute():
        gitkb_artifacts = repo / gitkb_artifacts
    gitkb_status = "off" if use_gitkb == "off" else gitkb_artifact_status(gitkb_artifacts)
    if use_gitkb == "on" and gitkb_status != "available":
        raise FileNotFoundError(f"GitKB artifacts are required but unavailable at {gitkb_artifacts}: {gitkb_status}")
    gitkb_provider_state = (
        "off" if use_gitkb == "off"
        else "auto-used" if use_gitkb == "auto" and gitkb_status == "available"
        else "on-used" if use_gitkb == "on" and gitkb_status == "available"
        else f"auto-{gitkb_status}"
    )
    run_id = f"run_{utc_now_iso()}"
    run_logs: list[dict[str, object]] = []

    project_config_path = output / "project.json"
    project_config_path.write_text(
        json.dumps({
            "documentType": "dfdmaker.repo-run",
            "schemaVersion": "0.1",
            "repo": {
                "root": ".",
                "path": str(repo),
                "git_commit": _git_output(repo, ["rev-parse", "HEAD"]),
                "default_branch": _git_default_branch(repo),
            },
            "output": {
                "path": _relative_or_absolute(output, repo),
                "pen_file": "project.dfd.json",
            },
            "analysis": {
                "max_file_size": max_file_size,
                "include": include_patterns,
                "exclude": exclude_patterns,
            },
            "providers": {
                "gitkb": gitkb_provider_state,
                "fastapi": True,
                "inventory": True,
                "model_ast": True,
            },
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    decisions_path = output / "decisions.json"
    decisions_path.write_text(
        json.dumps({
            "documentType": "dfdmaker.decisions",
            "schemaVersion": "0.1",
            "decisions": [],
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    started_at, started_perf = _provider_timer()
    inventory = build_inventory(
        repo,
        max_file_size=max_file_size,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )
    run_logs.append(_provider_log(run_id, "inventory", started_at, started_perf, len(inventory.files)))
    inventory_path = output / "inventory.json"
    inventory_path.write_text(
        inventory.model_dump_json(indent=2),
        encoding="utf-8",
    )

    started_at, started_perf = _provider_timer()
    fastapi_evidence = collect_fastapi_routes(repo, inventory)
    run_logs.append(_provider_log(run_id, "fastapi_ast", started_at, started_perf, len(fastapi_evidence)))

    started_at, started_perf = _provider_timer()
    model_evidence = collect_model_evidence(repo, inventory)
    run_logs.append(_provider_log(run_id, "model_ast", started_at, started_perf, len(model_evidence)))

    gitkb_evidence = []
    if use_gitkb != "off" and gitkb_status == "available":
        started_at, started_perf = _provider_timer()
        gitkb_evidence = collect_gitkb_evidence(repo, gitkb_artifacts)
        run_logs.append(_provider_log(run_id, "gitkb_artifacts", started_at, started_perf, len(gitkb_evidence)))
    elif use_gitkb != "off":
        started_at, started_perf = _provider_timer()
        run_logs.append(_provider_log(run_id, "gitkb_artifacts", started_at, started_perf, 0, status=gitkb_status))

    evidence = fastapi_evidence + model_evidence + gitkb_evidence
    evidence_path = output / "evidence.jsonl"
    write_evidence_jsonl(evidence_path, evidence)

    started_at, started_perf = _provider_timer()
    facts = auto_accept_phase_a_facts(
        route_evidence_to_facts(fastapi_evidence)
        + model_evidence_to_facts(model_evidence)
        + gitkb_evidence_to_facts(gitkb_evidence)
    )
    run_logs.append(_provider_log(run_id, "fact_generation", started_at, started_perf, len(facts)))
    facts_path = output / "facts.jsonl"
    write_facts_jsonl(facts_path, facts)

    started_at, started_perf = _provider_timer()
    pen = compile_pen_from_facts(
        facts=facts,
        project_name=f"{repo.name} Repo Analysis",
        repo_root=repo,
    )
    # Behavioral layer: detect real business rules (validators/state machines)
    # and connectors (middleware/auth/outbound calls) so the Business Rules and
    # Connectors tabs are populated with evidence-linked content for this repo.
    rules, connectors = synthesize_behavioral_layer(repo, inventory)
    pen.dfd.business_rules = rules
    pen.dfd.connectors = connectors
    run_logs.append(_provider_log(run_id, "pen_compiler", started_at, started_perf, len(pen.dfd.processes)))
    pen_path = output / "project.dfd.json"
    pen_path.write_text(
        pen.model_dump_json(by_alias=True, indent=2),
        encoding="utf-8",
    )
    PenFile.model_validate_json(pen_path.read_text(encoding="utf-8"))

    run_log_path = output / "run-log.jsonl"
    run_log_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in run_logs),
        encoding="utf-8",
    )

    result = AnalyzeResult(
        project_config_path=str(project_config_path),
        inventory_path=str(inventory_path),
        evidence_path=str(evidence_path),
        facts_path=str(facts_path),
        decisions_path=str(decisions_path),
        run_log_path=str(run_log_path),
        pen_path=str(pen_path),
        route_count=len(fastapi_evidence),
        process_count=len(pen.dfd.processes),
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze a repo and emit a DFDMaker PenFile.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Run Phase A repo analysis.")
    analyze.add_argument("--repo", default=".", help="Repository root to analyze.")
    analyze.add_argument("--output", default=".dfdmaker", help="Output directory.")
    analyze.add_argument("--include", action="append", default=[], help="Only include files matching this glob. May be repeated.")
    analyze.add_argument("--exclude", action="append", default=[], help="Exclude files matching this glob. May be repeated.")
    analyze.add_argument("--max-file-size", type=int, default=2_000_000)
    analyze.add_argument("--use-gitkb", choices=["auto", "on", "off"], default="auto")
    analyze.add_argument("--gitkb-artifacts", default="artifacts/gitkb")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        result = analyze_repo(
            repo=Path(args.repo),
            output=Path(args.output),
            max_file_size=args.max_file_size,
            include_patterns=args.include,
            exclude_patterns=args.exclude,
            use_gitkb=args.use_gitkb,
            gitkb_artifacts=Path(args.gitkb_artifacts),
        )
        print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
