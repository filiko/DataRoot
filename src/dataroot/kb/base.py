"""Persistence boundary for DataRoot knowledge documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


@dataclass
class DocumentRecord:
    """Normalized document record emitted by DataRoot before persistence."""

    doc_type: str
    slug: str
    title: str
    frontmatter: dict
    body: str = ""

    def normalized_frontmatter(self) -> dict:
        data = dict(self.frontmatter)
        data["type"] = self.doc_type
        data["slug"] = self.slug
        data["title"] = self.title
        return data


@dataclass
class SearchResult:
    slug: str
    title: str
    doc_type: str
    score: float
    snippet: str = ""


@dataclass
class GraphNode:
    slug: str
    title: str
    doc_type: str


@dataclass
class GraphEdge:
    source: str
    target: str
    label: str = "wikilink"


@dataclass
class GraphResult:
    root: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)


class KBStore(Protocol):
    """Adapter implemented by GitKBStore and LocalMarkdownStore."""

    root: Path

    def init(self) -> None:
        ...

    def write(self, record: DocumentRecord, commit_message: str | None = None) -> None:
        ...

    def update(self, slug: str, content: str, commit_message: str | None = None) -> None:
        ...

    def read(self, slug: str) -> DocumentRecord:
        ...

    def list(self, doc_type: str | None = None, path_prefix: str | None = None) -> list[DocumentRecord]:
        ...

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        ...

    def graph(self, slug: str, direction: str = "both", depth: int = 2) -> GraphResult:
        ...

    def commit(self, message: str) -> None:
        ...
