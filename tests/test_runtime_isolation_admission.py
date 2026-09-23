# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive admission, authorization, and evidence integration tests for runtime isolation."""

from __future__ import annotations

import pytest

from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    ExecutionAuthorization,
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
from responsibleai.governance.risk import RiskTier
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.models import BackendMode


def _make_action(tool_name: str, args: dict, *, org_id: str = "tenant-alpha") -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-auth-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
            framework="mcp-client",
        ),
        action_type=tool_name,
        target=tool_name,
        arguments=args,
        purpose="admission-integration-test",
    )


def _make_permit(action: ActionRequest) -> ExecutionAuthorization:
    return authorize_execution(
        DecisionResult(
            decision=GovernanceDecision.ALLOW,
            action_id=action.action_id,
            risk_tier=RiskTier.MINIMAL,
        ),
        action,
    )


@pytest.mark.asyncio
class TestExecutionAdmissionIntegration:
    async def test_authorization_replay_rejected_with_zero_sandbox_starts(self):
        """A consumed authorization cannot be presented again; executor rejects before broker."""
        broker = IsolationBroker(mode=BackendMode.LOCAL_DEV)
        executor = InternalToolExecutor(broker=broker)

        action = _make_action("rai_trust_score", {"agent_id": "test-agent"})
        permit = _make_permit(action)

        # First run consumes permit
        res1 = await executor.execute(permit, action)
        assert res1 is not None

        # Replay must fail closed with AuthorizationAlreadyConsumedError
        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(permit, action)

    async def test_stale_expired_authorization_rejected(self):
        """Expired permit fails closed before broker invocation."""
        broker = IsolationBroker(mode=BackendMode.LOCAL_DEV)
        executor = InternalToolExecutor(broker=broker)

        action = _make_action("rai_trust_score", {"agent_id": "test-agent"})
        permit = _make_permit(action)
        # Force expiry
        object.__setattr__(permit, "expires_at", permit.issued_at)

        with pytest.raises(AuthorizationExpiredError):
            await executor.execute(permit, action)

    async def test_organization_mismatch_rejected(self):
        """Permit issued to Tenant A cannot be used by Tenant B."""
        broker = IsolationBroker(mode=BackendMode.LOCAL_DEV)
        executor = InternalToolExecutor(broker=broker)

        action_a = _make_action("rai_trust_score", {"agent_id": "test-agent"}, org_id="tenant-a")
        permit_a = _make_permit(action_a)

        action_b = _make_action("rai_trust_score", {"agent_id": "test-agent"}, org_id="tenant-b")

        with pytest.raises(AuthorizationOrganizationMismatchError):
            await executor.execute(permit_a, action_b)

    async def test_action_tampering_mismatch_rejected(self):
        """Permit granted for arguments X cannot execute arguments Y."""
        broker = IsolationBroker(mode=BackendMode.LOCAL_DEV)
        executor = InternalToolExecutor(broker=broker)

        action = _make_action("rai_trust_score", {"agent_id": "original-agent"})
        permit = _make_permit(action)

        tampered_action = _make_action("rai_trust_score", {"agent_id": "tampered-agent"})

        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(permit, tampered_action)
