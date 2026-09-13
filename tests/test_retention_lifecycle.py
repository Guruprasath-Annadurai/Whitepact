# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Automated Retention Policy Lifecycle & Pruning."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.data_governance.retention import RetentionManager
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    eval_runs,
    organizations,
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
                name="Test Org Retention",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_retention_policy_creation_and_pruning(sqlite_engine: DatabaseEngine, sample_org: str):
    ret_mgr = RetentionManager(sqlite_engine)

    # 1. Set retention policy
    pol = await ret_mgr.set_retention_policy(sample_org, "TENANT_OPERATIONAL", 30 * 86400)
    assert pol.org_id == sample_org
    assert pol.retention_period_seconds == 30 * 86400

    # 2. Insert operational data
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(eval_runs).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                run_type="benchmark",
                model="gpt-4",
                provider="openai",
                payload="{}", 
                created_at="2026-08-01T00:00:00Z",
            )
        )

    # 3. Run retention cleanup
    report = await ret_mgr.run_retention_cleanup(sample_org)
    assert report.evaluated_policies == 1
    assert report.pruned_records.get("eval_runs", 0) == 1

    # 4. Verify record is pruned
    async with sqlite_engine.raw.connect() as conn:
        rows = (await conn.execute(select(eval_runs).where(eval_runs.c.org_id == sample_org))).fetchall()
        assert len(rows) == 0

    # 5. Idempotency test: re-running produces 0 errors and 0 new pruned records
    report2 = await ret_mgr.run_retention_cleanup(sample_org)
    assert report2.pruned_records.get("eval_runs", 0) == 0


@pytest.mark.asyncio
async def test_retention_skips_held_category(sqlite_engine: DatabaseEngine, sample_org: str):
    ret_mgr = RetentionManager(sqlite_engine)
    hold_mgr = LegalHoldManager(sqlite_engine)

    # Set retention policy
    await ret_mgr.set_retention_policy(sample_org, "TENANT_OPERATIONAL", 30 * 86400)

    # Place legal hold on TENANT_OPERATIONAL
    await hold_mgr.create_hold(sample_org, "TENANT_OPERATIONAL", "Audit preservation", "legal-admin")

    # Insert operational data
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(eval_runs).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                run_type="benchmark",
                model="claude-3",
                provider="anthropic",
                payload="{}", 
                created_at="2026-08-01T00:00:00Z",
            )
        )

    # Run retention cleanup
    report = await ret_mgr.run_retention_cleanup(sample_org)
    assert len(report.held_categories) == 1
    assert "eval_runs" not in report.pruned_records

    # Verify record was NOT deleted
    async with sqlite_engine.raw.connect() as conn:
        rows = (await conn.execute(select(eval_runs).where(eval_runs.c.org_id == sample_org))).fetchall()
        assert len(rows) == 1
