"""Tests for the execution-binding invariants an approval must enforce
(WhitePact v3 authority-layer spec, Sections 24/25/26/51):

- **Mutation invariant**: an approval is valid only for the exact
  action a human reviewed — changed arguments after approval must
  invalidate it.
- **Replay protection**: a consumed, single-use approval must not
  authorize a second execution.
- **Self-approval protection**: the identity that proposed an action
  cannot also resolve its own approval requirement.

`ApprovalRepository.consume()` is the execution-binding check point —
an executor must call it and only proceed on success. This file proves
each invariant it's supposed to enforce, not just that the method
exists.
"""

from __future__ import annotations

import pytest

from responsibleai.db import (
    ApprovalActionMismatchError,
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
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import (
    ApprovalStatus,
    build_approval_request,
    compute_action_digest,
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


def _identity(org_id: str = "org-1", identity_id: str = "agent-key") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1", identity_id: str = "agent-key") -> AgentContext:
    return AgentContext(identity=_identity(org_id, identity_id), framework="mcp-client")


def _payment_action(amount: int, target: str = "payments.execute") -> ActionRequest:
    return ActionRequest(
        agent=_agent(),
        action_type="payment",
        target=target,
        arguments={"amount_inr": amount, "beneficiary": "acme-vendor"},
    )


async def _seed_approved(approval_repo: ApprovalRepository, action: ActionRequest) -> str:
    """Real path: gateway produces REQUIRE_APPROVAL, the request is
    persisted, then a distinct human identity resolves it APPROVED —
    exactly what a caller does before ever calling consume()."""
    gateway = WhitePactRuntimeGateway()
    authority = AuthorityContext(
        delegated_by="org-1", granted_action_types=frozenset({"payment"}),
        require_approval_for=frozenset({"payment"}),
    )
    decision = gateway.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
    approval = await approval_repo.create(build_approval_request(action, decision))
    resolved = await approval_repo.resolve(
        approval.approval_id, resolved_by="human-approver-1", outcome=ApprovalStatus.APPROVED,
    )
    return resolved.approval_id


class TestMutationInvariant:
    async def test_matching_action_consumes_successfully(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)
        approval_id = await _seed_approved(approval_repo, action)
        consumed = await approval_repo.consume(approval_id, action=action)
        assert consumed.status == ApprovalStatus.CONSUMED

    async def test_changed_amount_is_rejected(self, approval_repo: ApprovalRepository) -> None:
        original = _payment_action(50_000)
        approval_id = await _seed_approved(approval_repo, original)

        mutated = _payment_action(5_000_000)  # amount changed after approval
        with pytest.raises(ApprovalActionMismatchError):
            await approval_repo.consume(approval_id, action=mutated)

    async def test_changed_target_is_rejected(self, approval_repo: ApprovalRepository) -> None:
        original = _payment_action(50_000, target="payments.execute")
        approval_id = await _seed_approved(approval_repo, original)

        mutated = _payment_action(50_000, target="payments.execute.admin-override")
        with pytest.raises(ApprovalActionMismatchError):
            await approval_repo.consume(approval_id, action=mutated)

    async def test_changed_beneficiary_argument_is_rejected(self, approval_repo: ApprovalRepository) -> None:
        original = _payment_action(50_000)
        approval_id = await _seed_approved(approval_repo, original)

        mutated = ActionRequest(
            agent=_agent(), action_type="payment", target="payments.execute",
            arguments={"amount_inr": 50_000, "beneficiary": "attacker-controlled-account"},
        )
        with pytest.raises(ApprovalActionMismatchError):
            await approval_repo.consume(approval_id, action=mutated)

    async def test_approval_with_no_digest_never_matches(self) -> None:
        """A row persisted before action_digest existed (empty string,
        the migration's server_default) must fail closed, not be
        silently treated as matching everything."""
        from datetime import UTC, datetime

        from responsibleai.governance.approval import ApprovalRequest

        approval = ApprovalRequest(
            action_id="a1", action_type="payment", target="payments.execute",
            reason_codes=[], requested_at=datetime.now(UTC), action_digest="",
        )
        action = _payment_action(50_000)
        assert approval.matches_action(action) is False


class TestReplayProtection:
    async def test_second_consume_of_same_action_fails(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)
        approval_id = await _seed_approved(approval_repo, action)

        first = await approval_repo.consume(approval_id, action=action)
        assert first.status == ApprovalStatus.CONSUMED

        with pytest.raises(ApprovalNotApprovedError):
            await approval_repo.consume(approval_id, action=action)

    async def test_consuming_pending_approval_fails(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = await approval_repo.create(build_approval_request(action, decision))

        with pytest.raises(ApprovalNotApprovedError):
            await approval_repo.consume(approval.approval_id, action=action)

    async def test_consuming_denied_approval_fails(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = await approval_repo.create(build_approval_request(action, decision))
        await approval_repo.resolve(
            approval.approval_id, resolved_by="human-approver-1", outcome=ApprovalStatus.DENIED,
        )

        with pytest.raises(ApprovalNotApprovedError):
            await approval_repo.consume(approval.approval_id, action=action)


class TestSelfApprovalProtection:
    async def test_requester_cannot_resolve_own_approval(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)  # requested_by == "agent-key"
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = await approval_repo.create(build_approval_request(action, decision))

        with pytest.raises(SelfApprovalError):
            await approval_repo.resolve(
                approval.approval_id, resolved_by="agent-key", outcome=ApprovalStatus.APPROVED,
            )

    async def test_different_identity_can_resolve(self, approval_repo: ApprovalRepository) -> None:
        action = _payment_action(50_000)
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"payment"}),
            require_approval_for=frozenset({"payment"}),
        )
        decision = gateway.evaluate(action, authority)
        approval = await approval_repo.create(build_approval_request(action, decision))

        resolved = await approval_repo.resolve(
            approval.approval_id, resolved_by="human-approver-1", outcome=ApprovalStatus.APPROVED,
        )
        assert resolved.status == ApprovalStatus.APPROVED


class TestComputeActionDigest:
    def test_identical_actions_produce_identical_digests(self) -> None:
        a = _payment_action(50_000)
        b = ActionRequest(
            agent=_agent(), action_type="payment", target="payments.execute",
            arguments={"amount_inr": 50_000, "beneficiary": "acme-vendor"},
        )
        assert compute_action_digest(a) == compute_action_digest(b)

    def test_argument_order_does_not_affect_digest(self) -> None:
        a = ActionRequest(
            agent=_agent(), action_type="payment", target="payments.execute",
            arguments={"amount_inr": 50_000, "beneficiary": "acme-vendor"},
        )
        b = ActionRequest(
            agent=_agent(), action_type="payment", target="payments.execute",
            arguments={"beneficiary": "acme-vendor", "amount_inr": 50_000},
        )
        assert compute_action_digest(a) == compute_action_digest(b)

    def test_different_amounts_produce_different_digests(self) -> None:
        a = _payment_action(50_000)
        b = _payment_action(50_001)
        assert compute_action_digest(a) != compute_action_digest(b)
