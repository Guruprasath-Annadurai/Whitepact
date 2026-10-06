# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical MCP catalog metadata — single source for tool/resource counts."""

from __future__ import annotations

from responsibleai import __version__
from responsibleai.mcp.resources import RESOURCE_DEFS
from responsibleai.mcp.tools import TOOL_DEFS

MCP_PROTOCOL_VERSION = "2025-03-26"
SERVICE_NAME = "whitepact-mcp"

# Update when a new wheel is published to PyPI (do not conflate with source tree).
PACKAGE_PUBLISHED_VERSION = "1.2.6"
SOURCE_DEVELOPMENT_VERSION = __version__
MCP_SERVER_RELEASE_VERSION = PACKAGE_PUBLISHED_VERSION

PRODUCTION_MCP_TOOL_COUNT = len(TOOL_DEFS)
REGISTERED_MCP_RESOURCE_COUNT = len(RESOURCE_DEFS)
