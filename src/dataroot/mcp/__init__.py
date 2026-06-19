"""DataRoot stdio MCP server.

Exposes the Live Ask pipeline (`profile` -> `link` -> `answer_question`) as
eight bounded MCP tools. Default workspace is the Austin Permits Texas Open
Data slice; ``company_a`` and ``company_b`` work the same way.

Public entry points:

- :func:`build_server` -- returns a configured :class:`mcp.server.Server`
  with the eight tools registered. Use this when embedding DataRoot's MCP
  surface inside another transport (tests, in-process verifiers, custom
  hosts).
- :func:`run_stdio` -- blocking stdio entry point. ``python -m dataroot.mcp``
  and ``dataroot mcp`` both call into this. Refuses to start when
  ``git-kb`` is not on ``PATH``.

See ``docs/mcp-server.md`` for the full per-tool API reference and
``scripts/verify_mcp.py`` for an in-process sanity check.
"""

from .server import build_server, run_stdio

__all__ = ["build_server", "run_stdio"]
