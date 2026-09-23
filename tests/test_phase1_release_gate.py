# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Negative execution checks for the independently reported release blockers."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from responsibleai.governance.execution import (
    DecisionNotExecutableError,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.mcp import server
from responsibleai.rbac.models import OrgContext, Plan, Role


@pytest.mark.parametrize("org_id", ["tenant-a", None])
async def test_hosted_missing_governance_never_dispatches(monkeypatch, org_id):
    dispatch = AsyncMock(return_value={"executed": True})
    monkeypatch.setattr(server, "dispatch_tool", dispatch)
    ctx = OrgContext(key_id="key", role=Role.OWNER, org_id=org_id, plan=Plan.ENTERPRISE)
    org_token = server._current_org.set(ctx)
    governance_token = server._current_governance.set(None)
    try:
        result = await server._call_tool("rai_health", {})
        assert result[1].get("error") == "governance_unavailable"
        dispatch.assert_not_awaited()
    finally:
        server._current_org.reset(org_token)
        server._current_governance.reset(governance_token)


@pytest.mark.parametrize(
    "decision",
    [GovernanceDecision.DENY, GovernanceDecision.QUARANTINE, GovernanceDecision.REQUIRE_APPROVAL],
)
async def test_executor_rejects_nonexecutable_permit_before_dispatch(monkeypatch, decision):
    action = ActionRequest(
        AgentContext(IdentityContext("key", "api_key", org_id="tenant-a")),
        "rai_health",
        "rai_health",
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    permit.decision = decision
    dispatch = AsyncMock(return_value={"executed": True})
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
    with pytest.raises(DecisionNotExecutableError):
        await InternalToolExecutor().execute(permit, action)
    dispatch.assert_not_awaited()


async def test_hosted_lost_identity_does_not_become_stdio(monkeypatch):
    dispatch = AsyncMock(return_value={"executed": True})
    monkeypatch.setattr(server, "dispatch_tool", dispatch)
    token = server._current_hosted.set(True)
    try:
        assert (await server._call_tool("rai_health", {}))[1]["error"] == "governance_unavailable"
        dispatch.assert_not_awaited()
    finally:
        server._current_hosted.reset(token)


async def test_unavailable_governance_does_not_charge_allowed_usage(monkeypatch):
    usage = AsyncMock()
    usage.count_since.return_value = 0
    ctx = OrgContext(key_id="key", role=Role.ANALYST, org_id="tenant-a", plan=Plan.PRO)
    dispatch = AsyncMock()
    monkeypatch.setattr(server, "dispatch_tool", dispatch)
    org_token = server._current_org.set(ctx)
    usage_token = server._current_usage_repo.set(usage)
    try:
        assert (await server._call_tool("rai_health", {}))[1]["error"] == "governance_unavailable"
        usage.record_call.assert_awaited_once_with("tenant-a", "rai_health", "PRO", allowed=False)
        dispatch.assert_not_awaited()
    finally:
        server._current_usage_repo.reset(usage_token)
        server._current_org.reset(org_token)


async def test_upstream_same_permit_concurrent_admission(monkeypatch):
    from responsibleai.governance.execution import AuthorizationAlreadyConsumedError
    from responsibleai.governance.upstream import UpstreamServer
    from responsibleai.governance.upstream_executor import UpstreamMCPExecutor

    arrived = 0
    both_reading = asyncio.Event()
    target = UpstreamServer("srv", "tenant-a", "test", "https://example.com/mcp")

    async def get_target(_):
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            both_reading.set()
        await both_reading.wait()
        return target

    registry = AsyncMock()
    registry.get.side_effect = get_target
    audit = AsyncMock()

    # Ensure both calls cross the initial validation before either can consume.
    async def record_issued(*args, **kwargs):
        await asyncio.sleep(0)

    audit.record_issued.side_effect = record_issued
    sink = AsyncMock(return_value={"executed": True})
    monkeypatch.setattr("responsibleai.governance.upstream_executor._call_upstream_tool", sink)
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor.validate_upstream_server_url", lambda url: None
    )
    action = ActionRequest(
        AgentContext(IdentityContext("key", "api_key", org_id="tenant-a")),
        "mcp.tool_call",
        "srv::read",
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    executor = UpstreamMCPExecutor(registry, credential_issuance_repo=audit)
    results = await asyncio.gather(
        executor.execute(permit, action), executor.execute(permit, action), return_exceptions=True
    )
    assert sink.await_count == 1
    assert sum(isinstance(item, AuthorizationAlreadyConsumedError) for item in results) == 1
