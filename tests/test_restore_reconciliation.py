# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Restore Reconciliation Audit Records and Fail-Closed Behavior."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    organizations,
    restore_reconciliation_records,
    tenant_tombstones,
)


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.mark.asyncio
async def test_restore_reconciliation_audit_record_persisted(sqlite_engine: DatabaseEngine):
    engine_rec = RestoreReconciliationEngine(sqlite_engine)
    org_id = f"org-{uuid.uuid4().hex[:8]}"

    # Setup: tombstone exists
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Tombstoned Org Inc",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
        await conn.execute(
            insert(tenant_tombstones).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                original_name="Tombstoned Org Inc",
                generation_id="gen-reconcile-test",
                tombstoned_at="2026-09-11T00:00:00Z",
                tombstoned_by="admin-user",
                authority_hash="auth-hash-1",
                evidence_digest="ev-digest-1",
                details_json="{}",
            )
        )

    report = await engine_rec.reconcile_post_restore(reconciled_by="secops-reconciler")

    assert report.status == "RECONCILED"
    assert report.tombstones_detected == 1
    assert report.tenants_quarantined == 1

    # Verify audit record persisted in DB
    async with sqlite_engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(restore_reconciliation_records).where(
                    restore_reconciliation_records.c.id == report.id
                )
            )
        ).fetchone()

        assert row is not None
        assert row.status == "RECONCILED"
        assert row.reconciled_by == "secops-reconciler"
        assert row.tombstones_detected == 1
        assert row.tenants_quarantined == 1
        details = json.loads(row.details_json)
        assert org_id in details["quarantined_orgs"]


@pytest.mark.asyncio
async def test_restore_reconciliation_clean_no_tombstones(sqlite_engine: DatabaseEngine):
    engine_rec = RestoreReconciliationEngine(sqlite_engine)
    report = await engine_rec.reconcile_post_restore(reconciled_by="automated-sre")

    assert report.status == "RECONCILED"
    assert report.tombstones_detected == 0
    assert report.tenants_quarantined == 0


@pytest.mark.asyncio
async def test_restore_reconciliation_fail_closed_on_error(sqlite_engine: DatabaseEngine):
    engine_rec = RestoreReconciliationEngine(sqlite_engine)
    org_id = f"org-{uuid.uuid4().hex[:8]}"

    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(tenant_tombstones).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                original_name="Failed Org",
                generation_id="gen-fail-test",
                tombstoned_at="2026-09-11T00:00:00Z",
                tombstoned_by="admin-user",
                authority_hash="auth-1",
                evidence_digest="ev-1",
                details_json="{}",
            )
        )

    # Force an unhandled exception during the first begin() call to verify fail-closed
    class FaultyEngine:
        def __init__(self, real_engine: DatabaseEngine):
            self._real = real_engine
            self.calls = 0

        @property
        def raw(self):
            faulty = self
            real_raw = self._real.raw

            class FaultyRaw:
                def begin(self):
                    faulty.calls += 1
                    if faulty.calls == 1:
                        class BrokenBegin:
                            async def __aenter__(self):
                                raise RuntimeError("Database connection failure during reconciliation")

                            async def __aexit__(self, *args):
                                pass

                        return BrokenBegin()
                    return real_raw.begin()

                def connect(self):
                    return real_raw.connect()

            return FaultyRaw()

    faulty_engine = FaultyEngine(sqlite_engine)
    engine_rec._engine = faulty_engine  # type: ignore

    with pytest.raises(RestoreReconciliationError, match="Restore reconciliation aborted"):
        await engine_rec.reconcile_post_restore(reconciled_by="sre-agent")

    # Verify audit log caught the FAILED status
    async with sqlite_engine.raw.connect() as conn:
        records = (
            await conn.execute(
                select(restore_reconciliation_records).where(
                    restore_reconciliation_records.c.status == "FAILED"
                )
            )
        ).fetchall()
        assert len(records) >= 1
        assert "Database connection failure" in records[0].details_json
