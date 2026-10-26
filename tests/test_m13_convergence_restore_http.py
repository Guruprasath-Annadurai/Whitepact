# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Public recovery must not authorize global restore admission; real HTTP/PG."""

import secrets

import httpx
import pytest
from asgi_lifespan import LifespanManager

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance import backup_defense
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["/api/restore/reconcile", "/api/v1/restore/reconcile"])
async def test_public_restore_cannot_clear_quarantine_without_qualified_authority(
    monkeypatch, route
):
    databases = isolated_pg_url("wp_convergence_restore_http")
    database = await anext(databases)
    await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
    monkeypatch.setattr(dashboard.settings, "database_url", database)
    monkeypatch.setattr(dashboard.settings, "auto_migrate", False)
    monkeypatch.setattr(dashboard.settings, "auth_enabled", True)
    monkeypatch.setattr(dashboard.settings, "api_keys", [secrets.token_urlsafe(32)])
    monkeypatch.setattr(dashboard.settings, "environment", "development")
    gate = backup_defense.RestoreReadinessGate(backup_defense.RestoreReadinessState.RESTORE_PENDING)
    monkeypatch.setattr(backup_defense, "_GLOBAL_RESTORE_GATE", gate)
    try:
        async with LifespanManager(dashboard.app) as manager:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=manager.app), base_url="http://test"
            ) as client:
                response = await client.post(route, json={})
                assert response.status_code == 503, response.text
                assert response.json()["error"] == "RESTORE_SECURITY_QUALIFICATION_REQUIRED"
                assert gate.state == backup_defense.RestoreReadinessState.RESTORE_PENDING
                status = await client.get("/api/restore/status")
                assert status.status_code == 200
                assert status.json()["is_admitted"] is False
    finally:
        await databases.aclose()
