# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""MCP protocol facts from the installed SDK, not from documentation."""

from __future__ import annotations

import importlib.metadata

import mcp.types as mcp_types
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS


def test_installed_mcp_sdk_is_1x() -> None:
    version = importlib.metadata.version("mcp")
    assert version.startswith("1."), version


def test_installed_sdk_protocol_versions() -> None:
    assert mcp_types.DEFAULT_NEGOTIATED_VERSION == "2025-03-26"
    assert mcp_types.LATEST_PROTOCOL_VERSION == "2025-11-25"
    assert SUPPORTED_PROTOCOL_VERSIONS == [
        "2024-11-05",
        "2025-03-26",
        "2025-06-18",
        "2025-11-25",
    ]


def test_hosted_mcp_uses_stateless_streamable_http() -> None:
    import inspect

    from responsibleai.mcp import server as mcp_server

    source = inspect.getsource(mcp_server._build_http_app)
    assert "StreamableHTTPSessionManager" in source
    assert "stateless=True" in source
    assert 'Route("/mcp"' in source
    assert 'Route("/sse"' in source
    assert StreamableHTTPSessionManager is not None
