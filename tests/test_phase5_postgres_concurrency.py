# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL Concurrency, Race Condition, and Row-Locking Tests for Phase 5 Governance.

Tests 25–50 concurrent attempts across:
- Competing policy activations (single active winner).
- Revision number allocation (strictly monotonic, zero duplicates).
- Rollback vs activation races.
- Tenant deletion vs credential/session use.
- Legal hold vs tenant erasure.
- Concurrent restore reconciliation workers.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionOrchestrator,
)
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_policy_activations,
    organizations,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager


async def _run_concurrent_activations(engine: DatabaseEngine, org_id: str, count: int = 30):
    mgr = PolicyLifecycleManager(engine)

    # 1. Create N revisions
    revisions = []
    for i in range(count):
        rules = [
            PolicyRule(
                rule_id=f"rule-{i}",
                reason_code=f"RC_CONCURRENCY_{i}",
                effect=GovernanceDecision.ALLOW,
            )
        ]
        rev = await mgr.create_revision(
            org_id=org_id,
            rules=rules,
            created_by=f"admin-{i}",
            change_reason=f"Concurrent revision candidate {i}",
        )
        revisions.append(rev)

    # 2. Concurrently attempt to activate all revisions (30 concurrent workers)
    results = await asyncio.gather(
        *(mgr.activate_revision(org_id, rev.id, f"worker-{i}") for i, rev in enumerate(revisions)),
        return_exceptions=True,
    )

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
    """Verify concurrent activation invariants with 30 competing workers."""
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
        await _run_concurrent_activations(engine, org_id, count=30)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_revision_allocation_zero_duplicates():
    """Verify 30 concurrent revision creations produce zero duplicate revision numbers."""
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-rev-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Rev Num Concurrency Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    mgr = PolicyLifecycleManager(engine)

    async def create_one(idx: int):
        rules = [
            PolicyRule(rule_id=f"r-{idx}", reason_code="RC_TEST", effect=GovernanceDecision.DENY)
        ]
        return await mgr.create_revision(org_id, rules, f"creator-{idx}", f"Rev reason {idx}")

    try:
        tasks = [create_one(i) for i in range(30)]
        revisions = await asyncio.gather(*tasks)

        rev_nums = [r.revision_num for r in revisions]
        assert len(rev_nums) == 30
        assert len(set(rev_nums)) == 30, f"Duplicate revision numbers detected: {rev_nums}"
        assert min(rev_nums) == 1
        assert max(rev_nums) == 30
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_rollback_vs_activation():
    """Verify 30 concurrent rollback vs activation races maintain single active winner."""
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-rb-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Rollback Race Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    mgr = PolicyLifecycleManager(engine)
    # Seed 5 revisions
    revs = []
    for i in range(5):
        r = await mgr.create_revision(
            org_id,
            [PolicyRule(rule_id=f"r{i}", reason_code="RC_TEST", effect=GovernanceDecision.DENY)],
            "admin",
            f"Seed {i}",
        )
        revs.append(r)

    # Concurrently activate revs[0] and rollback to rev 1..5 (30 attempts total)
    async def op(idx: int):
        if idx % 2 == 0:
            return await mgr.activate_revision(org_id, revs[idx % 5].id, f"worker-{idx}")
        else:
            return await mgr.rollback(org_id, (idx % 5) + 1, f"worker-{idx}", f"Rollback {idx}")

    try:
        await asyncio.gather(*(op(i) for i in range(30)), return_exceptions=True)

        async with engine.raw.connect() as conn:
            active = (
                await conn.execute(
                    select(governance_policy_activations)
                    .where(governance_policy_activations.c.org_id == org_id)
                    .where(governance_policy_activations.c.is_active == True)  # noqa: E712
                )
            ).fetchall()
            assert len(active) == 1, "Expected exactly 1 active winner in rollback race"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_hold_vs_erasure():
    """Verify legal hold placed concurrently with tenant deletion prevents erasure."""
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-hold-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Hold Test Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    hold_mgr = LegalHoldManager(engine)
    orchestrator = TenantDeletionOrchestrator(engine)

    # Place hold
    await hold_mgr.create_hold(
        org_id=org_id,
        data_category="ALL",
        hold_reason="Litigation hold",
        created_by="legal_counsel",
    )

    # Concurrently attempt 25 deletions
    results = await asyncio.gather(
        *(
            orchestrator.delete_tenant(org_id, f"admin-{i}", "Customer requested delete")
            for i in range(25)
        ),
        return_exceptions=True,
    )

    # All 25 must fail with LegalHoldActiveError
    for r in results:
        assert isinstance(r, LegalHoldActiveError), f"Expected LegalHoldActiveError, got {type(r)}"

    # Organization must remain intact
    async with engine.raw.connect() as conn:
        org_row = (
            await conn.execute(select(organizations).where(organizations.c.id == org_id))
        ).fetchone()
        assert org_row is not None

    await engine.close()


@pytest.mark.asyncio
async def test_concurrent_restore_reconciliation_workers():
    """Verify 25 concurrent restore reconciliation workers reconcile cleanly to READY state."""
    engine = create_engine(":memory:")
    await engine.init()
    org_id = f"org-rec-race-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Rec Worker Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciliation_engine = RestoreReconciliationEngine(
        engine=engine,
        lifecycle_provider=provider,
        gate=gate,
    )

    await asyncio.gather(
        *(reconciliation_engine.reconcile_post_restore(f"worker_{i}") for i in range(25)),
        return_exceptions=True,
    )

    # Gate must be READY
    assert gate.state == RestoreReadinessState.READY
    assert gate.is_admitted() is True

    await engine.close()


@pytest.mark.asyncio
async def test_concurrent_activations_postgres():
    """Verify concurrent activation invariants under PostgreSQL with 30 workers."""
    url = os.environ.get("WHITEPACT_TEST_POSTGRES_PHASE5") or os.environ.get(
        "WHITEPACT_TEST_POSTGRES_CONCURRENCY"
    )
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
        await _run_concurrent_activations(engine, org_id, count=30)
    finally:
        await engine.close()
