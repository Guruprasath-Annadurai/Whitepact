# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WAR-8 Agent 3 identity, RBAC, and tenant-isolation regressions.

DEFECT-WAR8-AG3-03 browser sovereign reads require a live principal.
DEFECT-WAR8-AG3-04 drift trends are bound to the authenticated tenant.
DEFECT-WAR8-AG3-05 browser and machine sovereign routes share one privilege policy.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select, update

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db.engine import (
    organizations,
    sovereign_shadow_observations,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.rbac.models import Role
from responsibleai.sovereign.api_deps import bind_sovereign_engine, bind_web_identity_repository
from responsibleai.sovereign.router import router
from responsibleai.sovereign.web_routes import web_router
from responsibleai.trust.score import TrustScoreEngine
from tests.org_http_fixtures import seed_org_with_key

_VIEW_PATHS = ("/api/web/sovereign/status", "/api/web/sovereign/capabilities")
_MACHINE_VIEW_PATHS = ("/api/sovereign/status", "/api/sovereign/capabilities")


async def _shadow_count(engine, org_id: str) -> int:
    async with engine.raw.connect() as conn:
        value = (
            await conn.execute(
                select(func.count())
                .select_from(sovereign_shadow_observations)
                .where(sovereign_shadow_observations.c.org_id == org_id)
            )
        ).scalar()
    return int(value or 0)


@pytest.fixture()
async def sovereign_web():
    from responsibleai.db import create_engine

    engine = create_engine(":memory:")
    await engine.init()
    bind_sovereign_engine(engine)
    identities = WebIdentityRepository(engine)
    bind_web_identity_repository(identities)
    application = FastAPI()
    application.include_router(router)
    application.include_router(web_router)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, engine, identities


async def _member(
    identities: WebIdentityRepository,
    slug: str,
    role: Role = Role.OWNER,
) -> tuple[str, str, str, str]:
    user_id, verification = await identities.register(
        slug, f"{slug}@example.com", "Test-Password-42!"
    )
    assert await identities.verify_email(verification) is True
    org_id = await identities.attach_organization(user_id, name=slug, slug=slug, role=role)
    token, csrf = await identities.create_session(user_id, org_id=org_id)
    return org_id, user_id, token, csrf


def _browser(client: AsyncClient, token: str, csrf: str) -> None:
    client.cookies.set("wp_session", token)
    client.cookies.set("wp_csrf", csrf)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_anonymous_web_sovereign_reads_denied(sovereign_web) -> None:
    client, _, _ = sovereign_web
    for path in _VIEW_PATHS:
        res = await client.get(path)
        assert res.status_code == 401, path
        assert "sovereign_version" not in res.text
        assert "traceback" not in res.text.lower()


@pytest.mark.asyncio
async def test_invalid_revoked_and_expired_sessions_denied(sovereign_web) -> None:
    client, engine, identities = sovereign_web
    _org_id, _user_id, token, csrf = await _member(identities, "session-live")
    _browser(client, "not-a-session", csrf)
    invalid = await client.get("/api/web/sovereign/status")
    assert invalid.status_code == 401

    _browser(client, token, csrf)
    await identities.revoke_session(token)
    revoked = await client.get("/api/web/sovereign/status")
    assert revoked.status_code == 401

    org_id, user_id, fresh, fresh_csrf = await _member(identities, "session-expired")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_sessions)
            .where(web_sessions.c.user_id == user_id, web_sessions.c.org_id == org_id)
            .values(expires_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat())
        )
    _browser(client, fresh, fresh_csrf)
    expired = await client.get("/api/web/sovereign/capabilities")
    assert expired.status_code == 401

    org_id, user_id, stale, stale_csrf = await _member(identities, "session-stale")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_sessions)
            .where(web_sessions.c.user_id == user_id, web_sessions.c.org_id == org_id)
            .values(inactivity_expires_at=(datetime.now(UTC) - timedelta(minutes=5)).isoformat())
        )
    _browser(client, stale, stale_csrf)
    idle = await client.get("/api/web/sovereign/status")
    assert idle.status_code == 401


