# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Concurrency & Race Condition Verification for WhitePact Phase 5 Policy Operations."""

from __future__ import annotations

import asyncio
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
from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager


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
                name="Test Org Concurrency",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_concurrent_revision_creation(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)

    async def create_single_rev(idx: int):
        rules = [PolicyRule(rule_id=f"rule-{idx}", reason_code="RC_TEST", effect=GovernanceDecision.ALLOW)]
        return await mgr.create_revision(sample_org, rules, f"admin-{idx}", f"Concurrent rev {idx}")

    # Launch 5 concurrent revision creations
    tasks = [create_single_rev(i) for i in range(5)]
    revisions = await asyncio.gather(*tasks)

    # All 5 revisions must exist and have unique revision numbers
    revision_nums = [r.revision_num for r in revisions]
    assert len(set(revision_nums)) == 5
    assert sorted(revision_nums) == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_concurrent_activations_single_winner(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)

    # Create 3 revisions
    revs = []
    for i in range(3):
        rules = [PolicyRule(rule_id=f"rule-{i}", reason_code="RC_TEST", effect=GovernanceDecision.ALLOW)]
        rev = await mgr.create_revision(sample_org, rules, f"admin-{i}", f"Rev {i}")
        revs.append(rev)

    # Concurrently activate all 3
    tasks = [mgr.activate_revision(sample_org, rev.id, f"activator-{i}") for i, rev in enumerate(revs)]
    await asyncio.gather(*tasks)

    # Exactly ONE activation must have is_active = True
    async with sqlite_engine.raw.connect() as conn:
        active_rows = (
            await conn.execute(
                select(governance_policy_activations)
                .where(governance_policy_activations.c.org_id == sample_org)
                .where(governance_policy_activations.c.is_active == True)  # noqa: E712
            )
        ).fetchall()
        assert len(active_rows) == 1
