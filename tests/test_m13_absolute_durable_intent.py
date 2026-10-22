# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real storage unit evidence; SQLite is not PostgreSQL/native qualification."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import OperationalError

from responsibleai.db.containment_repository import (
    ContainmentAdmissionError,
    ContainmentGenerationConflictError,
    ContainmentRepository,
)
from responsibleai.db.engine import create_engine, organizations, runtime_containment_records


@pytest.fixture
async def journal(tmp_path):
    engine = create_engine(str(tmp_path / "independent-journal.db"))
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant",
                name="Tenant",
                slug="tenant",
                governance_status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    try:
        yield ContainmentRepository(engine), engine
    finally:
        await engine.close()


async def begin(repository, *, execution="execution", generation="original", tenant="tenant"):
    await repository.begin(
        execution_id=execution,
        organization_id=tenant,
        owner_generation=generation,
        backend_identity="daemon-identity",
        authorization_id="grant",
        action_digest="a" * 64,
        admission_epoch=4,
        expected_container_name="unique-owned-name",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["PREPARING", "ACTIVE", "UNRESOLVED"])
async def test_new_process_cannot_ignore_intent_after_all_local_files_are_lost(
    journal, state, tmp_path
):
    repository, engine = journal
    await begin(repository)
    if state == "ACTIVE":
        await repository.acknowledge("execution", "original", "c" * 64)
    elif state == "UNRESOLVED":
        await repository.mark_unresolved("execution", "original")
    # Empty tracking is explicitly NOT containment proof. A fresh repository
    # instance represents a restarted process, not a cached Python gate.
    restarted = ContainmentRepository(engine)
    with pytest.raises(ContainmentAdmissionError):
        await restarted.assert_admitted(owner_generation="restarted")
    with pytest.raises(ContainmentAdmissionError):
        await begin(restarted, execution="another", generation="restarted")
    async with engine.raw.connect() as conn:
        assert await conn.scalar(select(runtime_containment_records.c.state)) == state


@pytest.mark.asyncio
async def test_unknown_creation_cannot_be_marked_contained(journal):
    repository, _ = journal
    await begin(repository)
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.finish("execution", "original")
    await repository.mark_unresolved("execution", "original")
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.finish("execution", "original")


@pytest.mark.asyncio
async def test_immutable_receipt_and_exact_generation_are_enforced(journal):
    repository, engine = journal
    await begin(repository)
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.acknowledge("execution", "wrong", "c" * 64)
    await repository.acknowledge("execution", "original", "c" * 64)
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.acknowledge("execution", "original", "d" * 64)
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.finish("execution", "wrong")
    await repository.finish("execution", "original")
    await ContainmentRepository(engine).assert_admitted(owner_generation="restarted")
    with pytest.raises(ContainmentGenerationConflictError):
        await repository.mark_unresolved("execution", "original")


@pytest.mark.asyncio
async def test_organization_must_exist_and_remain_active(journal):
    repository, engine = journal
    with pytest.raises(ContainmentAdmissionError):
        await begin(repository, tenant="invented")
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.update()
            .where(organizations.c.id == "tenant")
            .values(governance_status="SUSPENDED")
        )
    with pytest.raises(ContainmentAdmissionError):
        await begin(repository)


@pytest.mark.asyncio
async def test_storage_failure_is_not_empty_success(journal):
    repository, engine = journal
    async with engine.raw.begin() as conn:
        await conn.run_sync(runtime_containment_records.drop)
    with pytest.raises(OperationalError):
        await repository.assert_admitted(owner_generation="new")


@pytest.mark.asyncio
async def test_normal_ready_gate_rechecks_journal_on_cold_restart(journal, monkeypatch):
    from responsibleai.data_governance.backup_defense import (
        RestoreQuarantineError,
        RestoreReadinessGate,
        RestoreReadinessState,
    )
    from responsibleai.isolation import durable_intent

    repository, engine = journal
    await begin(repository)
    monkeypatch.setattr(durable_intent, "process_generation", lambda: "restarted")
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.READY, db_engine=engine)
    with pytest.raises(RestoreQuarantineError):
        await gate.assert_current_traffic_admitted()
    assert gate.state == RestoreReadinessState.FAILED


@pytest.mark.asyncio
async def test_revocation_between_creation_and_start_is_rechecked(journal):
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

    repository, engine = journal
    epochs = RevocationEpochRepository(engine)
    for _ in range(4):
        await epochs.bump("tenant")
    await begin(repository)
    await repository.acknowledge("execution", "original", "c" * 64)
    await repository.assert_startable("execution", "original", "c" * 64)
    await epochs.bump("tenant")
    with pytest.raises(ContainmentAdmissionError):
        await repository.assert_startable("execution", "original", "c" * 64)
