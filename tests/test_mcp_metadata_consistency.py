# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
from pathlib import Path

from responsibleai import __version__
from responsibleai.mcp.metadata import (
    MCP_PROTOCOL_VERSION,
    PUBLIC_MCP_TOOL_COUNT,
    REGISTERED_MCP_RESOURCE_COUNT,
    REGISTERED_MCP_TOOL_COUNT,
    SERVICE_NAME,
)
from responsibleai.mcp.resources import RESOURCE_DEFS
from responsibleai.mcp.tools import TOOL_DEFS


def test_registered_tool_count_matches_tool_defs() -> None:
    assert REGISTERED_MCP_TOOL_COUNT == len(TOOL_DEFS)


def test_public_tool_count_excludes_test_only_tools() -> None:
    assert PUBLIC_MCP_TOOL_COUNT <= REGISTERED_MCP_TOOL_COUNT
    assert PUBLIC_MCP_TOOL_COUNT >= 1


def test_resource_count_matches_defs() -> None:
    assert REGISTERED_MCP_RESOURCE_COUNT == len(RESOURCE_DEFS)
    assert REGISTERED_MCP_RESOURCE_COUNT == 20


def test_platform_metadata_yaml_does_not_hardcode_stale_tool_count() -> None:
    text = Path("distribution/platform-metadata.yaml").read_text(encoding="utf-8")
    assert "count: 27" not in text
    assert "All 27 tools" not in text


def test_readme_public_tool_count_matches_canonical() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    match = re.search(r"MCP server \((\d+) tools, (\d+) resources\)", readme)
    assert match is not None, "README must state MCP tool/resource counts explicitly"
    assert int(match.group(1)) == PUBLIC_MCP_TOOL_COUNT
    assert int(match.group(2)) == REGISTERED_MCP_RESOURCE_COUNT


def test_product_version_matches_package() -> None:
    assert __version__
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in pyproject


def test_metadata_constants_are_documented() -> None:
    payload = {
        "service": SERVICE_NAME,
        "protocol_version": MCP_PROTOCOL_VERSION,
        "registered_tools": REGISTERED_MCP_TOOL_COUNT,
        "public_tools": PUBLIC_MCP_TOOL_COUNT,
        "resources": REGISTERED_MCP_RESOURCE_COUNT,
        "product_version": __version__,
    }
    json.dumps(payload)  # serializable for health/metadata endpoints
