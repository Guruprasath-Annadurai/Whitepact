"""Client-side MCP bridge for Gemini APIs without native remote MCP.

Google's Antigravity agent can connect to Whitepact's ``/mcp`` endpoint
directly. Gemini model APIs that only accept function declarations can use
this adapter: it converts MCP tool schemas to Gemini declarations and routes
the selected function call through an already-authenticated MCP session.

The caller owns transport setup, OAuth token acquisition, approval UI, and
session lifetime. Keeping those responsibilities outside the bridge avoids
copying credentials or weakening Whitepact's OAuth and Heart enforcement.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


class GeminiMCPBridge:
    """Translate an MCP client session into Gemini function tools."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def list_function_declarations(self) -> list[dict[str, Any]]:
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": deepcopy(tool.inputSchema),
            }
            for tool in result.tools
        ]

    async def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await self._session.call_tool(name, arguments)
        text_parts = [
            item.text
            for item in result.content
            if getattr(item, "type", None) == "text" and getattr(item, "text", None)
        ]
        if result.isError:
            detail = "\n".join(text_parts) or f"MCP tool {name!r} failed"
            raise RuntimeError(detail)
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured
        return {"content": text_parts}
