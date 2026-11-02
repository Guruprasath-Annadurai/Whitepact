"""Tests for the Delegation Graph (Core Invariant #2, v3 authority-layer
work): `DelegationRecord` (governance/delegation.py) and
`DelegationRepository` (db/delegation_repository.py) -- persisted
who-delegated-to-whom, attenuation enforced at grant time, continuous
re-authorization, and cascading revocation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db import (
    DelegationEscalationError,
    DelegationRepository,
    create_engine,
)
from responsibleai.governance.delegation import DelegationRecord


class TestDelegationRecordIsActive:
    def _record(self, **overrides) -> DelegationRecord:
        defaults = dict(
            delegation_id="d1",
            org_id="org-1",
            from_identity_id=None,
            to_identity_id="agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="test",
            granted_by="owner",
            granted_at=datetime.now(UTC),
        )
        defaults.update(overrides)
        return DelegationRecord(**defaults)

    def test_fresh_grant_is_active(self) -> None:
        assert self._record().is_active() is True

    def test_revoked_grant_is_inactive(self) -> None:
        assert self._record(revoked_at=datetime.now(UTC)).is_active() is False

    def test_expired_grant_is_inactive(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=1)
        assert self._record(expires_at=past).is_active() is False

    def test_future_expiry_is_still_active(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=10)
        assert self._record(expires_at=future).is_active() is True

    def test_to_authority_context_uses_from_identity_when_present(self) -> None:
        record = self._record(from_identity_id="mgr-1")
        assert record.to_authority_context().delegated_by == "mgr-1"

    def test_to_authority_context_falls_back_to_granted_by_for_root_grant(self) -> None:
        record = self._record(from_identity_id=None, granted_by="owner-9")
        assert record.to_authority_context().delegated_by == "owner-9"


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def repo(engine):
    return DelegationRepository(engine)


class TestGrantRootDelegation:
    async def test_grant_and_get_round_trip(self, repo) -> None:
        record = await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="autopay",
            granted_by="owner-1",
        )
        assert record.from_identity_id is None
        assert record.to_identity_id == "agent-1"
        fetched = await repo.get(record.delegation_id)
        assert fetched == record

    async def test_get_active_delegation_returns_it(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        active = await repo.get_active_delegation("org-1", "agent-1")
        assert active is not None
        assert active.to_identity_id == "agent-1"

    async def test_get_active_delegation_none_when_never_granted(self, repo) -> None:
        assert await repo.get_active_delegation("org-1", "nobody") is None

    async def test_get_latest_delegation_returns_expired_row(self, repo) -> None:
        past = datetime.now(UTC) - timedelta(minutes=1)
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
            expires_at=past,
        )
        latest = await repo.get_latest_delegation("org-1", "agent-1")
        assert latest is not None
        assert latest.is_active() is False
        # But get_active_delegation() correctly says None -- expired.
        assert await repo.get_active_delegation("org-1", "agent-1") is None

    async def test_orgs_are_isolated(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        assert await repo.get_active_delegation("org-2", "agent-1") is None

    async def test_second_grant_supersedes_first_as_current(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p1",
            granted_by="owner-1",
        )
        second = await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"y"}),
            purpose="p2",
            granted_by="owner-1",
        )
        active = await repo.get_active_delegation("org-1", "agent-1")
        assert active is not None
        assert active.delegation_id == second.delegation_id
        assert active.granted_action_types == frozenset({"y"})

    async def test_effective_authority_none_when_no_delegation(self, repo) -> None:
        assert await repo.get_effective_authority("org-1", "nobody") is None

    async def test_effective_authority_reflects_active_grant(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="p",
            granted_by="owner-1",
        )
        authority = await repo.get_effective_authority("org-1", "agent-1")
        assert authority is not None
        assert authority.granted_action_types == frozenset({"payment.execute"})


class TestGrantAttenuationEnforcement:
    """The invariant this whole graph exists to enforce: a delegated
    grant must never exceed what its own delegator currently, actively
    holds -- checked live at grant time, not just at call time."""

    async def test_child_within_parent_grant_succeeds(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 500_000},
            purpose="mgr root grant",
            granted_by="owner-1",
        )
        child = await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 100_000},
            purpose="delegated subset",
            granted_by="manager-1",
            from_identity_id="manager-1",
        )
        assert child.from_identity_id == "manager-1"

    async def test_child_exceeding_parent_value_limit_rejected(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 500_000},
            purpose="mgr root grant",
            granted_by="owner-1",
        )
        with pytest.raises(DelegationEscalationError):
            await repo.grant(
                "org-1",
                "agent-1",
                granted_action_types=frozenset({"payment.execute"}),
                constraints={"max_value_usd": 1_000_000},
                purpose="escalation attempt",
                granted_by="manager-1",
                from_identity_id="manager-1",
            )

    async def test_child_action_type_outside_parent_grant_rejected(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="mgr root grant",
            granted_by="owner-1",
        )
        with pytest.raises(DelegationEscalationError):
            await repo.grant(
                "org-1",
                "agent-1",
                granted_action_types=frozenset({"payment.execute", "user.delete"}),
                purpose="escalation attempt",
                granted_by="manager-1",
                from_identity_id="manager-1",
            )

    async def test_delegating_from_identity_with_no_active_grant_rejected(self, repo) -> None:
        with pytest.raises(DelegationEscalationError):
            await repo.grant(
                "org-1",
                "agent-1",
                granted_action_types=frozenset({"x"}),
                purpose="orphan delegation",
                granted_by="ghost-manager",
                from_identity_id="ghost-manager",
            )

    async def test_delegating_from_identity_with_revoked_grant_rejected(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="mgr root grant",
            granted_by="owner-1",
        )
        await repo.revoke_branch("org-1", "manager-1", revoked_by="owner-1", reason="offboarded")
        with pytest.raises(DelegationEscalationError):
            await repo.grant(
                "org-1",
                "agent-1",
                granted_action_types=frozenset({"payment.execute"}),
                purpose="delegation from revoked manager",
                granted_by="manager-1",
                from_identity_id="manager-1",
            )

    async def test_validate_delegation_dry_run_matches_grant_outcome(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 500_000},
            purpose="mgr root grant",
            granted_by="owner-1",
        )
        ok = await repo.validate_delegation(
            "org-1",
            "manager-1",
            frozenset({"payment.execute"}),
            constraints={"max_value_usd": 100_000},
        )
        assert ok is None
        bad = await repo.validate_delegation(
            "org-1",
            "manager-1",
            frozenset({"payment.execute"}),
            constraints={"max_value_usd": 1_000_000},
        )
        assert bad is not None


class TestAuthorityChain:
    async def test_chain_is_empty_for_unknown_identity(self, repo) -> None:
        assert await repo.get_authority_chain("org-1", "nobody") == []

    async def test_root_only_chain_has_one_hop(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        chain = await repo.get_authority_chain("org-1", "agent-1")
        assert len(chain) == 1
        assert chain[0].to_identity_id == "agent-1"

    async def test_multi_hop_chain_is_root_first(self, repo) -> None:
        await repo.grant(
            "org-1",
            "vp-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="p",
            granted_by="vp-1",
            from_identity_id="vp-1",
        )
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="p",
            granted_by="manager-1",
            from_identity_id="manager-1",
        )
        chain = await repo.get_authority_chain("org-1", "agent-1")
        assert [hop.to_identity_id for hop in chain] == ["vp-1", "manager-1", "agent-1"]

    async def test_chain_stops_at_a_revoked_ancestor(self, repo) -> None:
        await repo.grant(
            "org-1",
            "vp-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="vp-1",
            from_identity_id="vp-1",
        )
        await repo.revoke_branch("org-1", "vp-1", revoked_by="owner-1", reason="offboarded")
        # manager-1's own delegation was cascaded away by revoke_branch,
        # so get_authority_chain(manager-1) finds nothing active at all.
        assert await repo.get_authority_chain("org-1", "manager-1") == []


class TestCascadingRevocation:
    async def test_revoking_a_leaf_only_affects_the_leaf(self, repo) -> None:
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="manager-1",
            from_identity_id="manager-1",
        )
        revoked = await repo.revoke_branch("org-1", "agent-1", revoked_by="owner-1", reason="done")
        assert len(revoked) == 1
        assert await repo.get_active_delegation("org-1", "manager-1") is not None
        assert await repo.get_active_delegation("org-1", "agent-1") is None

    async def test_revoking_a_parent_cascades_to_every_descendant(self, repo) -> None:
        await repo.grant(
            "org-1",
            "vp-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.grant(
            "org-1",
            "manager-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="vp-1",
            from_identity_id="vp-1",
        )
        await repo.grant(
            "org-1",
            "manager-2",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="vp-1",
            from_identity_id="vp-1",
        )
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="manager-1",
            from_identity_id="manager-1",
        )
        revoked = await repo.revoke_branch(
            "org-1", "vp-1", revoked_by="owner-1", reason="offboarded"
        )
        assert set(revoked) == {
            (await repo.get_latest_delegation("org-1", i)).delegation_id
            for i in ("vp-1", "manager-1", "manager-2", "agent-1")
        }
        for identity in ("vp-1", "manager-1", "manager-2", "agent-1"):
            assert await repo.get_active_delegation("org-1", identity) is None

    async def test_revoking_an_already_inactive_identity_is_a_noop(self, repo) -> None:
        assert await repo.revoke_branch("org-1", "nobody", revoked_by="owner-1", reason="n/a") == []

    async def test_revoke_stamps_revoked_by_and_reason(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.revoke_branch(
            "org-1", "agent-1", revoked_by="owner-9", reason="security incident"
        )
        record = await repo.get_latest_delegation("org-1", "agent-1")
        assert record is not None
        assert record.revoked_by == "owner-9"
        assert record.revoke_reason == "security incident"
        assert record.is_active() is False


class TestExplainAuthority:
    async def test_explain_unknown_identity(self, repo) -> None:
        explanation = await repo.explain_authority("org-1", "nobody")
        assert explanation["currently_active"] is False
        assert explanation["chain"] == []

    async def test_explain_active_identity(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"payment.execute"}),
            purpose="autopay",
            granted_by="owner-1",
        )
        explanation = await repo.explain_authority("org-1", "agent-1")
        assert explanation["currently_active"] is True
        assert len(explanation["chain"]) == 1
        assert explanation["chain"][0]["purpose"] == "autopay"

    async def test_explain_revoked_identity_shows_inactive_but_not_erased(self, repo) -> None:
        await repo.grant(
            "org-1",
            "agent-1",
            granted_action_types=frozenset({"x"}),
            purpose="p",
            granted_by="owner-1",
        )
        await repo.revoke_branch("org-1", "agent-1", revoked_by="owner-1", reason="done")
        explanation = await repo.explain_authority("org-1", "agent-1")
        assert explanation["currently_active"] is False
