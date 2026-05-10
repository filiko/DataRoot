"""Stdio entry point for the DataRoot MCP server.

Run with::

    python -m dataroot.mcp

equivalent to ``dataroot mcp`` (the CLI subcommand) and to
``bash scripts/start-mcp.sh`` (the WSL launcher Codex / Claude Code use).

Exits 1 with a descriptive message when ``git-kb`` is missing from ``PATH``;
the server has no LocalMarkdownStore fallback. See ``docs/mcp-server.md``
for the full API reference.
"""

from .server import run_stdio

if __name__ == "__main__":
    raise SystemExit(run_stdio())
