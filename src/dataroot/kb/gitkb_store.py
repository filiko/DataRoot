"""GitKB-backed KBStore implementation.

This adapter intentionally shells out to GitKB rather than re-implementing
GitKB's persistence, search, commit, or graph behavior.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .base import DocumentRecord, GraphEdge, GraphNode, GraphResult, SearchResult
from .markdown import markdown_to_record, record_to_markdown

SHOW_BATCH_SIZE = 100


@dataclass
class GitKBStore:
    root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    @staticmethod
    def is_available() -> bool:
        if not shutil.which("git") or not shutil.which("git-kb"):
            return False
        result = subprocess.run(
            ["git", "kb", "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return result.returncode == 0

    def init(self) -> None:
        self._run(["git", "kb", "init"], check=False)

    def write(self, record: DocumentRecord, commit_message: str | None = None) -> None:
        content = record_to_markdown(record)
        document_id = ""
        if record.doc_type == "relationship":
            result = self._run(
                [
                    "git",
                    "kb",
                    "create",
                    record.doc_type,
                    "--title",
                    record.title,
                    "--slug",
                    record.slug,
                    "--body",
                    "DataRoot relationship pending workspace materialization.",
                    "--json",
                ]
            )
            payload = json.loads(result.stdout)
            document_id = str(payload.get("id", ""))
        workspace_path = self._workspace_path_for_slug(record.slug)
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        workspace_path.write_text(
            self._workspace_markdown(record, content, document_id=document_id),
            encoding="utf-8",
        )
        if commit_message:
            self.commit(commit_message)

    def update(self, slug: str, content: str, commit_message: str | None = None) -> None:
        record = markdown_to_record(content, slug)
        metadata = self._workspace_metadata_for_slug(slug)
        if "id" not in metadata:
            document = self._show_document(slug)
            metadata = {
                "id": str(document.get("id", "")),
                "status": str(document.get("status", "draft")),
                "priority": str(document.get("priority", "medium")),
            }
        workspace_path = self._workspace_path_for_slug(slug)
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        workspace_path.write_text(
            self._workspace_markdown(
                record,
                content,
                document_id=metadata.get("id", ""),
                status=metadata.get("status", "draft"),
                priority=metadata.get("priority", "medium"),
            ),
            encoding="utf-8",
        )
        if commit_message:
            self.commit(commit_message)

    def read(self, slug: str) -> DocumentRecord:
        document = self._show_document(slug)
        return self._record_from_document(document, slug)

    def _show_document(self, slug: str) -> dict:
        documents = self._show_documents([slug])
        if not documents:
            raise FileNotFoundError(f"KB document not found: {slug}")
        return documents[0]

    def _show_documents(self, slugs: list[str]) -> list[dict]:
        if not slugs:
            return []
        result = self._run(["git", "kb", "show", *slugs, "--json"])
        payload = json.loads(result.stdout)
        documents = payload.get("documents", [])
        return documents

    def _record_from_document(self, document: dict, fallback_slug: str) -> DocumentRecord:
        content = str(document.get("content", ""))
        record = markdown_to_record(content, str(document.get("slug", fallback_slug)))
        if not record.frontmatter:
            record.doc_type = str(document.get("type", record.doc_type))
            record.slug = str(document.get("slug", record.slug))
            record.title = str(document.get("title", record.title))
        return record

    def list(self, doc_type: str | None = None, path_prefix: str | None = None) -> list[DocumentRecord]:
        command = ["git", "kb", "list", "--json"]
        if doc_type:
            command += ["--type", doc_type]
        if path_prefix:
            command += ["--path", path_prefix]
        result = self._run(command)
        payload = json.loads(result.stdout)
        records = []
        slugs = [str(item.get("slug", "")) for item in payload if item.get("slug")]
        for index in range(0, len(slugs), SHOW_BATCH_SIZE):
            for document in self._show_documents(slugs[index : index + SHOW_BATCH_SIZE]):
                records.append(self._record_from_document(document, str(document.get("slug", ""))))
        return records

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        result = self._run(["git", "kb", "search", query, "--limit", str(limit), "--json"])
        payload = json.loads(result.stdout)
        rows = []
        for item in payload:
            rows.append(
                SearchResult(
                    slug=str(item.get("slug", "")),
                    title=str(item.get("title", item.get("slug", ""))),
                    doc_type=str(item.get("type", "unknown")),
                    score=float(item.get("score", 1.0)),
                    snippet=str(item.get("snippet", "")),
                )
            )
        return rows

    def graph(self, slug: str, direction: str = "both", depth: int = 2) -> GraphResult:
        direction_map = {"inbound": "in", "outbound": "out", "both": "both"}
        result = self._run(
            [
                "git",
                "kb",
                "graph",
                slug,
                "--direction",
                direction_map.get(direction, direction),
                "--depth",
                str(depth),
                "--json",
            ]
        )
        payload = json.loads(result.stdout)
        graph = GraphResult(root=str(payload.get("root", slug)))
        nodes = payload.get("nodes", [])
        id_to_slug = {}
        for node in nodes:
            node_slug = str(node.get("slug", node.get("id", "")))
            if not node_slug:
                continue
            node_id = str(node.get("id", node_slug))
            id_to_slug[node_id] = node_slug
            doc_type = str(node.get("type", ""))
            if not doc_type:
                try:
                    doc_type = self.read(node_slug).doc_type
                except Exception:
                    doc_type = "unknown"
            graph.nodes[node_slug] = GraphNode(
                slug=node_slug,
                title=str(node.get("title", node_slug)),
                doc_type=doc_type,
            )
        for edge in payload.get("edges", []):
            source = id_to_slug.get(str(edge.get("from")), str(edge.get("from", "")))
            target = id_to_slug.get(str(edge.get("to")), str(edge.get("to", "")))
            if source and target:
                graph.edges.append(GraphEdge(source=source, target=target, label=str(edge.get("rel_type", "reference"))))
        return graph

    def commit(self, message: str) -> None:
        self._run(["git", "kb", "commit", "-a", "-m", message])

    def _run(self, command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                "GitKB command failed: "
                + " ".join(command)
                + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def _workspace_path_for_slug(self, slug: str) -> Path:
        cleaned = slug.replace("\\", "/").strip("/")
        path = (self.root / ".kb" / "workspaces" / "main" / f"{cleaned}.md").resolve()
        workspace_root = (self.root / ".kb" / "workspaces" / "main").resolve()
        if workspace_root not in path.parents and path != workspace_root:
            raise ValueError(f"Slug escapes GitKB workspace: {slug}")
        return path

    def _workspace_metadata_for_slug(self, slug: str) -> dict[str, str]:
        path = self._workspace_path_for_slug(slug)
        if not path.exists():
            return {}
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            return {}
        metadata = {}
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"').strip("'")
        return metadata

    def _workspace_markdown(
        self,
        record: DocumentRecord,
        content: str,
        document_id: str = "",
        status: str = "draft",
        priority: str = "medium",
    ) -> str:
        title = json.dumps(record.title, ensure_ascii=True)
        lines = ["---"]
        if document_id:
            lines.append(f"id: {document_id}")
        lines.extend(
            [
                f"slug: {record.slug}",
                f"title: {title}",
                f"type: {record.doc_type}",
                f"status: {status}",
                f"priority: {priority}",
                "---",
                "",
                content.rstrip(),
                "",
            ]
        )
        return "\n".join(lines)
