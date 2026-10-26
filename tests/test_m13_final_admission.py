# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Live restore-marker admission contracts, with actual database transactions."""

from contextlib import aclosing

import pytest
from sqlalchemy import insert

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
)
from responsibleai.db.engine import create_engine, restore_reconciliation_records
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.fixture(params=["sqlite", "postgres"])
async def admission_engine(request):
    if request.param == "sqlite":
        engine = create_engine(":memory:")
        await engine.init()
        try:
            yield engine
        finally:
            await engine.close()
    else:
        async with aclosing(isolated_pg_url("wp_final_admission")) as databases:
            async for database in databases:
                await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
                engine = create_engine(database)
                try:
                    yield engine
                finally:
                    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["CONTAINMENT_PENDING", "FAILED", "RECONCILING"])
async def test_live_pending_marker_denies_after_clean_startup(status, admission_engine):
    engine = admission_engine
    try:
        gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.READY,
            provider=InMemoryLifecycleStateProvider(),
            db_engine=engine,
        )
        await gate.assert_current_traffic_admitted()
        async with engine.raw.begin() as connection:
            await connection.execute(
                insert(restore_reconciliation_records).values(
                    id="pending",
                    restored_at="2026-10-19T12:00:00Z",
                    status=status,
                    reconciled_by="independent-test",
                )
            )
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
        with pytest.raises(RestoreQuarantineError):
            gate.assert_traffic_admitted()
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_bound_database_failure_never_falls_back_to_cached_ready():
    engine = create_engine(":memory:")
    # Deliberately no schema: query failure must be a denial, not READY fallback.
    try:
        gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.READY,
            provider=InMemoryLifecycleStateProvider(),
            db_engine=engine,
        )
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
        assert gate.state == RestoreReadinessState.FAILED
    finally:
        await engine.close()
