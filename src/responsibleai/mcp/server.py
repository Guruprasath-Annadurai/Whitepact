"""
ResponsibleAI MCP Server — governance tools for Claude Code and MCP-compatible AI assistants.

Configure Claude Code by adding to .claude/settings.json:
    {
      "mcpServers": {
        "responsibleai": {
          "command": "responsibleai-mcp"
        }
      }
    }

Environment variables (all optional):
    RAI_MCP_LOG_LEVEL   Logging level: DEBUG | INFO | WARNING (default: WARNING)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from responsibleai.mcp.resources import RESOURCE_DEFS, dispatch_resource
from responsibleai.mcp.tools import TOOL_DEFS, dispatch_tool

_log_level = os.environ.get("RAI_MCP_LOG_LEVEL", "WARNING").upper()
logging.basicConfig(level=getattr(logging, _log_level, logging.WARNING))
_logger = logging.getLogger("responsibleai.mcp")

server: Server = Server("responsibleai-mcp")


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return TOOL_DEFS


@server.call_tool()
async def _call_tool(
    name: str,
    arguments: dict[str, Any] | None,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    _logger.debug("tool_call name=%s args=%s", name, arguments)
    result = await dispatch_tool(name, arguments or {})
    return [types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))]


@server.list_resources()
async def _list_resources() -> list[types.Resource]:
    return RESOURCE_DEFS


@server.read_resource()
async def _read_resource(uri: types.AnyUrl) -> str:
    _logger.debug("resource_read uri=%s", uri)
    return await dispatch_resource(str(uri))


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


def main() -> None:
    """CLI entry point: responsibleai-mcp."""
    _logger.info("starting responsibleai-mcp v1.2.0")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
