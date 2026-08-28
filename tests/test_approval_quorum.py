# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for multi-approver quorum (v3 authority-layer work, Task
#142): "no multi-approver quorum or delegation-chain approval" was
flagged repeatedly in this session's gap reports. Closes the quorum
half.

Covers: required_approvals defaulting (HIGH risk -> 2, everything else
-> 1, preserving exact prior single-approver behavior), the veto
semantics of a single DENIED vote, the replay guard against double-
voting, and that consume()/resume still only work once quorum is
actually reached.
"""

from __future__ import annotations

import pytest

from responsibleai.db import (
    AlreadyVotedError,
    ApprovalAlreadyResolvedError,
    ApprovalNotApprovedError,
    ApprovalRepository,
    SelfApprovalError,
    create_engine,
)
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    RiskTier,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import (
    ApprovalStatus,
    build_approval_request,
    default_required_approvals,
)
from responsibleai.governance.models import DecisionResult


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def repo(engine):
    return ApprovalRepository(engine)


def _identity(org_id: str = "org-1", identity_id: str = "agent-key") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), framework="mcp-client")


def _action(target: str = "rai_hallucination") -> ActionRequest:
    return ActionRequest(
        agent=_agent(), action_type="mcp_tool_call", target=target, arguments={"text": "x"}
    )


class TestDefaultRequiredApprovals:
    def test_high_risk_requires_two(self) -> None:
        assert default_required_approvals(RiskTier.HIGH) == 2

    def test_every_other_tier_requires_one(self) -> None:
        assert default_required_approvals(RiskTier.MEDIUM) == 1
        assert default_required_approvals(RiskTier.LOW) == 1
        assert default_required_approvals(RiskTier.MINIMAL) == 1
        assert default_required_approvals(None) == 1

    def test_build_approval_request_uses_risk_tiered_default(self) -> None:
        action = _action()
        decision = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action.action_id,
            risk_tier=RiskTier.HIGH,
        )
        approval = build_approval_request(action, decision)
        assert approval.required_approvals == 2

        decision_medium = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action.action_id,
            risk_tier=RiskTier.MEDIUM,
        )
        assert build_approval_request(action, decision_medium).required_approvals == 1


async def _seed_quorum_approval(repo: ApprovalRepository, *, required_approvals: int = 2) -> str:
    gateway = WhitePactRuntimeGateway()
    authority = AuthorityContext(
        delegated_by="org-1",
        granted_action_types=frozenset({"mcp_tool_call"}),
        require_approval_for=frozenset({"mcp_tool_call"}),
    )
    action = _action()
    decision = gateway.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
    approval = build_approval_request(action, decision)
    approval.required_approvals = required_approvals
    saved = await repo.create(approval)
    return saved.approval_id


class TestSingleApproverBackwardCompatibility:
    """required_approvals=1 (the default before quorum existed) must
    behave EXACTLY as resolve() always did: one call closes it."""

    async def test_one_approve_call_closes_immediately(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=1)
        resolved = await repo.resolve(
            approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED
        )
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_by == "human-1"

    async def test_second_resolve_call_still_raises_already_resolved(
        self, repo: ApprovalRepository
    ) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=1)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)
        with pytest.raises(ApprovalAlreadyResolvedError):
            await repo.resolve(approval_id, resolved_by="human-2", outcome=ApprovalStatus.APPROVED)


class TestQuorumApproval:
    async def test_single_vote_leaves_pending(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=2)
        result = await repo.resolve(
            approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED
        )
        assert result.status == ApprovalStatus.PENDING

        fetched = await repo.get(approval_id)
        assert fetched.status == ApprovalStatus.PENDING

    async def test_second_approval_reaches_quorum_and_closes(
        self, repo: ApprovalRepository
    ) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=2)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)
        final = await repo.resolve(
            approval_id, resolved_by="human-2", outcome=ApprovalStatus.APPROVED
        )
        assert final.status == ApprovalStatus.APPROVED
        assert final.resolved_by == "human-2"

    async def test_three_of_three_quorum(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=3)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)
        r2 = await repo.resolve(approval_id, resolved_by="human-2", outcome=ApprovalStatus.APPROVED)
        assert r2.status == ApprovalStatus.PENDING
        r3 = await repo.resolve(approval_id, resolved_by="human-3", outcome=ApprovalStatus.APPROVED)
        assert r3.status == ApprovalStatus.APPROVED

    async def test_single_deny_vetoes_regardless_of_quorum(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=3)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)
        vetoed = await repo.resolve(
            approval_id, resolved_by="human-2", outcome=ApprovalStatus.DENIED
        )
        assert vetoed.status == ApprovalStatus.DENIED

        # No further votes possible -- it's closed.
        with pytest.raises(ApprovalAlreadyResolvedError):
            await repo.resolve(approval_id, resolved_by="human-3", outcome=ApprovalStatus.APPROVED)

    async def test_double_vote_from_same_identity_rejected(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=2)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)
        with pytest.raises(AlreadyVotedError):
            await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)

    async def test_self_approval_still_rejected_within_a_quorum(
        self, repo: ApprovalRepository
    ) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=2)
        with pytest.raises(SelfApprovalError):
            await repo.resolve(
                approval_id, resolved_by="agent-key", outcome=ApprovalStatus.APPROVED
            )

    async def test_consume_refused_until_quorum_reached(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=2)
        await repo.resolve(approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)

        action = _action()
        with pytest.raises(ApprovalNotApprovedError):
            await repo.consume(approval_id, action=action)

        await repo.resolve(approval_id, resolved_by="human-2", outcome=ApprovalStatus.APPROVED)
        consumed = await repo.consume(approval_id, action=action)
        assert consumed.status == ApprovalStatus.CONSUMED

    async def test_list_votes_returns_full_history(self, repo: ApprovalRepository) -> None:
        approval_id = await _seed_quorum_approval(repo, required_approvals=3)
        await repo.resolve(
            approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED, notes="lgtm"
        )
        await repo.resolve(approval_id, resolved_by="human-2", outcome=ApprovalStatus.APPROVED)

        votes = await repo.list_votes(approval_id)
        assert len(votes) == 2
        assert votes[0].resolver_identity_id == "human-1"
        assert votes[0].notes == "lgtm"
        assert votes[1].resolver_identity_id == "human-2"
        assert all(v.outcome == ApprovalStatus.APPROVED for v in votes)