@pytest.mark.asyncio
async def test_disabled_and_unverified_users_denied(sovereign_web) -> None:
    client, engine, identities = sovereign_web
    _org_id, user_id, token, csrf = await _member(identities, "user-disabled")
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(disabled=1))
    _browser(client, token, csrf)
    disabled = await client.get("/api/web/sovereign/status")
    assert disabled.status_code == 401

    org_id, user_id, token, csrf = await _member(identities, "user-unverified")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_users).where(web_users.c.id == user_id).values(email_verified_at=None)
        )
    _browser(client, token, csrf)
    unverified = await client.get("/api/web/sovereign/capabilities")
    assert unverified.status_code == 401
    assert org_id not in unverified.text


@pytest.mark.asyncio
async def test_revoked_and_invited_memberships_denied(sovereign_web) -> None:
    client, engine, identities = sovereign_web
    org_id, user_id, token, csrf = await _member(identities, "member-revoked")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == user_id, web_memberships.c.org_id == org_id)
            .values(status="REVOKED")
        )
    _browser(client, token, csrf)
    revoked = await client.get("/api/web/sovereign/status")
    assert revoked.status_code == 401

    org_id, user_id, token, csrf = await _member(identities, "member-invited")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == user_id, web_memberships.c.org_id == org_id)
            .values(status="INVITED")
        )
    _browser(client, token, csrf)
    invited = await client.get("/api/web/sovereign/capabilities")
    assert invited.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["DISABLED", "SUSPENDED", "DELETED"])
async def test_inactive_org_denied(sovereign_web, status: str) -> None:
    client, engine, identities = sovereign_web
    org_id, _user_id, token, csrf = await _member(identities, f"org-{status.lower()}")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status=status)
        )
    _browser(client, token, csrf)
    res = await client.get("/api/web/sovereign/status")
    assert res.status_code == 401
    assert org_id not in res.text


@pytest.mark.asyncio
async def test_deactivated_and_deleted_org_denied(sovereign_web) -> None:
    client, engine, identities = sovereign_web
    org_id, _user_id, token, csrf = await _member(identities, "org-deactivated")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(deactivated_at="2020-01-01T00:00:00+00:00")
        )
    _browser(client, token, csrf)
    deactivated = await client.get("/api/web/sovereign/status")
    assert deactivated.status_code == 401

    org_id, _user_id, token, csrf = await _member(identities, "org-deleted")
    async with engine.raw.begin() as conn:
        await conn.execute(delete(organizations).where(organizations.c.id == org_id))
    _browser(client, token, csrf)
    deleted = await client.get("/api/web/sovereign/capabilities")
    assert deleted.status_code == 401
    assert org_id not in deleted.text


@pytest.mark.asyncio
async def test_viewer_can_read_status_and_capabilities(sovereign_web) -> None:
    client, _, identities = sovereign_web
    _org_id, _user_id, token, csrf = await _member(identities, "viewer-read", role=Role.VIEWER)
    _browser(client, token, csrf)
    for path in _VIEW_PATHS:
        res = await client.get(path)
        assert res.status_code == 200, path
        assert "sovereign_version" in res.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.VIEWER, Role.DEVELOPER])
