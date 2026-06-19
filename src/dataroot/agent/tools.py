"""Tool dispatcher for DataRoot agent roles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from dataroot.kb.base import DocumentRecord
from dataroot.kb.markdown import append_links, record_to_markdown
from dataroot.query_tools import find_candidate_paths, query_table


class ToolExecutor:
    """Dispatch JSON-schema tool calls to KBStore-backed functions."""

    def __init__(self, store):
        self.store = store

    def __call__(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        if tool_name == "kb_search":
            return [result.__dict__ for result in self.store.search(tool_args["query"], tool_args.get("limit", 10))]
        if tool_name == "kb_semantic":
            return [result.__dict__ for result in self.store.search(tool_args["query"], tool_args.get("limit", 10))]
        if tool_name == "kb_show":
            record = self.store.read(_slug(tool_args["slug"]))
            return {"frontmatter": record.normalized_frontmatter(), "body": record.body}
        if tool_name == "kb_list":
            records = self.store.list(doc_type=tool_args.get("type"), path_prefix=tool_args.get("path"))
            return [{"slug": record.slug, "type": record.doc_type, "title": record.title} for record in records]
        if tool_name == "kb_graph":
            graph = self.store.graph(
                _slug(tool_args["slug"]),
                direction=tool_args.get("direction", "both"),
                depth=tool_args.get("depth", 2),
            )
            return _graph_to_dict(graph)
        if tool_name == "kb_update":
            return self._kb_update(tool_args)
        if tool_name == "query_table":
            rows = query_table(
                self.store,
                _slug(tool_args["table_slug"]),
                filters=tool_args.get("filters") or [],
                limit=tool_args.get("limit", 50),
            )
            return [row.__dict__ for row in rows]
        if tool_name == "find_candidate_paths":
            return find_candidate_paths(
                self.store,
                start_terms=tool_args["start_terms"],
                target_terms=tool_args["target_terms"],
                depth=tool_args.get("constraints", {}).get("depth", 3) if isinstance(tool_args.get("constraints"), dict) else 3,
            )
        if tool_name == "log_inquiry":
            return self._log_inquiry(tool_args)
        raise ValueError(f"Unknown tool: {tool_name}")

    def _kb_update(self, tool_args: dict[str, Any]) -> dict[str, str]:
        slug = _slug(tool_args["slug"])
        content = tool_args["content"]
        links = [_parse_wikilink(link) for link in tool_args.get("wikilinks", [])]
        if links:
            content = append_links(content, links)
        self.store.update(slug, content)
        self.store.commit(f"Update {slug}")
        return {"slug": slug, "status": "updated"}

    def _log_inquiry(self, tool_args: dict[str, Any]) -> dict[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        slug = f"inquiries/{timestamp}"
        trace = tool_args.get("provenance_trace", {})
        body = "\n".join(
            [
                f"# Inquiry {timestamp}",
                "",
                "## Question",
                "",
                tool_args["question"],
                "",
                "## Answer",
                "",
                tool_args["answer"],
                "",
                "## Provenance",
                "",
                "```json",
                json.dumps(trace, indent=2, default=str),
                "```",
            ]
        )
        record = DocumentRecord(
            doc_type="inquiry",
            slug=slug,
            title=tool_args["question"][:80],
            frontmatter={"created_at": timestamp},
            body=body,
        )
        self.store.write(record, commit_message=f"Log inquiry {timestamp}")
        return {"slug": slug, "status": "logged"}

def _slug(value: str) -> str:
    return value.replace("\\", "/").strip("/")


def _parse_wikilink(value: str) -> tuple[str, str]:
    cleaned = value.strip()
    if cleaned.startswith("[[") and cleaned.endswith("]]"):
        cleaned = cleaned[2:-2]
    if "|" in cleaned:
        slug, label = cleaned.split("|", 1)
        return _slug(slug), label.strip() or "agent-added"
    return _slug(cleaned), "agent-added"


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
