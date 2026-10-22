# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Owner-source review only; explicitly run against Recovery Zero, not candidate tests."""

import subprocess

import pytest
from sqlalchemy import insert

from responsibleai.data_governance import backup_defense
from responsibleai.db.engine import create_engine, restore_reconciliation_records
from responsibleai.isolation import in_flight


@pytest.mark.asyncio
async def test_recovery_name_without_identity_must_not_authorize_destructive_cleanup(monkeypatch):
    calls = []

    def docker(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="exited false", stderr="")

    monkeypatch.setattr(in_flight.shutil, "which", lambda command: "/controlled/docker")
    monkeypatch.setattr(subprocess, "run", docker)
    confirmed = await in_flight.verify_authoritative_container_containment("foreign-tenant-container")
    assert not any(command[1:3] == ["rm", "-f"] for command in calls), (
        "An unqualified name is not proof of tenant/execution container ownership"
    )
    assert not confirmed


@pytest.mark.parametrize("filename", ["corrupted.json", "unattributed.json"])
def test_unreadable_unknown_tracking_must_not_admit_a_specific_tenant(monkeypatch, tmp_path, filename):
    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    (tmp_path / filename).write_text("{", encoding="utf-8")
    assert in_flight._check_remote_worker_active("customer"), (
        "Unreadable tracking cannot prove that unknown execution authority belongs to another tenant"
    )


@pytest.mark.asyncio
async def test_marker_written_after_startup_cannot_use_cached_ready_authority():
    engine = create_engine(":memory:")
    await engine.init()
    try:
        gate = backup_defense.RestoreReadinessGate(
            initial_state=backup_defense.RestoreReadinessState.READY,
            provider=backup_defense.InMemoryLifecycleStateProvider(),
            db_engine=engine,
        )
        await gate.check_database_authority()
        async with engine.raw.begin() as connection:
            await connection.execute(insert(restore_reconciliation_records).values(
                id="independent-pending", restored_at="2026-10-19T12:00:00Z",
                status="CONTAINMENT_PENDING", reconciled_by="independent-test",
            ))
        # Production admission is synchronous and must not reuse a startup-only
        # DB result after durable authority changes. No container is executed.
        with pytest.raises(backup_defense.RestoreQuarantineError):
            gate.assert_traffic_admitted()
    finally:
        await engine.close()
