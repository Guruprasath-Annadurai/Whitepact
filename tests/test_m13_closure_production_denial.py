# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unsafe production configuration must be rejected before permit consumption."""

from unittest.mock import AsyncMock

import pytest

from responsibleai.governance.execution import InternalToolExecutor, authorize_execution
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.isolation.errors import IsolationError


@pytest.mark.asyncio
async def test_missing_production_broker_never_consumes_or_dispatches(monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    action = ActionRequest(
        AgentContext(
            IdentityContext("principal", "api_key", org_id="tenant"), organization_id="tenant"
        ),
        "rai_health",
        "rai_health",
        arguments={},
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    admission = AsyncMock(side_effect=AssertionError("Unsafe configuration reached admission"))
    dispatch = AsyncMock(side_effect=AssertionError("Unsafe configuration reached dispatch"))
    monkeypatch.setattr("responsibleai.governance.execution.admit_execution", admission)
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
    # Construct the invalid configuration directly; no broker initialization or
    # operating-system execution occurs in this denial-only regression.
    executor = object.__new__(InternalToolExecutor)
    executor._broker = None
    executor._nonce_repo = None

    with pytest.raises(IsolationError, match="forbidden in production"):
        await executor.execute(permit, action)

    admission.assert_not_awaited()
    dispatch.assert_not_awaited()
    assert not permit.consumed
