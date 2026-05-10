"""DataRoot command line interface."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from dataroot.config import DataRootConfig, load_config, write_config
from dataroot.domain import apply_domain_spec, infer_domain_spec
from dataroot.kb.factory import make_store
from dataroot.link import link_workspace
from dataroot.profile import profile_workspace
from dataroot.query import answer_question, persist_answer_artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dataroot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--backend", choices=["gitkb"], default="gitkb")

    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("path")

    subparsers.add_parser("link")

    infer_parser = subparsers.add_parser("infer-domain-spec")
    infer_parser.add_argument("--output", default=".dataroot/domain_spec.yaml")

    apply_parser = subparsers.add_parser("apply-domain-spec")
    apply_parser.add_argument("--spec", default=".dataroot/domain_spec.yaml")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--type")
    list_parser.add_argument("--path-prefix")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("slug")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)

    graph_parser = subparsers.add_parser("graph")
    graph_parser.add_argument("slug")
    graph_parser.add_argument("--direction", choices=["inbound", "outbound", "both"], default="both")
    graph_parser.add_argument("--depth", type=int, default=2)

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("question")

    miro_parser = subparsers.add_parser("miro")
    miro_parser.add_argument("provenance_slug")
    miro_parser.add_argument("--board-id")

    refresh_parser = subparsers.add_parser("miro-refresh-board")
    refresh_parser.add_argument("--board-id", required=True)
    refresh_parser.add_argument("--preserve-title", default="DataRoot Provenance")
    refresh_parser.add_argument("--dry-run", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    subparsers.add_parser("mcp", help="Run the DataRoot stdio MCP server (requires git-kb).")

    args = parser.parse_args(argv)
    root = Path.cwd()

    if args.command == "serve":
        import uvicorn

        uvicorn.run("dataroot.server.app:app", host=args.host, port=args.port, reload=args.reload)
        return 0

    if args.command == "mcp":
        from dataroot.mcp.server import run_stdio

        return run_stdio()

    if args.command == "init":
        config = DataRootConfig(root=root, kb_backend=args.backend)
        write_config(config)
        store = _make_store_or_exit(parser, config)
        store.init()
        print("Initialized DataRoot with backend: gitkb")
        return 0

    if args.command == "miro-refresh-board":
        from dataroot.render.miro_refresh import refresh_ask_board

        load_config(root)
        try:
            result = refresh_ask_board(
                root=root,
                board_id=args.board_id,
                preserve_title=args.preserve_title,
                dry_run=args.dry_run,
            )
        except (RuntimeError, FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
            parser.exit(1, f"error: {exc}\n")
        _print_miro_refresh_result(result)
        return 0

    config = load_config(root)
    store = _make_store_or_exit(parser, config)

    if args.command == "profile":
        summary = profile_workspace(Path(args.path), store)
        print(
            f"Profiled {summary.files_seen} files, wrote {summary.records_written} records"
            f" ({summary.skipped_files} skipped)."
        )
        return 0

    if args.command == "link":
        summary = link_workspace(store)
        print(
            f"Linked workspace: {summary.relationship_docs} relationship docs, "
            f"{summary.documents_updated} docs updated, {summary.links_added} links considered."
        )
        return 0

    if args.command == "infer-domain-spec":
        summary = infer_domain_spec(store, root / args.output)
        print(
            f"Wrote {summary.output_path} with {summary.entities} entities and "
            f"{summary.relationships} relationships."
        )
        return 0

    if args.command == "apply-domain-spec":
        summary = apply_domain_spec(store, root / args.spec)
        print(f"Applied domain spec to {summary.updated_docs} documents.")
        return 0

    if args.command == "list":
        for record in store.list(doc_type=args.type, path_prefix=args.path_prefix):
            print(f"{record.slug}\t{record.doc_type}\t{record.title}")
        return 0

    if args.command == "show":
        record = store.read(_normalize_slug(args.slug))
        print(json.dumps(record.normalized_frontmatter(), indent=2, default=str))
        if record.body:
            print()
            print(record.body)
        return 0

    if args.command == "search":
        for result in store.search(args.query, limit=args.limit):
            print(f"{result.slug}\t{result.doc_type}\t{result.score}\t{result.title}")
            if result.snippet:
                print(f"  {result.snippet}")
        return 0

    if args.command == "graph":
        graph = store.graph(_normalize_slug(args.slug), direction=args.direction, depth=args.depth)
        print(json.dumps(_graph_to_dict(graph), indent=2))
        return 0

    if args.command == "ask":
        answer = answer_question(store, args.question)
        print(answer)
        persist_answer_artifacts(store, args.question, answer)
        return 0

    if args.command == "miro":
        from dataroot.render.miro import render_provenance_to_miro

        provenance_slug = _normalize_slug(args.provenance_slug)
        record = store.read(provenance_slug)
        try:
            trace = _extract_provenance_json(record.body)
            inquiry_slug = _inquiry_slug_for_provenance(provenance_slug)
            url = render_provenance_to_miro(
                trace,
                store=store,
                inquiry_slug=inquiry_slug,
                board_id=args.board_id,
                provenance_slug=provenance_slug,
            )
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            parser.exit(1, f"error: {exc}\n")
        print(url)
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _graph_to_dict(graph) -> dict:
    return {
        "root": graph.root,
        "nodes": {
            slug: {"title": node.title, "type": node.doc_type}
            for slug, node in sorted(graph.nodes.items())
        },
        "edges": [
            {"source": edge.source, "target": edge.target, "label": edge.label}
            for edge in graph.edges
        ],
    }


def _normalize_slug(slug: str) -> str:
    return slug.replace("\\", "/").strip("/")


def _extract_provenance_json(body: str) -> dict:
    match = re.search(r"```json\s*(.*?)\s*```", body, re.DOTALL | re.IGNORECASE)
    if not match:
        raise ValueError("no provenance JSON found in doc body")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("provenance JSON must be an object")
    return payload


def _inquiry_slug_for_provenance(provenance_slug: str) -> str | None:
    if provenance_slug.startswith("provenance_traces/"):
        return provenance_slug.replace("provenance_traces/", "inquiries/", 1)
    return None


def _print_miro_refresh_result(result) -> None:
    plan = result.plan
    print(f"Preserved frame: {plan.preserved_frame_title} ({plan.preserved_frame_id})")
    print(f"Items selected for deletion: {len(plan.items_to_delete)}")
    frame_titles = plan.frame_titles_to_delete
    if frame_titles:
        print("Frames selected for deletion:")
        for title in frame_titles:
            print(f"- {title}")
    else:
        print("Frames selected for deletion: none")

    if result.dry_run:
        print("Dry run only; no board changes made.")
        return

    print(f"Deleted items: {result.deleted_count}")
    for rendered in result.rendered:
        print(f"Rendered {rendered.label}: {rendered.question}")
        print(f"  Inquiry: {rendered.inquiry_slug}")
        print(f"  Provenance: {rendered.provenance_slug}")
    print(f"Board URL: https://miro.com/app/board/{plan.board_id}/")


def _make_store_or_exit(parser: argparse.ArgumentParser, config: DataRootConfig):
    try:
        return make_store(config)
    except RuntimeError as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
