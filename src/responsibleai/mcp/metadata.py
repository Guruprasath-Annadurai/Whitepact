# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical MCP catalog metadata — single source for tool/resource counts."""

from __future__ import annotations

from responsibleai import __version__
from responsibleai.mcp.resources import RESOURCE_DEFS
from responsibleai.mcp.tools import TOOL_DEFS

MCP_PROTOCOL_VERSION = "2025-03-26"
SERVICE_NAME = "whitepact-mcp"


def _is_test_only_tool(name: str) -> bool:
    return name.startswith("test.") or name.startswith("test_")


REGISTERED_MCP_TOOL_COUNT = len(TOOL_DEFS)
PUBLIC_MCP_TOOL_COUNT = sum(1 for t in TOOL_DEFS if not _is_test_only_tool(t.name))
REGISTERED_MCP_RESOURCE_COUNT = len(RESOURCE_DEFS)
PRODUCT_VERSION = __version__
