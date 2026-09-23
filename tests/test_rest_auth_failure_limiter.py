# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""REST dashboard failed-auth throttling (PR #93), on the RC tree."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings
from responsibleai.dashboard.middleware import MAX_REQUEST_BODY_BYTES
from responsibleai.rbac.models import Role


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    _auth_failure_limiter._failures.clear()
    yield
    _auth_failure_limiter._failures.clear()


@pytest.mark.asyncio
async def test_valid_key_is_never_blocked() -> None:
    async with LifespanManager(app, startup_timeout=15):
        org = await app_module._org_repo.create_org("Limiter Co", "limiter-co")
        _key, raw = await app_module._org_repo.create_key(org.id, "owner", Role.OWNER)
        headers = {"Authorization": f"Bearer {raw}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(30):
                response = await client.get(f"/api/orgs/{org.id}", headers=headers)
                assert response.status_code == 200


@pytest.mark.asyncio
async def test_repeated_invalid_keys_eventually_get_429() -> None:
    async with LifespanManager(app, startup_timeout=15):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            last_status = None
            for i in range(25):
                response = await client.get(
                    "/api/orgs", headers={"Authorization": f"Bearer guess-{i}"}
                )
                last_status = response.status_code
            assert last_status == 429


@pytest.mark.asyncio
async def test_missing_authorization_header_also_counts_as_a_failure() -> None:
    async with LifespanManager(app, startup_timeout=15):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = None
            for _ in range(25):
                response = await client.get("/api/orgs")
            assert response is not None
            assert response.status_code == 429


@pytest.mark.asyncio
async def test_blocked_ip_cannot_use_even_a_valid_key() -> None:
    async with LifespanManager(app, startup_timeout=15):
        org = await app_module._org_repo.create_org("Blocked Co", "blocked-co")
        _key, raw = await app_module._org_repo.create_key(org.id, "owner", Role.OWNER)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for i in range(20):
                await client.get("/api/orgs", headers={"Authorization": f"Bearer guess-{i}"})
            response = await client.get(
                f"/api/orgs/{org.id}", headers={"Authorization": f"Bearer {raw}"}
            )
            assert response.status_code == 429


@pytest.mark.asyncio
async def test_dev_mode_auth_disabled_bypasses_the_limiter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "auth_enabled", False)
    async with LifespanManager(app, startup_timeout=15):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = None
            for _ in range(25):
                response = await client.get("/api/orgs")
            assert response is not None
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_oversized_content_length_is_rejected() -> None:
    async with LifespanManager(app, startup_timeout=15):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/orgs",
                content=b"{}",
                headers={
                    "Authorization": "Bearer bootstrap-test-key",
                    "Content-Type": "application/json",
                    "Content-Length": str(MAX_REQUEST_BODY_BYTES + 1),
                },
            )
            assert response.status_code == 413
            assert response.json()["error"] == "payload_too_large"
