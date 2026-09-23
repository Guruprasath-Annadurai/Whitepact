# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Atomic Policy Activation and Governance Epoch Synchronization."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_policies,
    governance_policy_activations,
    governance_policy_versions,
    governance_revocation_epochs,
    organizations,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager
from responsibleai.governance.risk import RiskTier


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture
async def sample_org(sqlite_engine: DatabaseEngine):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Test Org Activation",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_atomic_activation_and_single_active_winner(
    sqlite_engine: DatabaseEngine, sample_org: str
):
    mgr = PolicyLifecycleManager(sqlite_engine)

    # 1. Create Revision 1
    rules1 = [PolicyRule(rule_id="r1", reason_code="RC_ALLOW", effect=GovernanceDecision.ALLOW)]
    rev1 = await mgr.create_revision(sample_org, rules1, "admin-1", "Rev 1")

    # 2. Activate Revision 1
    act1 = await mgr.activate_revision(sample_org, rev1.id, "admin-1")
    assert act1.is_active is True
    assert act1.revision_id == rev1.id

    active_now = await mgr.get_active_activation(sample_org)
    assert active_now is not None
    assert active_now.id == act1.id

    # 3. Create Revision 2 and activate
    rules2 = [PolicyRule(rule_id="r2", reason_code="RC_DENY", effect=GovernanceDecision.DENY)]
    rev2 = await mgr.create_revision(sample_org, rules2, "admin-2", "Rev 2")
    act2 = await mgr.activate_revision(sample_org, rev2.id, "admin-2")

    assert act2.is_active is True
    assert act2.previous_activation_id == act1.id

    # Verify only ONE row in governance_policy_activations has is_active = True for this org
    async with sqlite_engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(governance_policy_activations)
                .where(governance_policy_activations.c.org_id == sample_org)
                .where(governance_policy_activations.c.is_active == True)  # noqa: E712
            )
        ).fetchall()
        assert len(rows) == 1
        assert rows[0].id == act2.id


@pytest.mark.asyncio
async def test_activation_epoch_and_compatibility_sync(
    sqlite_engine: DatabaseEngine, sample_org: str
):
    mgr = PolicyLifecycleManager(sqlite_engine)
    rules = [
        PolicyRule(
            rule_id="rule-sync-1",
            reason_code="RC_SYNC",
            effect=GovernanceDecision.ALLOW,
            risk_tiers=frozenset({RiskTier.LOW}),
            action_types=frozenset({"execute"}),
            targets=frozenset({"tool-1"}),
        )
    ]
    rev = await mgr.create_revision(sample_org, rules, "admin", "Sync check")
    act = await mgr.activate_revision(sample_org, rev.id, "admin")

    # Verify epoch was incremented
    assert act.governance_epoch >= 1
    async with sqlite_engine.raw.connect() as conn:
        epoch_row = (
            await conn.execute(
                select(governance_revocation_epochs.c.epoch).where(
                    governance_revocation_epochs.c.organization_id == sample_org
                )
            )
        ).scalar()
        assert epoch_row == act.governance_epoch

        # Verify legacy governance_policies table was synchronized
        policy_rows = (
            await conn.execute(
                select(governance_policies).where(governance_policies.c.org_id == sample_org)
            )
        ).fetchall()
        assert len(policy_rows) == 1
        assert policy_rows[0].rule_id == "rule-sync-1"

        # Verify legacy governance_policy_versions table was bumped
        v_row = (
            await conn.execute(
                select(governance_policy_versions.c.version).where(
                    governance_policy_versions.c.org_id == sample_org
                )
            )
        ).scalar()
        assert v_row >= 1
