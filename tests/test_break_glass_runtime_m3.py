# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""P1-05 — break-glass delegation revocation is reachable and admin-gated."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.rbac.models import Role
from tests.org_http_fixtures import seed_org_with_key

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


async def _add_org_key(org_id: str, name: str, role: Role) -> str:
    from responsibleai.dashboard.app import _org_repo

    _rec, raw = await _org_repo.create_key(org_id, name, role, internal_unverified_fixture=True)
    return raw


@pytest.mark.asyncio
async def test_break_glass_revoke_requires_admin(client: AsyncClient) -> None:
    org_id, _kid, admin_raw = await seed_org_with_key(
        name="Break Glass Co", slug="break-glass-co", key_name="admin", role=Role.ADMIN
    )
    analyst_raw = await _add_org_key(org_id, "analyst", Role.ANALYST)
    denied = await client.post(
        "/api/governance/delegations/agent-99/revoke",
        headers={"Authorization": f"Bearer {analyst_raw}"},
        json={"reason": "break-glass drill"},
    )
    assert denied.status_code == 403
    ok = await client.post(
        "/api/governance/delegations/agent-99/revoke",
        headers={"Authorization": f"Bearer {admin_raw}"},
        json={"reason": "break-glass drill"},
    )
    assert ok.status_code in (200, 404)
