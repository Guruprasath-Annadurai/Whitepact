# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for tenant ownership on every /api/orgs/{org_id} route.

A role check is not a tenant check. These tests prove that an OWNER from
organization B cannot read or mutate organization A merely by supplying A's
UUID (or one of A's API-key IDs) in a path parameter.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings

_BOOTSTRAP = {"Authorization": "Bearer soc2-bootstrap-key"}


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["soc2-bootstrap-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield


@pytest.fixture
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


async def _make_org(client: AsyncClient, slug: str) -> tuple[str, str]:
    response = await client.post(
        "/api/orgs",
        json={"name": slug, "slug": slug},
        headers=_BOOTSTRAP,
    )
    assert response.status_code == 201, response.text
    org_id = response.json()["id"]

    response = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "owner", "role": "OWNER"},
        headers=_BOOTSTRAP,
    )
    assert response.status_code == 201, response.text
    return org_id, response.json()["key"]


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.mark.asyncio
async def test_all_org_scoped_routes_reject_cross_tenant_owner(client: AsyncClient) -> None:
    victim_org, victim_owner = await _make_org(client, "soc2-victim")
    _attacker_org, attacker_owner = await _make_org(client, "soc2-attacker")

    response = await client.post(
        f"/api/orgs/{victim_org}/keys",
        json={"name": "victim-secondary", "role": "ANALYST"},
        headers=_auth(victim_owner),
    )
    assert response.status_code == 201, response.text
    victim_key_id = response.json()["id"]

    attempts = [
        ("GET", f"/api/orgs/{victim_org}", None),
        ("DELETE", f"/api/orgs/{victim_org}", None),
        ("PUT", f"/api/orgs/{victim_org}/sso", {"sso_required": False}),
        ("PUT", f"/api/orgs/{victim_org}/mfa", {"mfa_required": False}),
        ("GET", f"/api/orgs/{victim_org}/authority-ceiling", None),
        ("PUT", f"/api/orgs/{victim_org}/authority-ceiling", {}),
        ("GET", f"/api/orgs/{victim_org}/autonomy-budget", None),
        (
            "PUT",
            f"/api/orgs/{victim_org}/autonomy-budget",
            {"max_autonomous_actions": 1, "window_minutes": 60},
        ),
        ("DELETE", f"/api/orgs/{victim_org}/autonomy-budget", None),
        (
            "POST",
            f"/api/orgs/{victim_org}/keys",
            {"name": "cross-tenant-key", "role": "VIEWER"},
        ),
        ("GET", f"/api/orgs/{victim_org}/keys", None),
        ("DELETE", f"/api/orgs/{victim_org}/keys/{victim_key_id}", None),
        ("POST", f"/api/orgs/{victim_org}/keys/{victim_key_id}/mfa/enroll", None),
        (
            "POST",
            f"/api/orgs/{victim_org}/keys/{victim_key_id}/mfa/verify",
            {"code": "000000"},
        ),
        ("DELETE", f"/api/orgs/{victim_org}/keys/{victim_key_id}/mfa", None),
    ]

    for method, url, payload in attempts:
        response = await client.request(
            method,
            url,
            json=payload,
            headers=_auth(attacker_owner),
        )
        assert response.status_code == 404, (method, url, response.status_code, response.text)
        assert victim_org not in response.text

    # The denied operations must not mutate the victim tenant.
    response = await client.get(f"/api/orgs/{victim_org}", headers=_auth(victim_owner))
    assert response.status_code == 200, response.text

    response = await client.get(
        f"/api/orgs/{victim_org}/keys",
        headers=_auth(victim_owner),
    )
    assert response.status_code == 200, response.text
    assert victim_key_id in {item["id"] for item in response.json()["keys"]}
