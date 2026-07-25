"""Google ADK MCPToolset wiring for the ResponsibleAI MCP server — the
"free integration" from GAME_CHANGER_BUILD_PLAN.md Phase B.

ADK's `McpToolset` auto-discovers tools from any MCP server via
`list_tools` and wraps them as native ADK `BaseTool`s, so pointing it at
`responsibleai-mcp` (already published as a console script — see
`pyproject.toml`'s `[project.scripts]`) requires no new integration code
on the MCP server itself, unlike the LangChain/LangGraph adapters, which
had to implement their own interception logic. This module is a thin
convenience factory over the two connection modes ADK supports for a
server like this one; it adds nothing `McpToolset` doesn't already do,
it just saves the caller from importing three separate ADK classes.

Requires `google-adk`. Not a core dependency — install via the `adk`
extra:

    pip install "rai-governance-platform[adk]"

Usage (local stdio, the simplest option — spawns `responsibleai-mcp`
as a subprocess):

    from google.adk.agents import LlmAgent
    from responsibleai.integrations.adk_toolset import build_stdio_toolset

    agent = LlmAgent(
        model="gemini-2.0-flash",
        tools=[build_stdio_toolset()],
    )

Usage (a hosted instance running `responsibleai-mcp-http`):

    from responsibleai.integrations.adk_toolset import build_http_toolset
    toolset = build_http_toolset("https://responsibleai-dashboard.onrender.com/mcp")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

try:
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
    from mcp import StdioServerParameters

    _ADK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra isn't installed
    _ADK_AVAILABLE = False

if TYPE_CHECKING:
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset as McpToolsetType

DEFAULT_STDIO_COMMAND = "responsibleai-mcp"
DEFAULT_STDIO_TIMEOUT_SECONDS = 30.0
DEFAULT_HTTP_TIMEOUT_SECONDS = 10.0
RAI_TOOL_PREFIX = "rai"


def _require_adk() -> None:
    if not _ADK_AVAILABLE:
        raise ImportError(
            "build_stdio_toolset/build_http_toolset require the 'adk' extra: "
            "pip install \"rai-governance-platform[adk]\" (needs google-adk)."
        )


def build_stdio_toolset(
    *,
    command: str = DEFAULT_STDIO_COMMAND,
    args: list[str] | None = None,
    tool_filter: list[str] | None = None,
    timeout: float = DEFAULT_STDIO_TIMEOUT_SECONDS,
) -> McpToolsetType:
    """Spawn `responsibleai-mcp` as a local subprocess and expose its tools
    (including `rai_check_trust`) as native ADK tools.

    `tool_filter`, if given, restricts which of the server's 27 tools are
    exposed — e.g. `tool_filter=["rai_check_trust"]` to expose only the
    trust-check primitive rather than the full evaluation toolset.
    """
    _require_adk()
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command=command, args=args or []),
            timeout=timeout,
        ),
        tool_filter=tool_filter,
        tool_name_prefix=RAI_TOOL_PREFIX,
    )


def build_http_toolset(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    tool_filter: list[str] | None = None,
    timeout: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
) -> McpToolsetType:
    """Connect to a hosted `responsibleai-mcp-http` instance over
    Streamable HTTP instead of spawning a local subprocess — the option
    for an ADK agent that isn't running on the same machine as the MCP
    server.
    """
    _require_adk()
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=url, headers=headers, timeout=timeout,
        ),
        tool_filter=tool_filter,
        tool_name_prefix=RAI_TOOL_PREFIX,
    )
