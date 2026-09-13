# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Data Erasure State Machine & Zero False Completion Invariants."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.erasure import (
    DataErasureManager,
    ErasureStatus,
)
from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    incidents,
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
                name="Test Org Erasure",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_erasure_state_machine_and_verification(sqlite_engine: DatabaseEngine, sample_org: str):
    erasure_mgr = DataErasureManager(sqlite_engine)

    # Insert erasable operational data
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                incident_type="POLICY_BREACH",
                severity="HIGH",
                siem_event_type="ALERT",
                description="Incident to erase",
                evidence_hash="hash-99",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # 1. Request erasure
    req = await erasure_mgr.request_erasure(sample_org, "privacy-officer", "GDPR Article 17 Erasure")
    assert req.status == ErasureStatus.REQUESTED
    assert req.org_id == sample_org

    # 2. Execute erasure
    completed_req = await erasure_mgr.execute_erasure(req.id)
    assert completed_req.status == ErasureStatus.COMPLETED
    assert completed_req.verification_status == "VERIFIED_ZERO_RESIDUE"
    assert completed_req.completed_at is not None

    # 3. Invariant: 0 residual rows in erased tables
    async with sqlite_engine.raw.connect() as conn:
        rows = (await conn.execute(select(incidents).where(incidents.c.org_id == sample_org))).fetchall()
        assert len(rows) == 0


@pytest.mark.asyncio
async def test_erasure_blocked_by_active_legal_hold(sqlite_engine: DatabaseEngine, sample_org: str):
    erasure_mgr = DataErasureManager(sqlite_engine)
    hold_mgr = LegalHoldManager(sqlite_engine)

    # Place legal hold
    await hold_mgr.create_hold(sample_org, "ALL", "Regulatory Investigation", "compliance-team")

    # Insert incident
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(incidents).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                incident_type="FINANCIAL",
                severity="HIGH",
                siem_event_type="ALERT",
                description="Held financial incident",
                evidence_hash="hash-88",
                status="OPEN",
                created_at="2026-09-12T00:00:00Z",
            )
        )

    # Request and execute erasure
    req = await erasure_mgr.request_erasure(sample_org, "privacy-officer", "Customer requested delete")
    result = await erasure_mgr.execute_erasure(req.id)

    # Invariant: Must transition to BLOCKED_BY_HOLD, NOT COMPLETED!
    assert result.status == ErasureStatus.BLOCKED_BY_HOLD
    assert result.completed_at is None

    # Invariant: Held data MUST NOT be erased
    async with sqlite_engine.raw.connect() as conn:
        rows = (await conn.execute(select(incidents).where(incidents.c.org_id == sample_org))).fetchall()
        assert len(rows) == 1
