"""ResponsibleAI MCP Server — governance tools for Claude Code and MCP-compatible AI assistants.

No eager imports here on purpose: `mcp/tools.py`, `mcp/resources.py`, and
`mcp/server.py` depend on the optional `mcp` SDK package (`pip install
rai-governance-platform[mcp]`), but `mcp/licensing.py` is pure Python and is
imported by the core dashboard (`dashboard/app.py`) to gate hosted tool
access. Importing `server.main` here would force the `mcp` SDK onto every
dashboard-only install. Console scripts reference
`responsibleai.mcp.server:main` / `:main_http` directly (see pyproject.toml)
rather than through this package, so nothing needs it re-exported here.
"""
