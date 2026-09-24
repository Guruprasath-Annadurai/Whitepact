# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from pathlib import Path

from responsibleai.mcp.metadata import (
    MCP_SERVER_RELEASE_VERSION,
    PACKAGE_PUBLISHED_VERSION,
    PRODUCTION_MCP_TOOL_COUNT,
    REGISTERED_MCP_RESOURCE_COUNT,
    SOURCE_DEVELOPMENT_VERSION,
)
from responsibleai.mcp.resources import RESOURCE_DEFS
from responsibleai.mcp.tools import TOOL_DEFS


def test_production_tool_count_matches_registry() -> None:
    assert PRODUCTION_MCP_TOOL_COUNT == len(TOOL_DEFS)
    assert PRODUCTION_MCP_TOOL_COUNT == 30


def test_resource_count_matches_defs() -> None:
    assert REGISTERED_MCP_RESOURCE_COUNT == len(RESOURCE_DEFS)


def test_platform_metadata_yaml_does_not_hardcode_stale_tool_count() -> None:
    text = Path("distribution/platform-metadata.yaml").read_text(encoding="utf-8")
    assert "count: 27" not in text
    assert "All 27 tools" not in text


def test_readme_public_tool_count_matches_production_registry() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    match = re.search(
        r"MCP server.*?\b(\d+)\b.*production tools.*?(\d+)\b.*resources",
        readme,
        re.IGNORECASE | re.DOTALL,
    )
    assert match is not None
    assert int(match.group(1)) == PRODUCTION_MCP_TOOL_COUNT
    assert int(match.group(2)) == REGISTERED_MCP_RESOURCE_COUNT


def test_version_semantics_are_explicit() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{SOURCE_DEVELOPMENT_VERSION}"' in pyproject
    assert PACKAGE_PUBLISHED_VERSION == MCP_SERVER_RELEASE_VERSION
