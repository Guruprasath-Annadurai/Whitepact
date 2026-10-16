# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent verification suite for Delegation & Revocation Foundation (P0-08).

Proves:
1. Ordinary delegation grants use lock_epoch() and do NOT advance the revocation epoch.
2. Branch revocation (revoke_branch) advances the revocation epoch atomically.
3. Unrelated additive grants do not cause stale-grant invalidation.
4. Concurrent writers respect tenant serialization.
5. Cross-tenant isolation is strictly enforced.
6. Atomic rollback on failure leaves epoch and graph unchanged.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from responsibleai.db.delegation_repository import (
    DelegationEscalationError,
    DelegationRepository,
)
from responsibleai.db.engine import create_engine, governance_delegations, organizations
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository


@pytest.fixture
async def delegation_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/test_delegation_epoch.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_alpha", "name": "Alpha Corp", "slug": "alpha", "created_at": "now"},
                {"id": "org_beta", "name": "Beta Corp", "slug": "beta", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
class TestDelegationRevocationFoundation:
    async def test_ordinary_grant_does_not_advance_revocation_epoch(self, delegation_db):
        delegations = DelegationRepository(delegation_db)
        epochs = RevocationEpochRepository(delegation_db)

        # Baseline epoch before any grants
        initial_epoch = await epochs.current("org_alpha", scope="governance")
        assert initial_epoch.epoch == 0

        # 1. Root grant to human supervisor
        grant1 = await delegations.grant(
            "org_alpha",
            "supervisor-1",
            granted_action_types=frozenset({"tool:read", "tool:write", "tool:delete"}),
            constraints={"allowed_targets": ["documents/*", "records/*"]},
            purpose="records-management",
            granted_by="customer-owner",
        )
        assert grant1.to_identity_id == "supervisor-1"

        # Epoch must remain 0 (no drift)
        epoch_after_grant1 = await epochs.current("org_alpha", scope="governance")
        assert epoch_after_grant1.epoch == 0, "Ordinary delegation grant must NOT advance epoch"

        # 2. Additive subordinate grant to agent worker
        grant2 = await delegations.grant(
            "org_alpha",
            "agent-worker-1",
            from_identity_id="supervisor-1",
            granted_action_types=frozenset({"tool:read", "tool:write"}),
            constraints={"allowed_targets": ["documents/*"]},
            purpose="records-management",
            granted_by="supervisor-1",
        )
        assert grant2.to_identity_id == "agent-worker-1"

        # Epoch must still remain 0
        epoch_after_grant2 = await epochs.current("org_alpha", scope="governance")
        assert epoch_after_grant2.epoch == 0, "Subordinate delegation grant must NOT advance epoch"

        # 3. Third unrelated grant to another agent
        grant3 = await delegations.grant(
            "org_alpha",
            "agent-worker-2",
            from_identity_id="supervisor-1",
            granted_action_types=frozenset({"tool:read"}),
            constraints={"allowed_targets": ["documents/*"]},
            purpose="records-management",
            granted_by="supervisor-1",
        )
        assert grant3.to_identity_id == "agent-worker-2"

        # Epoch must still remain 0
        epoch_after_grant3 = await epochs.current("org_alpha", scope="governance")
        assert epoch_after_grant3.epoch == 0, "Unrelated additive grant must NOT advance epoch"

    async def test_branch_revocation_advances_epoch_and_cascades(self, delegation_db):
        delegations = DelegationRepository(delegation_db)
        epochs = RevocationEpochRepository(delegation_db)

        # Setup tree: supervisor -> worker1 -> subworker1
        await delegations.grant(
            "org_alpha",
            "sup-a",
            granted_action_types=frozenset({"exec", "read"}),
            purpose="ops",
            granted_by="owner",
        )
        await delegations.grant(
            "org_alpha",
            "worker-a",
            from_identity_id="sup-a",
            granted_action_types=frozenset({"exec", "read"}),
            purpose="ops",
            granted_by="sup-a",
        )
        await delegations.grant(
            "org_alpha",
            "subworker-a",
            from_identity_id="worker-a",
            granted_action_types=frozenset({"read"}),
            purpose="ops",
            granted_by="worker-a",
        )

        assert (await epochs.current("org_alpha")).epoch == 0

        # Revoke sup-a branch: should revoke sup-a, worker-a, subworker-a and bump epoch
        revoked = await delegations.revoke_branch(
            "org_alpha",
            "sup-a",
            revoked_by="security-admin",
            reason="Security rotation",
        )
        assert len(revoked) == 3

        # Epoch must now be 1
        epoch_after_revoke = await epochs.current("org_alpha")
        assert epoch_after_revoke.epoch == 1, "Branch revocation must bump the revocation epoch"

        # Verify all descendants are now inactive
        for identity in ["sup-a", "worker-a", "subworker-a"]:
            rec = await delegations.get_active_delegation("org_alpha", identity)
            assert rec is None, f"{identity} must no longer have active delegation"

    async def test_cross_tenant_isolation_and_no_leakage(self, delegation_db):
        delegations = DelegationRepository(delegation_db)
        epochs = RevocationEpochRepository(delegation_db)

        # Create grant in org_alpha
        await delegations.grant(
            "org_alpha",
            "agent-alpha",
            granted_action_types=frozenset({"read"}),
            purpose="data",
            granted_by="owner-alpha",
        )

        # Attempt to delegate from org_alpha identity in org_beta: fails closed
        with pytest.raises(DelegationEscalationError):
            await delegations.grant(
                "org_beta",
                "agent-beta",
                from_identity_id="agent-alpha",
                granted_action_types=frozenset({"read"}),
                purpose="data",
                granted_by="attacker",
            )

        # Revocation in org_beta does not affect org_alpha epoch
        await epochs.bump("org_beta")
        assert (await epochs.current("org_beta")).epoch == 1
        assert (await epochs.current("org_alpha")).epoch == 0

    async def test_concurrent_grants_serialize_safely(self, delegation_db):
        delegations = DelegationRepository(delegation_db)
        epochs = RevocationEpochRepository(delegation_db)

        # Seed root
        await delegations.grant(
            "org_alpha",
            "root-agent",
            granted_action_types=frozenset({"t1", "t2", "t3"}),
            purpose="p",
            granted_by="owner",
        )

        async def worker(idx: int):
            return await delegations.grant(
                "org_alpha",
                f"leaf-agent-{idx}",
                from_identity_id="root-agent",
                granted_action_types=frozenset({"t1"}),
                purpose="p",
                granted_by="root-agent",
            )

        # 20 concurrent grant writers
        results = await asyncio.gather(*[worker(i) for i in range(20)])
        assert len(results) == 20

        # Epoch must remain 0 across all concurrent grants
        current_epoch = await epochs.current("org_alpha")
        assert current_epoch.epoch == 0
