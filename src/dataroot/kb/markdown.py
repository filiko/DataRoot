"""Markdown/frontmatter serialization helpers."""

from __future__ import annotations

import json
import re

from .base import DocumentRecord

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")


def record_to_markdown(record: DocumentRecord) -> str:
    frontmatter = record.normalized_frontmatter()
    yaml_lines = [f"{key}: {_format_value(value)}" for key, value in frontmatter.items()]
    body = record.body.rstrip()
    if body:
        body = "\n\n" + body + "\n"
    else:
        body = "\n"
    return "---\n" + "\n".join(yaml_lines) + "\n---\n" + body


def markdown_to_record(content: str, fallback_slug: str) -> DocumentRecord:
    frontmatter, body = split_frontmatter(content)
    doc_type = str(frontmatter.get("type", "note"))
    slug = str(frontmatter.get("slug", fallback_slug))
    title = str(frontmatter.get("title", slug.rsplit("/", 1)[-1]))
    return DocumentRecord(doc_type=doc_type, slug=slug, title=title, frontmatter=frontmatter, body=body.strip())


def split_frontmatter(content: str) -> tuple[dict, str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break

    if end_index is None:
        return {}, content

    data: dict = {}
    for line in lines[1:end_index]:
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = _parse_value(value.strip())

    return data, "\n".join(lines[end_index + 1 :])


def extract_wikilinks(text: str) -> list[str]:
    links = []
    for match in WIKILINK_RE.finditer(text):
        slug = match.group(1).strip()
        if slug and slug not in links:
            links.append(slug)
    return links


def append_links(content: str, links: list[tuple[str, str]]) -> str:
    if not links:
        return content

    existing = set(extract_wikilinks(content))
    new_lines = []
    for slug, label in links:
        if slug not in existing:
            new_lines.append(f"- [[{slug}|{label}]]")

    if not new_lines:
        return content

    return content.rstrip() + "\n\n## Inferred Links\n\n" + "\n".join(new_lines) + "\n"


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=True)
    return json.dumps(str(value), ensure_ascii=True)


def _parse_value(value: str) -> object:
    if value in {"true", "false"}:
        return value == "true"
    if value == "null":
        return None
    if not value:
        return ""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        pass
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
