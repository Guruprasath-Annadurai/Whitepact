# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Hosted metering follows the authorization decision and does not run without it."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.mcp_usage_repository import McpUsageRepository
from responsibleai.mcp import server as mcp_server
from responsibleai.mcp.governance_integration import GovernanceOutcome
from responsibleai.rbac.models import OrgContext, Plan, Role


@pytest.fixture()
async def usage_repo():
    engine = create_engine(":memory:")
    await engine.init()
    try:
        yield McpUsageRepository(engine)
    finally:
        await engine.close()


def _org() -> OrgContext:
    return OrgContext(key_id="k1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)


async def test_governance_denial_does_not_consume_allowed_quota(
    usage_repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mcp_server, "monthly_quota", lambda _plan: 1)
    outcomes = [
        GovernanceOutcome(
            proceed=False,
            arguments={},
            blocked_response={"error": "governance_blocked"},
        ),
        GovernanceOutcome(proceed=True, arguments={}, result={"ok": True}),
    ]
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.apply_governance",
        AsyncMock(side_effect=outcomes),
    )
    gov = mcp_server._current_governance.set(object())
    org_token = mcp_server._current_org.set(_org())
    usage_token = mcp_server._current_usage_repo.set(usage_repo)
    try:
        denied = await mcp_server._call_tool("rai_health", {"_whitepact_purpose": "close books"})
        allowed = await mcp_server._call_tool("rai_health", {"_whitepact_purpose": "close books"})
    finally:
        mcp_server._current_usage_repo.reset(usage_token)
        mcp_server._current_org.reset(org_token)
        mcp_server._current_governance.reset(gov)
    assert denied[1]["error"] == "governance_blocked"
    assert "error" not in allowed[1]
    usage = await usage_repo.usage_this_month("org-1")
    assert usage["allowed_calls"] == 1
    assert usage["blocked_calls"] == 1


async def test_missing_purpose_is_metered_as_blocked(usage_repo) -> None:
    gov = mcp_server._current_governance.set(object())
    org_token = mcp_server._current_org.set(_org())
    usage_token = mcp_server._current_usage_repo.set(usage_repo)
    try:
        result = await mcp_server._call_tool("rai_health", {})
    finally:
        mcp_server._current_usage_repo.reset(usage_token)
        mcp_server._current_org.reset(org_token)
        mcp_server._current_governance.reset(gov)
    assert result[1]["error"] == "governance_purpose_required"
    usage = await usage_repo.usage_this_month("org-1")
    assert usage["allowed_calls"] == 0
    assert usage["blocked_calls"] == 1


async def test_hosted_without_usage_repo_does_not_execute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    apply = AsyncMock(
        return_value=GovernanceOutcome(proceed=True, arguments={}, result={"ok": True})
    )
    monkeypatch.setattr("responsibleai.mcp.governance_integration.apply_governance", apply)
    hosted = mcp_server._current_hosted.set(True)
    gov = mcp_server._current_governance.set(object())
    org_token = mcp_server._current_org.set(_org())
    usage_token = mcp_server._current_usage_repo.set(None)
    try:
        result = await mcp_server._call_tool("rai_health", {"_whitepact_purpose": "close books"})
    finally:
        mcp_server._current_usage_repo.reset(usage_token)
        mcp_server._current_org.reset(org_token)
        mcp_server._current_governance.reset(gov)
        mcp_server._current_hosted.reset(hosted)
    assert result[1]["error"] == "quota_enforcement_unavailable"
    apply.assert_not_awaited()
