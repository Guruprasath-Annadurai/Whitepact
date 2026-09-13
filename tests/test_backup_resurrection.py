# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Backup Resurrection Defense & Restore Quarantine Invariants."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import RestoreReconciliationEngine
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    org_api_keys,
    organizations,
    tenant_tombstones,
    web_sessions,
    web_users,
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
                name="Resurrected Org Corp",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_backup_restore_quarantines_tombstoned_tenant(sqlite_engine: DatabaseEngine, sample_org: str):
    engine_rec = RestoreReconciliationEngine(sqlite_engine)

    # 1. Simulate prior durable tombstone registered in ledger before backup
    tombstone_id = str(uuid.uuid4())
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(tenant_tombstones).values(
                id=tombstone_id,
                org_id=sample_org,
                original_name="Resurrected Org Corp",
                generation_id="gen-prior-tombstone",
                tombstoned_at="2026-09-10T00:00:00Z",
                tombstoned_by="system-compliance",
                authority_hash="auth-hash-1",
                evidence_digest="ev-digest-1",
                details_json="{}",
            )
        )

        # 2. Simulate backup restore introducing resurrected user, session, and key for that tombstoned org
        user_id = str(uuid.uuid4())
        await conn.execute(
            insert(web_users).values(
                id=user_id,
                email="ghost@example.com",
                full_name="Ghost User",
                password_hash="hash-ghost",
                created_at="2026-08-01T00:00:00Z",
                updated_at="2026-08-01T00:00:00Z",
            )
        )
        await conn.execute(
            insert(web_sessions).values(
                token_hash="ghost-sess-hash",
                user_id=user_id,
                org_id=sample_org,
                csrf_hash="csrf-ghost",
                expires_at="2026-09-30T00:00:00Z",
                created_at="2026-08-01T00:00:00Z",
                last_seen_at="2026-08-01T00:00:00Z",
                revoked=0,
            )
        )
        await conn.execute(
            insert(org_api_keys).values(
                id=str(uuid.uuid4()),
                org_id=sample_org,
                key_hash="ghost-key-hash",
                name="Ghost Key",
                role="ADMIN",
                created_at="2026-08-01T00:00:00Z",
                revoked=0,
            )
        )

    # 3. Post-Restore Reconciliation runs
    report = await engine_rec.reconcile_post_restore(reconciled_by="sre-restore-agent")

    assert report.status == "RECONCILED"
    assert report.tombstones_detected == 1
    assert report.tenants_quarantined == 1
    assert sample_org in report.details["quarantined_orgs"]

    # 4. Invariant Verification: Resurrected credentials and sessions MUST BE REVOKED!
    async with sqlite_engine.raw.connect() as conn:
        s_rows = (await conn.execute(select(web_sessions).where(web_sessions.c.org_id == sample_org))).fetchall()
        assert len(s_rows) == 0

        k_rows = (await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == sample_org))).fetchall()
        assert len(k_rows) == 0

        # Invariant: Organization row marked as RESTORE_QUARANTINED
        org_row = (await conn.execute(select(organizations).where(organizations.c.id == sample_org))).fetchone()
        assert org_row is not None
        assert "RESTORE_QUARANTINED" in org_row.name
