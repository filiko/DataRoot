"""Local Markdown fallback KBStore implementation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .base import DocumentRecord, GraphEdge, GraphNode, GraphResult, SearchResult
from .markdown import extract_wikilinks, markdown_to_record, record_to_markdown


@dataclass
class LocalMarkdownStore:
    root: Path

    def __post_init__(self) -> None:
        self.root = self.root.resolve()

    def init(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, record: DocumentRecord, commit_message: str | None = None) -> None:
        path = self._path_for_slug(record.slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record_to_markdown(record), encoding="utf-8")

    def update(self, slug: str, content: str, commit_message: str | None = None) -> None:
        path = self._path_for_slug(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def read(self, slug: str) -> DocumentRecord:
        path = self._path_for_slug(slug)
        if not path.exists():
            raise FileNotFoundError(f"KB document not found: {slug}")
        return markdown_to_record(path.read_text(encoding="utf-8"), slug)

    def list(self, doc_type: str | None = None, path_prefix: str | None = None) -> list[DocumentRecord]:
        self.init()
        records = []
        for path in sorted(self.root.rglob("*.md")):
            if not path.is_file():
                continue
            slug = self._slug_for_path(path)
            record = markdown_to_record(path.read_text(encoding="utf-8"), slug)
            if doc_type and record.doc_type != doc_type:
                continue
            if path_prefix and not record.slug.startswith(path_prefix):
                continue
            records.append(record)
        return records

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        terms = [term.lower() for term in query.split() if term.strip()]
        if not terms:
            return []

        results: list[SearchResult] = []
        for record in self.list():
            haystack = " ".join(
                [
                    record.slug,
                    record.title,
                    record.doc_type,
                    str(record.frontmatter),
                    record.body,
                ]
            ).lower()
            score = sum(haystack.count(term) for term in terms)
            if score <= 0:
                continue
            results.append(
                SearchResult(
                    slug=record.slug,
                    title=record.title,
                    doc_type=record.doc_type,
                    score=float(score),
                    snippet=_snippet(record.body, terms),
                )
            )

        results.sort(key=lambda item: (-item.score, item.slug))
        return results[:limit]

    def graph(self, slug: str, direction: str = "both", depth: int = 2) -> GraphResult:
        slug = slug.replace("\\", "/").strip("/")
        records = {record.slug: record for record in self.list()}
        inbound: dict[str, list[str]] = {}
        outbound: dict[str, list[str]] = {}

        for record in records.values():
            outbound[record.slug] = extract_wikilinks(record.body)
            for target in outbound[record.slug]:
                inbound.setdefault(target, []).append(record.slug)

        result = GraphResult(root=slug)
        queue: deque[tuple[str, int]] = deque([(slug, 0)])
        seen = {slug}

        while queue:
            current, distance = queue.popleft()
            record = records.get(current)
            if record:
                result.nodes[current] = GraphNode(slug=current, title=record.title, doc_type=record.doc_type)
            else:
                result.nodes[current] = GraphNode(slug=current, title=current, doc_type="unknown")

            if distance >= depth:
                continue

            next_slugs = []
            if direction in {"outbound", "both"}:
                for target in outbound.get(current, []):
                    result.edges.append(GraphEdge(source=current, target=target))
                    next_slugs.append(target)
            if direction in {"inbound", "both"}:
                for source in inbound.get(current, []):
                    result.edges.append(GraphEdge(source=source, target=current))
                    next_slugs.append(source)

            for next_slug in next_slugs:
                if next_slug not in seen:
                    seen.add(next_slug)
                    queue.append((next_slug, distance + 1))

        unique_edges = []
        edge_keys = set()
        for edge in result.edges:
            key = (edge.source, edge.target, edge.label)
            if key not in edge_keys:
                edge_keys.add(key)
                unique_edges.append(edge)
        result.edges = unique_edges
        return result

    def commit(self, message: str) -> None:
        return None

    def _path_for_slug(self, slug: str) -> Path:
        cleaned = slug.strip().strip("/").replace("\\", "/")
        path = (self.root / f"{cleaned}.md").resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError(f"Slug escapes KB root: {slug}")
        return path

    def _slug_for_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).with_suffix("").as_posix()


def _snippet(body: str, terms: list[str]) -> str:
    compact = " ".join(body.split())
    lower = compact.lower()
    first_index = min((lower.find(term) for term in terms if term in lower), default=0)
    start = max(0, first_index - 60)
    end = min(len(compact), first_index + 180)
    return compact[start:end]
