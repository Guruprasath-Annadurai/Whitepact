# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A hold committed after initial deletion validation must still prevent erasure."""

import asyncio

import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import LifecycleState
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.erasure import DataErasureManager, ErasureStatus
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from tests.test_m13_referenced_approval_deletion import _seed_execution
from tests.test_m13_referenced_approval_deletion import deletion_ready as deletion_ready


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["credentials", "operational", "tombstone"])
async def test_committed_hold_after_quarantine_prevents_operational_erasure(deletion_ready, phase):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="late-legal-hold",
        name="Late legal hold",
        slug="late-legal-hold",
    )
    async with service.engine.raw.begin() as connection:
        ids = await _seed_execution(connection, tenant, "late-hold", referenced=False)
    reached, release = asyncio.Event(), asyncio.Event()

    class Paused(TenantDeletionOrchestrator):
        async def pause(self, observed):
            if phase == observed:
                reached.set()
                await release.wait()

        async def _revoke_referenced_authority(self, *args, **kwargs):
            await self.pause("credentials")
            return await super()._revoke_referenced_authority(*args, **kwargs)

        async def _erase_operational_rows(self, *args, **kwargs):
            await self.pause("operational")
            return await super()._erase_operational_rows(*args, **kwargs)

        async def _register_tombstone(self, *args, **kwargs):
            await self.pause("tombstone")
            return await super()._register_tombstone(*args, **kwargs)

    operation = asyncio.create_task(
        Paused(service.engine, service.provider).delete_tenant(
            tenant, "test-controller", "hold-race"
        )
    )
    try:
        await asyncio.wait_for(reached.wait(), timeout=10)
        hold = await LegalHoldManager(service.engine).create_hold(
            tenant, "ALL", "Independent preservation mandate", "test-legal-owner"
        )
    finally:
        release.set()
    with pytest.raises(LegalHoldActiveError):
        await operation
    assert await LegalHoldManager(service.engine).is_held(tenant)
    assert hold.active
    assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
    async with service.engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM governance_approvals WHERE id=:id"),
                {"id": ids["approval_id"]},
            )
            # A hold is prospective: already committed erasure is not undone.
            == (0 if phase == "tombstone" else 1)
        )
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
            )
            == 0
        )


@pytest.mark.asyncio
async def test_erasure_rechecks_hold_committed_after_initial_lookup(deletion_ready, monkeypatch):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="late-erasure-hold",
        name="Late erasure hold",
        slug="late-erasure-hold",
    )
    async with service.engine.raw.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO incidents (id,org_id,incident_type,severity,siem_event_type,"
                "description,evidence_hash,status,created_at) VALUES "
                "('preserved-incident',:tenant,'POLICY_BREACH','HIGH','ALERT',"
                "'Must survive a committed hold','fixture-evidence','OPEN','2026-10-24T00:00:00Z')"
            ),
            {"tenant": tenant},
        )
    erasure = DataErasureManager(service.engine)
    request = await erasure.request_erasure(tenant, "test-privacy-owner", "test-erasure")
    reached, release = asyncio.Event(), asyncio.Event()
    original = erasure._legal_hold.is_held
    first = True

    async def pause_initial_read(*args, **kwargs):
        nonlocal first
        observed = await original(*args, **kwargs)
        if first:
            first = False
            assert observed is False
            reached.set()
            await release.wait()
        return observed

    monkeypatch.setattr(erasure._legal_hold, "is_held", pause_initial_read)
    operation = asyncio.create_task(erasure.execute_erasure(request.id))
    try:
        await asyncio.wait_for(reached.wait(), 10)
        await LegalHoldManager(service.engine).create_hold(
            tenant, "ALL", "Committed before erasure", "test-legal-owner"
        )
    finally:
        release.set()
    result = await operation
    assert result.status == ErasureStatus.BLOCKED_BY_HOLD
    assert result.completed_at is None
    assert result.verification_status == "BLOCKED_BY_HOLD"
    async with service.engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text(
                    "SELECT count(*) FROM incidents WHERE id='preserved-incident' AND org_id=:tenant"
                ),
                {"tenant": tenant},
            )
            == 1
        )