async def test_low_privilege_cannot_use_sovereign_operations(sovereign_web, role: Role) -> None:
    client, engine, identities = sovereign_web
    org_id, user_id, token, csrf = await _member(identities, f"low-{role.value.lower()}", role=role)
    _browser(client, token, csrf)
    web = await client.post(
        "/api/web/sovereign/xray",
        json={},
        headers={"X-WP-CSRF": csrf},
    )
    assert web.status_code == 403
    shadow = await client.post(
        "/api/web/sovereign/shadow",
        json={"agent_id": "agent", "action_type": "read", "persist": True},
        headers={"X-WP-CSRF": csrf},
    )
    assert shadow.status_code == 403
    assert await _shadow_count(engine, org_id) == 0
    machine = await client.get("/api/sovereign/xray", headers=_bearer(token))
    assert machine.status_code == 403
    for path in _MACHINE_VIEW_PATHS:
        allowed = await client.get(path, headers=_bearer(token))
        assert allowed.status_code == 200, path
    assert user_id


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [Role.SECURITY_ADMIN, Role.ADMIN, Role.OWNER])
async def test_privileged_roles_can_use_sovereign_xray(sovereign_web, role: Role) -> None:
    client, _, identities = sovereign_web
    org_id, user_id, token, csrf = await _member(
        identities, f"priv-{role.value.lower()}", role=role
    )
    _browser(client, token, csrf)
    web = await client.post(
        "/api/web/sovereign/xray",
        json={"principal_id": "forged-principal"},
        headers={"X-WP-CSRF": csrf},
    )
    assert web.status_code == 200
    assert web.json()["graph"]["organization_id"] == org_id
    assert "forged-principal" not in web.text
    machine = await client.post(
        "/api/sovereign/xray",
        json={"organization_id": org_id, "principal_id": "forged-principal"},
        headers=_bearer(token),
    )
    assert machine.status_code == 200
    assert machine.json()["graph"]["organization_id"] == org_id
    assert "forged-principal" not in machine.text


@pytest.mark.asyncio
async def test_browser_tenant_and_csrf_controls_remain(sovereign_web) -> None:
    client, engine, identities = sovereign_web
    org_id, _user_id, token, csrf = await _member(identities, "csrf-owner")
    _browser(client, token, csrf)
    missing = await client.post(
        "/api/web/sovereign/shadow",
        json={"agent_id": "agent", "action_type": "read", "persist": True},
    )
    assert missing.status_code == 403
    assert await _shadow_count(engine, org_id) == 0
    overridden = await client.get(
        "/api/web/sovereign/status",
        params={"organization_id": "other-org", "principal_id": "forged"},
    )
    assert overridden.status_code == 400
    header = await client.get(
        "/api/web/sovereign/capabilities",
        headers={"X-Organization-Id": "other-org"},
    )
    assert header.status_code == 400


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def drift_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


def _score(engine: TrustScoreEngine, level: float):
    return engine.compute(
        fairness=level,
        privacy=level,
        security=level,
        robustness=level,
        compliance=level,
        authenticity=level,
    )


@pytest.mark.asyncio
async def test_drift_is_tenant_bound_and_has_no_global_fallback(drift_client) -> None:
    client = drift_client
    org_a, _key_a, raw_a = await seed_org_with_key(
        name="Drift A", slug="drift-a", key_name="viewer-a", role=Role.VIEWER
    )
    org_b, _key_b, raw_b = await seed_org_with_key(
        name="Drift B", slug="drift-b", key_name="viewer-b", role=Role.VIEWER
    )
    scorer = TrustScoreEngine()
    repo = app_module._trust_repo
    assert repo is not None
    await repo.record("shared-model", "openai", _score(scorer, 0.95), org_id=org_a)
    await repo.record("shared-model", "openai", _score(scorer, 0.96), org_id=org_a)
    await repo.record("shared-model", "openai", _score(scorer, 0.10), org_id=org_b)
    await repo.record("shared-model", "openai", _score(scorer, 0.11), org_id=org_b)

    anon = await client.get("/api/drift/shared-model/openai")
    assert anon.status_code == 401
    assert "direction" not in anon.text

    legacy = await client.get(
        "/api/drift/shared-model/openai",
        params={"organization_id": org_b},
    )
    assert legacy.status_code == 401

    seen_a = await client.get(
        "/api/drift/shared-model/openai",
        headers=_bearer(raw_a),
        params={"organization_id": org_b, "org_id": org_b},
    )
    assert seen_a.status_code == 200
    body_a = seen_a.json()
    assert body_a["trend"]["latest"] > 80
    assert all(row["overall"] > 80 for row in body_a["recent_history"])

    seen_b = await client.get("/api/drift/shared-model/openai", headers=_bearer(raw_b))
    assert seen_b.status_code == 200
    body_b = seen_b.json()
    assert body_b["trend"]["latest"] < 30
    assert all(row["overall"] < 30 for row in body_b["recent_history"])
    assert body_a["trend"]["latest"] != body_b["trend"]["latest"]
