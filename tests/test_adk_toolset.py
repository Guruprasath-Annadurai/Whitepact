# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the Google ADK McpToolset factories — the "free integration"
from GAME_CHANGER_BUILD_PLAN.md Phase B. Verifies the factories build a
real, correctly-configured McpToolset against the actual installed
google-adk package (the `adk` extra / dev dependency) rather than a
hand-rolled stand-in for its constructor."""

from __future__ import annotations

import pytest

adk = pytest.importorskip("google.adk")

from google.adk.tools.mcp_tool.mcp_session_manager import (  # noqa: E402
    StdioConnectionParams,
    StreamableHTTPConnectionParams,
)
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset  # noqa: E402

from responsibleai.integrations.adk_toolset import (  # noqa: E402
    DEFAULT_STDIO_COMMAND,
    RAI_TOOL_PREFIX,
    build_http_toolset,
    build_stdio_toolset,
)


class TestBuildStdioToolset:
    def test_returns_an_mcp_toolset(self) -> None:
        toolset = build_stdio_toolset()
        assert isinstance(toolset, McpToolset)

    def test_uses_the_published_console_script_by_default(self) -> None:
        toolset = build_stdio_toolset()
        params = toolset.connection_params
        assert isinstance(params, StdioConnectionParams)
        assert params.server_params.command == DEFAULT_STDIO_COMMAND

    def test_custom_command_and_args_are_honored(self) -> None:
        toolset = build_stdio_toolset(command="python3", args=["-m", "responsibleai.mcp.server"])
        params = toolset.connection_params
        assert params.server_params.command == "python3"
        assert params.server_params.args == ["-m", "responsibleai.mcp.server"]

    def test_tool_filter_is_forwarded(self) -> None:
        toolset = build_stdio_toolset(tool_filter=["rai_check_trust"])
        assert toolset.tool_filter == ["rai_check_trust"]

    def test_tool_name_prefix_is_set(self) -> None:
        toolset = build_stdio_toolset()
        assert toolset.tool_name_prefix == RAI_TOOL_PREFIX


class TestBuildHttpToolset:
    def test_returns_an_mcp_toolset(self) -> None:
        toolset = build_http_toolset("https://example.com/mcp")
        assert isinstance(toolset, McpToolset)

    def test_url_and_headers_are_honored(self) -> None:
        toolset = build_http_toolset(
            "https://example.com/mcp", headers={"Authorization": "Bearer x"}
        )
        params = toolset.connection_params
        assert isinstance(params, StreamableHTTPConnectionParams)
        assert params.url == "https://example.com/mcp"
        assert params.headers == {"Authorization": "Bearer x"}
