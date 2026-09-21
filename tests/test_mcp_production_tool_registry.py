# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.mcp.tools import (
    PRODUCTION_TOOL_DEFS,
    TEST_TOOL_NAME,
    TOOL_DEFS,
    advertised_tool_defs,
    dispatch_tool,
    set_mcp_dispatch_hosted,
)


def test_production_registry_excludes_test_tool() -> None:
    assert TEST_TOOL_NAME not in {t.name for t in PRODUCTION_TOOL_DEFS}
    assert len(PRODUCTION_TOOL_DEFS) == 30
    assert len(TOOL_DEFS) == 31


def test_hosted_listing_never_includes_test_tool() -> None:
    names = {t.name for t in advertised_tool_defs(hosted=True)}
    assert TEST_TOOL_NAME not in names
    assert len(names) == 30


def test_test_registry_requires_env_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAI_MCP_ALLOW_TEST_TOOLS", raising=False)
    names = {t.name for t in advertised_tool_defs(hosted=False)}
    assert TEST_TOOL_NAME not in names

    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "1")
    names_with_test = {t.name for t in advertised_tool_defs(hosted=False)}
    assert TEST_TOOL_NAME in names_with_test


@pytest.mark.asyncio
async def test_hosted_dispatch_blocks_test_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "1")
    set_mcp_dispatch_hosted(True)
    result = await dispatch_tool(TEST_TOOL_NAME, {})
    assert result.get("error") == "tool_unavailable"


@pytest.mark.asyncio
async def test_test_env_allows_dispatch_when_not_hosted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "1")
    set_mcp_dispatch_hosted(False)
    result = await dispatch_tool(TEST_TOOL_NAME, {})
    assert "error" not in result or result.get("error") != "tool_unavailable"


def test_client_arguments_cannot_enable_test_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client-supplied flags must not bypass server env gate."""
    monkeypatch.delenv("RAI_MCP_ALLOW_TEST_TOOLS", raising=False)
    # Simulate malicious extra keys that must never be consulted by advertised_tool_defs.
    names = {t.name for t in advertised_tool_defs(hosted=False)}
    assert TEST_TOOL_NAME not in names
    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "false")
    names = {t.name for t in advertised_tool_defs(hosted=False)}
    assert TEST_TOOL_NAME not in names


@pytest.mark.asyncio
async def test_default_env_disables_test_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RAI_MCP_ALLOW_TEST_TOOLS", raising=False)
    set_mcp_dispatch_hosted(False)
    result = await dispatch_tool(TEST_TOOL_NAME, {"enable_test_tools": True, "RAI_MCP_ALLOW_TEST_TOOLS": "1"})
    assert result.get("error") == "tool_unavailable"
