# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent PR224 counterexamples; original historical assertions are untouched."""

import json

import pytest
from sqlalchemy import insert

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
)
from responsibleai.db.engine import create_engine, restore_reconciliation_records
from responsibleai.isolation import in_flight


@pytest.mark.asyncio
async def test_cached_database_check_cannot_authorize_later_synchronous_admission():
    engine = create_engine(":memory:")
    await engine.init()
    try:
        gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.READY,
            provider=InMemoryLifecycleStateProvider(),
            db_engine=engine,
        )
        await gate.assert_current_traffic_admitted()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(restore_reconciliation_records).values(
                    id="after-startup",
                    restored_at="2026-10-20T00:00:00Z",
                    status="CONTAINMENT_PENDING",
                    reconciled_by="independent-negative",
                )
            )
        # No asynchronous refresh between the committed marker and this call.
        with pytest.raises(RestoreQuarantineError):
            gate.assert_traffic_admitted()
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
        assert gate.state == RestoreReadinessState.FAILED
    finally:
        await engine.close()


@pytest.mark.parametrize("foreign_v2_name", [False, True])
def test_corrupt_record_cannot_be_suppressed_by_unverified_filename(
    foreign_v2_name, tmp_path, monkeypatch
):
    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    name = (
        in_flight._tracking_filename("tenant-b", "execution")
        if foreign_v2_name
        else "unattributed_worker.json"
    )
    (tmp_path / name).write_text("{", encoding="utf-8")
    assert in_flight._check_remote_worker_active("tenant-a")
    assert (tmp_path / name).exists()


def test_validated_foreign_registration_does_not_quarantine_another_tenant(tmp_path, monkeypatch):
    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    entry = in_flight.InFlightExecution(
        execution_id="execution",
        organization_id="tenant-b",
        action_id="negative-control",
        authorization_id=None,
        task=None,
        terminate_callback=None,
        created_at=0.0,
    )
    in_flight._record_cross_worker_registration(entry)
    assert in_flight._check_remote_worker_active("tenant-a") == []
    records = list(tmp_path.glob("*.json"))
    assert len(records) == 1
    assert json.loads(records[0].read_text())["organization_id"] == "tenant-b"


def test_exact_unicode_tenant_identifiers_never_share_tracking_authority(tmp_path, monkeypatch):
    import unicodedata

    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    composed = "caf\u00e9"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert in_flight._tracking_filename(composed, "execution") != in_flight._tracking_filename(
        decomposed, "execution"
    )
    for organization in (composed, decomposed):
        entry = in_flight.InFlightExecution(
            execution_id="execution",
            organization_id=organization,
            action_id="identity-test",
            authorization_id=None,
            task=None,
            terminate_callback=None,
            created_at=0.0,
        )
        in_flight._record_cross_worker_registration(entry)
    records = list(tmp_path.glob("*.json"))
    assert len(records) == 2
    assert {json.loads(record.read_text())["organization_id"] for record in records} == {
        composed,
        decomposed,
    }
