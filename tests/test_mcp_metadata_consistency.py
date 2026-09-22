# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

from responsibleai.mcp.metadata import (
    MCP_SERVER_RELEASE_VERSION,
    PACKAGE_PUBLISHED_VERSION,
    PRODUCTION_MCP_TOOL_COUNT,
    REGISTERED_MCP_RESOURCE_COUNT,
    SOURCE_DEVELOPMENT_VERSION,
)
from responsibleai.mcp.resources import RESOURCE_DEFS
from responsibleai.mcp.tools import PRODUCTION_TOOL_DEFS, TEST_TOOL_NAME


def test_production_tool_count_matches_registry() -> None:
    assert PRODUCTION_MCP_TOOL_COUNT == len(PRODUCTION_TOOL_DEFS)
    assert TEST_TOOL_NAME not in {t.name for t in PRODUCTION_TOOL_DEFS}
    assert PRODUCTION_MCP_TOOL_COUNT == 30


def test_resource_count_matches_defs() -> None:
    assert REGISTERED_MCP_RESOURCE_COUNT == len(RESOURCE_DEFS)


def test_version_semantics_are_explicit() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{SOURCE_DEVELOPMENT_VERSION}"' in pyproject
    assert PACKAGE_PUBLISHED_VERSION == MCP_SERVER_RELEASE_VERSION
