# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL, bind_counter_engine
from responsibleai.mcp.tools import dispatch_tool, set_mcp_dispatch_hosted


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.mark.asyncio
async def test_governance_channel_allows_counter_without_mcp_test_flag(engine) -> None:
    await engine.init()
    bind_counter_engine(engine)
    set_mcp_dispatch_hosted(True)
    result = await dispatch_tool(
        SYNTHETIC_COUNTER_TOOL,
        {"_whitepact_organization_id": "org-gov", "fail_after_effect": False},
        channel="governance_admitted",
    )
    assert "error" not in result
    assert result.get("ok") is True


@pytest.mark.asyncio
async def test_mcp_hosted_still_blocks_counter_without_test_flag(engine) -> None:
    await engine.init()
    bind_counter_engine(engine)
    set_mcp_dispatch_hosted(True)
    result = await dispatch_tool(SYNTHETIC_COUNTER_TOOL, {})
    assert result.get("error") == "tool_unavailable"
