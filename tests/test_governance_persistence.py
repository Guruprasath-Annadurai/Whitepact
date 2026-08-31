# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for persisted governance evidence and approvals (SPEC.md
Section 3.7 / Phases 11-12): `EvidenceRepository`'s per-org hash chain
(and tamper detection) and `ApprovalRepository`'s resolution state
machine.
"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from responsibleai.db import (
    ApprovalAlreadyResolvedError,
    ApprovalNotFoundError,
    ApprovalRepository,
    EvidenceRepository,
    create_engine,
)
from responsibleai.db.engine import governance_evidence
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.evidence import build_evidence_record


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def evidence_repo(engine):
    return EvidenceRepository(engine)


@pytest.fixture()
def approval_repo(engine):
    return ApprovalRepository(engine)


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), framework="mcp-client")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call", "deployment"}))
    return AuthorityContext(**kwargs)


class TestEvidenceRepositoryRecordAndGet:
    async def test_record_and_get_round_trip(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)

        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        fetched = await evidence_repo.get(saved.evidence_id)

        assert fetched is not None
        assert fetched.evidence_id == saved.evidence_id
        assert fetched.decision == "ALLOW"
        assert fetched.organization_id == "org-1"
        assert fetched.hash == saved.hash

    async def test_get_unknown_id_returns_none(self, evidence_repo) -> None:
        assert await evidence_repo.get("does-not-exist") is None

    async def test_argument_keys_never_leak_values(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority()
        action = ActionRequest(
            agent=agent,
            action_type="mcp_tool_call",
            target="rai_scan",
            arguments={"text": "super secret contact me at a@b.com"},
        )
        decision = gw.evaluate(action, authority)
        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        fetched = await evidence_repo.get(saved.evidence_id)
        assert fetched.argument_keys == ["text"]

    async def test_delegation_chain_persisted_round_trip(self, evidence_repo) -> None:
        """v3 authority-layer work (Task #143): AuthorityContext.
        delegation_chain must survive a real DB write/read, not just
        the in-memory build_evidence_record() step."""
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(
            delegated_by=agent.agent_id, delegation_chain=("org-1", "alice", agent.agent_id)
        )
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)

        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        fetched = await evidence_repo.get(saved.evidence_id)
        assert fetched.delegation_chain == ["org-1", "alice", agent.agent_id]

    async def test_no_delegation_chain_persists_as_empty_list(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)

        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        fetched = await evidence_repo.get(saved.evidence_id)
        assert fetched.delegation_chain == []


class TestEvidenceHashChain:
    async def test_first_entry_has_no_prev_hash(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        assert saved.prev_hash is None
        assert saved.hash is not None

    async def test_second_entry_chains_onto_first(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        first = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        second = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        assert second.prev_hash == first.hash
        assert second.hash != first.hash

    async def test_chains_are_independent_per_org(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority()
        action_a = ActionRequest(
            agent=_agent("org-a"), action_type="mcp_tool_call", target="rai_health"
        )
        action_b = ActionRequest(
            agent=_agent("org-b"), action_type="mcp_tool_call", target="rai_health"
        )
        decision = gw.evaluate(action_a, authority)

        first_a = await evidence_repo.record(
            build_evidence_record(action_a, _agent("org-a"), authority, decision)
        )
        first_b = await evidence_repo.record(
            build_evidence_record(action_b, _agent("org-b"), authority, decision)
        )
        assert first_a.prev_hash is None
        assert first_b.prev_hash is None  # org-b's chain isn't affected by org-a's entry

    async def test_verify_chain_true_when_untampered(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        for _ in range(3):
            await evidence_repo.record(build_evidence_record(action, agent, authority, decision))
        assert await evidence_repo.verify_chain("org-1") is True

    async def test_verify_chain_empty_org_is_true(self, evidence_repo) -> None:
        assert await evidence_repo.verify_chain("org-with-no-evidence") is True

    async def test_verify_chain_detects_tampered_field(self, evidence_repo, engine) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        saved = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )

        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_evidence)
                .where(governance_evidence.c.id == saved.evidence_id)
                .values(decision="DENY")
            )

        assert await evidence_repo.verify_chain("org-1") is False

    async def test_verify_chain_detects_broken_link(self, evidence_repo, engine) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        await evidence_repo.record(build_evidence_record(action, agent, authority, decision))
        second = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )

        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_evidence)
                .where(governance_evidence.c.id == second.evidence_id)
                .values(prev_hash="0" * 64)
            )

        assert await evidence_repo.verify_chain("org-1") is False


