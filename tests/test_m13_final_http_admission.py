# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual ASGI admission must consult a marker committed after startup."""

import httpx
import pytest
from sqlalchemy import insert
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from responsibleai.dashboard.middleware import RestoreReadinessMiddleware
from responsibleai.data_governance import backup_defense
from responsibleai.db.engine import restore_reconciliation_records
from tests.test_m13_final_admission import admission_engine as admission_engine


@pytest.mark.asyncio
async def test_http_cannot_reuse_startup_ready_after_durable_pending_marker(
    monkeypatch, admission_engine
):
    engine = admission_engine
    gate = backup_defense.RestoreReadinessGate(
        initial_state=backup_defense.RestoreReadinessState.READY,
        provider=backup_defense.InMemoryLifecycleStateProvider(),
        db_engine=engine,
    )
    monkeypatch.setattr(backup_defense, "_GLOBAL_RESTORE_GATE", gate)
    dispatched = []

    async def endpoint(request):
        dispatched.append(request.url.path)
        return JSONResponse({"dispatched": True})

    app = Starlette(routes=[Route("/customer-mutation", endpoint, methods=["POST"])])
    app.add_middleware(RestoreReadinessMiddleware)
    try:
        await gate.check_database_authority()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            assert (await client.post("/customer-mutation")).status_code == 200
            async with engine.raw.begin() as connection:
                await connection.execute(
                    insert(restore_reconciliation_records).values(
                        id="pending",
                        restored_at="2026-10-19T12:00:00Z",
                        status="CONTAINMENT_PENDING",
                        reconciled_by="independent-test",
                    )
                )
            response = await client.post("/customer-mutation")
            assert response.status_code == 503
            assert dispatched == ["/customer-mutation"]
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_read_only_restore_status_reports_live_pending_marker(monkeypatch, admission_engine):
    from responsibleai.dashboard.app import restore_status

    engine = admission_engine
    gate = backup_defense.RestoreReadinessGate(
        initial_state=backup_defense.RestoreReadinessState.READY,
        provider=backup_defense.InMemoryLifecycleStateProvider(),
        db_engine=engine,
    )
    monkeypatch.setattr(backup_defense, "_GLOBAL_RESTORE_GATE", gate)
    await gate.check_database_authority()
    async with engine.raw.begin() as connection:
        await connection.execute(
            insert(restore_reconciliation_records).values(
                id="pending",
                restored_at="2026-10-19T12:00:00Z",
                status="CONTAINMENT_PENDING",
                reconciled_by="independent-test",
            )
        )
    response = await restore_status()
    assert b'"is_admitted":false' in response.body
