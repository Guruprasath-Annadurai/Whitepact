# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PR #93 tenant ownership on every /api/orgs/{org_id} route, on the RC tree.

Role is not tenancy. An OWNER of org B must not read or mutate org A by
putting A's UUID (or one of A's key IDs) in the path.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.rbac.models import Role


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["soc2-bootstrap-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield


@pytest.mark.asyncio
async def test_all_org_scoped_routes_reject_cross_tenant_owner() -> None:
    async with LifespanManager(app, startup_timeout=15):
        org_repo = app_module._org_repo
        victim = await org_repo.create_org("Victim", "soc2-victim")
        attacker = await org_repo.create_org("Attacker", "soc2-attacker")
        _victim_key, victim_raw = await org_repo.create_key(victim.id, "victim-owner", Role.OWNER)
        attacker_key, attacker_raw = await org_repo.create_key(
            attacker.id, "attacker-owner", Role.OWNER
        )
        extra, _extra_raw = await org_repo.create_key(victim.id, "victim-secondary", Role.ANALYST)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_attacker = {"Authorization": f"Bearer {attacker_raw}"}
            headers_victim = {"Authorization": f"Bearer {victim_raw}"}
            attempts = [
                ("GET", f"/api/orgs/{victim.id}", None),
                ("DELETE", f"/api/orgs/{victim.id}", None),
                ("PUT", f"/api/orgs/{victim.id}/sso", {"sso_required": False}),
                ("PUT", f"/api/orgs/{victim.id}/mfa", {"mfa_required": False}),
                ("GET", f"/api/orgs/{victim.id}/authority-ceiling", None),
                ("PUT", f"/api/orgs/{victim.id}/authority-ceiling", {}),
                ("GET", f"/api/orgs/{victim.id}/autonomy-budget", None),
                (
                    "PUT",
                    f"/api/orgs/{victim.id}/autonomy-budget",
                    {"max_autonomous_actions": 1, "window_minutes": 60},
                ),
                ("DELETE", f"/api/orgs/{victim.id}/autonomy-budget", None),
                (
                    "POST",
                    f"/api/orgs/{victim.id}/keys",
                    {"name": "cross-tenant-key", "role": "VIEWER"},
                ),
                ("GET", f"/api/orgs/{victim.id}/keys", None),
                ("DELETE", f"/api/orgs/{victim.id}/keys/{extra.id}", None),
                ("POST", f"/api/orgs/{victim.id}/keys/{extra.id}/mfa/enroll", None),
                (
                    "POST",
                    f"/api/orgs/{victim.id}/keys/{extra.id}/mfa/verify",
                    {"code": "000000"},
                ),
                ("DELETE", f"/api/orgs/{victim.id}/keys/{extra.id}/mfa", None),
            ]
            for method, url, payload in attempts:
                response = await client.request(method, url, json=payload, headers=headers_attacker)
                assert response.status_code == 404, (
                    method,
                    url,
                    response.status_code,
                    response.text,
                )
                assert victim.id not in response.text
                assert extra.id not in response.text

            response = await client.get(f"/api/orgs/{victim.id}", headers=headers_victim)
            assert response.status_code == 200, response.text
            response = await client.get(f"/api/orgs/{victim.id}/keys", headers=headers_victim)
            assert response.status_code == 200, response.text
            assert extra.id in {item["id"] for item in response.json()["keys"]}
            # Attacker must not have revoked the victim key by swapping path ids.
            still = await org_repo.get_key(extra.id)
            assert still is not None
            assert still.org_id == victim.id
            unused = attacker_key.id
            assert unused


@pytest.mark.asyncio
async def test_cannot_revoke_foreign_key_via_own_org_path() -> None:
    async with LifespanManager(app, startup_timeout=15):
        org_repo = app_module._org_repo
        org_a = await org_repo.create_org("A", "idor-a")
        org_b = await org_repo.create_org("B", "idor-b")
        _ka, raw_a = await org_repo.create_key(org_a.id, "a-owner", Role.OWNER)
        kb, _raw_b = await org_repo.create_key(org_b.id, "b-owner", Role.OWNER)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.delete(
                f"/api/orgs/{org_a.id}/keys/{kb.id}",
                headers={"Authorization": f"Bearer {raw_a}"},
            )
            assert response.status_code == 404
            assert kb.id not in response.text
        remaining = await org_repo.get_key(kb.id)
        assert remaining is not None
        assert remaining.org_id == org_b.id