class TestEvidenceListing:
    async def test_list_for_org_ordered_newest_first(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent, authority = _agent(), _authority()
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        decision = gw.evaluate(action, authority)
        first = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )
        second = await evidence_repo.record(
            build_evidence_record(action, agent, authority, decision)
        )

        listed = await evidence_repo.list_for_org("org-1")
        assert [e.evidence_id for e in listed] == [second.evidence_id, first.evidence_id]

    async def test_list_for_org_scoped_by_org(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority()
        action_a = ActionRequest(
            agent=_agent("org-a"), action_type="mcp_tool_call", target="rai_health"
        )
        decision = gw.evaluate(action_a, authority)
        await evidence_repo.record(
            build_evidence_record(action_a, _agent("org-a"), authority, decision)
        )

        assert len(await evidence_repo.list_for_org("org-a")) == 1
        assert len(await evidence_repo.list_for_org("org-b")) == 0

    async def test_list_for_org_filters_by_decision(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        allow_authority = _authority()
        deny_authority = _authority(granted_action_types=frozenset())  # nothing granted -> DENY

        allow_action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        deny_action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")

        await evidence_repo.record(
            build_evidence_record(
                allow_action,
                agent,
                allow_authority,
                gw.evaluate(allow_action, allow_authority),
            )
        )
        await evidence_repo.record(
            build_evidence_record(
                deny_action,
                agent,
                deny_authority,
                gw.evaluate(deny_action, deny_authority),
            )
        )

        only_denies = await evidence_repo.list_for_org("org-1", decision="DENY")
        assert len(only_denies) == 1
        assert only_denies[0].decision == "DENY"


class TestApprovalRepositoryCreateAndList:
    async def test_create_persists_pending_request(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        decision = gw.evaluate(action, authority)
        assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL

        saved = await approval_repo.create(build_approval_request(action, decision))
        fetched = await approval_repo.get(saved.approval_id)
        assert fetched is not None
        assert fetched.status == ApprovalStatus.PENDING
        assert fetched.organization_id == "org-1"
        assert fetched.requested_by == "k1"

    async def test_get_unknown_id_returns_none(self, approval_repo) -> None:
        assert await approval_repo.get("does-not-exist") is None

    async def test_list_pending_scoped_by_org(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action_a = ActionRequest(agent=_agent("org-a"), action_type="deployment", target="prod")
        await approval_repo.create(
            build_approval_request(action_a, gw.evaluate(action_a, authority))
        )

        assert len(await approval_repo.list_pending("org-a")) == 1
        assert len(await approval_repo.list_pending("org-b")) == 0

    async def test_list_pending_excludes_resolved(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )

        assert len(await approval_repo.list_pending("org-1")) == 1
        await approval_repo.resolve(
            saved.approval_id,
            resolved_by="admin",
            outcome=ApprovalStatus.APPROVED,
        )
        assert len(await approval_repo.list_pending("org-1")) == 0


class TestApprovalResolution:
    async def test_resolve_approved(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )

        resolved = await approval_repo.resolve(
            saved.approval_id,
            resolved_by="admin@org-1",
            outcome=ApprovalStatus.APPROVED,
            notes="ok",
        )
        assert resolved.status == ApprovalStatus.APPROVED
        assert resolved.resolved_by == "admin@org-1"
        assert resolved.resolution_notes == "ok"
        assert resolved.resolved_at is not None

    async def test_resolve_denied(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )

        resolved = await approval_repo.resolve(
            saved.approval_id,
            resolved_by="admin@org-1",
            outcome=ApprovalStatus.DENIED,
        )
        assert resolved.status == ApprovalStatus.DENIED

    async def test_resolve_unknown_id_raises_not_found(self, approval_repo) -> None:
        with pytest.raises(ApprovalNotFoundError):
            await approval_repo.resolve(
                "does-not-exist",
                resolved_by="admin",
                outcome=ApprovalStatus.APPROVED,
            )

    async def test_double_resolve_raises(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )

        await approval_repo.resolve(
            saved.approval_id, resolved_by="admin", outcome=ApprovalStatus.APPROVED
        )
        with pytest.raises(ApprovalAlreadyResolvedError):
            await approval_repo.resolve(
                saved.approval_id, resolved_by="other", outcome=ApprovalStatus.DENIED
            )

    async def test_resolve_with_pending_outcome_rejected(self, approval_repo) -> None:
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )

        with pytest.raises(ValueError, match="APPROVED or DENIED"):
            await approval_repo.resolve(
                saved.approval_id, resolved_by="admin", outcome=ApprovalStatus.PENDING
            )

    async def test_first_resolution_preserved_after_failed_second_attempt(
        self, approval_repo
    ) -> None:
        """The state after a rejected double-resolve attempt must still
        reflect the *original* resolution, not anything from the second
        attempt."""
        gw = WhitePactRuntimeGateway()
        agent = _agent()
        authority = _authority(require_approval_for=frozenset({"deployment"}))
        action = ActionRequest(agent=agent, action_type="deployment", target="prod")
        saved = await approval_repo.create(
            build_approval_request(action, gw.evaluate(action, authority))
        )
        await approval_repo.resolve(
            saved.approval_id, resolved_by="admin-1", outcome=ApprovalStatus.APPROVED
        )

        with pytest.raises(ApprovalAlreadyResolvedError):
            await approval_repo.resolve(
                saved.approval_id, resolved_by="admin-2", outcome=ApprovalStatus.DENIED
            )

        final = await approval_repo.get(saved.approval_id)
        assert final.status == ApprovalStatus.APPROVED
        assert final.resolved_by == "admin-1"
