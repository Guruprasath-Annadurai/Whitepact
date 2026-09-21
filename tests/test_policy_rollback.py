# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Safe Policy Rollback & History Preservation."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_policy_activations,
    organizations,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import (
    PolicyLifecycleManager,
    PolicyRevisionNotFoundError,
)


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
                name="Test Org Rollback",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_safe_rollback_preserves_revision_history(
    sqlite_engine: DatabaseEngine, sample_org: str
):
    mgr = PolicyLifecycleManager(sqlite_engine)

    # 1. Create and activate Rev 1
    rules1 = [PolicyRule(rule_id="r1", reason_code="RC_DENY", effect=GovernanceDecision.DENY)]
    rev1 = await mgr.create_revision(sample_org, rules1, "admin-1", "Revision 1")
    await mgr.activate_revision(sample_org, rev1.id, "admin-1")

    # 2. Create and activate Rev 2
    rules2 = [
        PolicyRule(rule_id="r1", reason_code="RC_DENY", effect=GovernanceDecision.DENY),
        PolicyRule(rule_id="r2", reason_code="RC_ALLOW", effect=GovernanceDecision.ALLOW),
    ]
    rev2 = await mgr.create_revision(sample_org, rules2, "admin-2", "Revision 2")
    await mgr.activate_revision(sample_org, rev2.id, "admin-2")

    # 3. Rollback to Rev 1
    act_rollback = await mgr.rollback(
        sample_org, target_revision_num=1, rolled_back_by="admin-3", reason="Reverting to rev 1"
    )
    assert act_rollback.revision_id == rev1.id
    assert act_rollback.is_active is True

    # 4. Invariant Verification: All revisions R1 and R2 must STILL EXIST!
    revisions = await mgr.get_revisions(sample_org)
    assert len(revisions) == 2
    assert [r.revision_num for r in revisions] == [1, 2]

    # 5. Activation history has 3 total entries (rev1 -> rev2 -> rollback to rev1)
    async with sqlite_engine.raw.connect() as conn:
        activations = (
            await conn.execute(
                select(governance_policy_activations)
                .where(governance_policy_activations.c.org_id == sample_org)
                .order_by(governance_policy_activations.c.governance_epoch.asc())
            )
        ).fetchall()
        assert len(activations) == 3
        # First two activations are inactive, latest is active
        assert activations[0].is_active is False
        assert activations[1].is_active is False
        assert activations[2].is_active is True
        assert activations[2].id == act_rollback.id


@pytest.mark.asyncio
async def test_rollback_invalid_revision_fails(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)
    with pytest.raises(PolicyRevisionNotFoundError):
        await mgr.rollback(
            sample_org, target_revision_num=999, rolled_back_by="admin", reason="Non-existent"
        )
