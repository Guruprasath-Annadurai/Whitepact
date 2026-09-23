# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Legal Hold Foundation, Scoping & Release."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert

from responsibleai.data_governance.legal_hold import (
    LegalHoldManager,
)
from responsibleai.db.engine import DatabaseEngine, create_engine, organizations


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
                name="Test Org Legal Hold",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_legal_hold_creation_and_release(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = LegalHoldManager(sqlite_engine)

    # 1. No holds initially
    assert await mgr.is_held(sample_org) is False

    # 2. Create hold on PERSONAL data
    hold = await mgr.create_hold(sample_org, "PERSONAL", "Litigation hold", "legal-counsel")
    assert hold.active is True
    assert hold.org_id == sample_org

    # 3. Verify category is held, but other categories are not
    assert await mgr.is_held(sample_org, "PERSONAL") is True
    assert await mgr.is_held(sample_org, "TENANT_OPERATIONAL") is False

    # 4. Release hold
    released = await mgr.release_hold(sample_org, hold.id, "legal-counsel-2")
    assert released.active is False
    assert released.released_by == "legal-counsel-2"
    assert released.released_at is not None

    # 5. Verify no longer held
    assert await mgr.is_held(sample_org, "PERSONAL") is False


@pytest.mark.asyncio
async def test_legal_hold_tenant_isolation(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = LegalHoldManager(sqlite_engine)
    other_org = f"org-other-{uuid.uuid4().hex[:8]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=other_org,
                name="Other Org",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Place hold on sample_org
    await mgr.create_hold(sample_org, "ALL", "Audit hold", "admin")

    # Invariant: sample_org is held, other_org is NOT held
    assert await mgr.is_held(sample_org) is True
    assert await mgr.is_held(other_org) is False
