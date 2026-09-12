# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL Concurrency and Row Locking Tests for Phase 5 Policy Operations."""

from __future__ import annotations

import asyncio
import os
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


async def _run_concurrent_activations(engine: DatabaseEngine, org_id: str, count: int = 5):
    mgr = PolicyLifecycleManager(engine)

    # 1. Create N revisions
    revisions = []
    for i in range(count):
        rules = [
            PolicyRule(rule_id=f"rule-{i}", reason_code=f"RC_CONCURRENCY_{i}", effect=GovernanceDecision.ALLOW)
        ]
        rev = await mgr.create_revision(
            org_id=org_id,
            rules=rules,
            created_by=f"admin-{i}",
            change_reason=f"Concurrent revision candidate {i}",
        )
        revisions.append(rev)

    # 2. Concurrently attempt to activate all revisions
    results = await asyncio.gather(
        *(mgr.activate_revision(org_id, rev.id, f"worker-{i}") for i, rev in enumerate(revisions)),
        return_exceptions=True,
    )

    # Check that at least one succeeded and no unexpected crashes occurred
    successful_activations = [r for r in results if not isinstance(r, Exception)]
    assert len(successful_activations) >= 1

    # 3. Critical Invariant: Exactly ONE activation must have is_active = True
    async with engine.raw.connect() as conn:
        active_activations = (
            await conn.execute(
                select(governance_policy_activations)
                .where(governance_policy_activations.c.org_id == org_id)
                .where(governance_policy_activations.c.is_active == True)  # noqa: E712
            )
        ).fetchall()

        assert len(active_activations) == 1, (
            f"Expected exactly 1 active activation for org {org_id}, got {len(active_activations)}"
        )


@pytest.mark.asyncio
async def test_concurrent_activations_sqlite():
    """Verify concurrent activation invariants with file-backed SQLite."""
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Concurrency Org SQLite",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    try:
        await _run_concurrent_activations(engine, org_id, count=5)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_activations_postgres():
    """Verify concurrent activation invariants under PostgreSQL with row-level locks."""
    url = os.environ.get("WHITEPACT_TEST_POSTGRES_PHASE5") or os.environ.get("WHITEPACT_TEST_POSTGRES_CONCURRENCY")
    if not url:
        pytest.skip("WHITEPACT_TEST_POSTGRES_PHASE5 requires disposable PostgreSQL database")

    engine = create_engine(url)
    await engine.init()
    org_id = f"org-pg-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Concurrency Org PG",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    try:
        await _run_concurrent_activations(engine, org_id, count=10)
    finally:
        await engine.close()
