"""Tests for approval expiry (v3 authority-layer work, Task #135): a
REQUIRE_APPROVAL request has a real time limit
(`governance/approval.py`'s `DEFAULT_APPROVAL_TTL_HOURS`), enforced by
both `ApprovalRepository.resolve()` and `.consume()` — a human decision
made against, or an execution attempted against, an expired approval
window must fail, not silently proceed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db import ApprovalExpiredError, ApprovalRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import (
    DEFAULT_APPROVAL_TTL_HOURS,
    ApprovalStatus,
    build_approval_request,
)


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def approval_repo(engine):
    return ApprovalRepository(engine)


def _action() -> ActionRequest:
    identity = IdentityContext(identity_id="agent-key", kind="api_key", org_id="org-1")
    agent = AgentContext(identity=identity, framework="mcp-client")
    return ActionRequest(
        agent=agent, action_type="payment", target="payments.execute", arguments={"amount": 1}
    )


async def _seed_pending(approval_repo: ApprovalRepository, action: ActionRequest):
    gateway = WhitePactRuntimeGateway()
    authority = AuthorityContext(
        delegated_by="org-1",
        granted_action_types=frozenset({"payment"}),
        require_approval_for=frozenset({"payment"}),
    )
    decision = gateway.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
    return await approval_repo.create(build_approval_request(action, decision))


class TestBuildApprovalRequestStampsExpiry:
    def test_expires_at_is_set_ttl_hours_after_requested_at(self) -> None:
        action = _action()
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = build_approval_request(action, decision)
        assert approval.expires_at == approval.requested_at + timedelta(
            hours=DEFAULT_APPROVAL_TTL_HOURS
        )

    def test_is_expired_false_for_a_legacy_row_with_no_expiry(self) -> None:
        action = _action()
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = build_approval_request(action, decision)
        approval.expires_at = None
        assert approval.is_expired is False


class TestResolveRejectsExpired:
    async def test_resolving_an_expired_pending_approval_raises(
        self, approval_repo: ApprovalRepository
    ) -> None:
        action = _action()
        approval = await _seed_pending(approval_repo, action)
        # Simulate time passing past the TTL by directly rewriting the
        # persisted row's expires_at to the past (no time-mocking
        # dependency needed -- exercises the real read path).
        from sqlalchemy import update

        from responsibleai.db.engine import governance_approvals

        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        async with approval_repo._engine.raw.begin() as conn:  # noqa: SLF001 -- test-only direct row mutation
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval.approval_id)
                .values(expires_at=past)
            )

        with pytest.raises(ApprovalExpiredError):
            await approval_repo.resolve(
                approval.approval_id,
                resolved_by="human-approver-1",
                outcome=ApprovalStatus.APPROVED,
            )

    async def test_resolving_before_expiry_succeeds(
        self, approval_repo: ApprovalRepository
    ) -> None:
        action = _action()
        approval = await _seed_pending(approval_repo, action)
        resolved = await approval_repo.resolve(
            approval.approval_id,
            resolved_by="human-approver-1",
            outcome=ApprovalStatus.APPROVED,
        )
        assert resolved.status == ApprovalStatus.APPROVED


class TestConsumeRejectsExpired:
    async def test_consuming_an_expired_approved_approval_raises(
        self, approval_repo: ApprovalRepository
    ) -> None:
        action = _action()
        approval = await _seed_pending(approval_repo, action)
        await approval_repo.resolve(
            approval.approval_id,
            resolved_by="human-approver-1",
            outcome=ApprovalStatus.APPROVED,
        )

        from sqlalchemy import update

        from responsibleai.db.engine import governance_approvals

        past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        async with approval_repo._engine.raw.begin() as conn:  # noqa: SLF001 -- test-only direct row mutation
            await conn.execute(
                update(governance_approvals)
                .where(governance_approvals.c.id == approval.approval_id)
                .values(expires_at=past)
            )

        with pytest.raises(ApprovalExpiredError):
            await approval_repo.consume(approval.approval_id, action=action)
