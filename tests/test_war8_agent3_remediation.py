# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WAR-8 Agent 3 remediation: sovereign authz and tenant audit summaries."""

from __future__ import annotations

import asyncio

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select, update

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import WebIdentityRepository, create_engine
from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.engine import (
    organizations,
    sovereign_shadow_observations,
    web_memberships,
    web_users,
)
from responsibleai.incidents.logic import build_incident_record
from responsibleai.rbac.models import AuditEntry, Role
from responsibleai.sovereign.api_deps import bind_sovereign_engine, bind_web_identity_repository
from responsibleai.sovereign.router import router
from tests.org_http_fixtures import seed_org_with_key

BOOTSTRAP = {"Authorization": "Bearer bootstrap-test-key"}


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


async def _member(identities: WebIdentityRepository, slug: str, role: Role = Role.OWNER):
    user_id, verification = await identities.register(
        slug, f"{slug}@example.com", "Test-Password-42!"
    )
    assert await identities.verify_email(verification) is True
    org_id = await identities.attach_organization(user_id, name=slug, slug=slug, role=role)
    token, _csrf = await identities.create_session(user_id, org_id=org_id)
    return org_id, user_id, token


@pytest.fixture()
async def sovereign_app():
    engine = create_engine(":memory:")
    await engine.init()
    bind_sovereign_engine(engine)
    identities = WebIdentityRepository(engine)
    bind_web_identity_repository(identities)
    application = FastAPI()
    application.include_router(router)
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, engine, identities


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_anonymous_sovereign_get_rejected(sovereign_app) -> None:
    client, _, _ = sovereign_app
    for path in (
        "/api/sovereign/status",
        "/api/sovereign/capabilities",
        "/api/sovereign/authority/effective",
        "/api/sovereign/xray",
    ):
        res = await client.get(path)
        assert res.status_code == 401, path
        assert "traceback" not in res.text.lower()
        assert "sovereign_version" not in res.text


@pytest.mark.asyncio
async def test_anonymous_sovereign_post_rejected(sovereign_app) -> None:
    client, engine, _ = sovereign_app
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": "org-victim",
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
    )
    assert res.status_code == 401
    assert await _shadow_count(engine, "org-victim") == 0


@pytest.mark.asyncio
async def test_tenant_a_cannot_query_tenant_b_authority(sovereign_app) -> None:
    client, _, identities = sovereign_app
    _org_a, _user_a, token_a = await _member(identities, "war8-auth-a")
    org_b, _, _token_b = await _member(identities, "war8-auth-b")
    res = await client.get(
        "/api/sovereign/authority/effective",
        params={"organization_id": org_b},
        headers=_bearer(token_a),
    )
    assert res.status_code == 404
    assert org_b not in res.text


@pytest.mark.asyncio
async def test_tenant_a_cannot_query_tenant_b_xray(sovereign_app) -> None:
    client, _, identities = sovereign_app
    org_a, _user_a, token_a = await _member(identities, "war8-xray-a")
    org_b, _, _token_b = await _member(identities, "war8-xray-b")
    res = await client.get(
        "/api/sovereign/xray",
        params={"organization_id": org_b},
        headers=_bearer(token_a),
    )
    assert res.status_code == 404
    own = await client.get("/api/sovereign/xray", headers=_bearer(token_a))
    assert own.status_code == 200
    assert own.json()["graph"]["organization_id"] == org_a


@pytest.mark.asyncio
async def test_tenant_a_cannot_persist_tenant_b_shadow(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_a, _user_a, token_a = await _member(identities, "war8-shadow-a")
    org_b, _, _token_b = await _member(identities, "war8-shadow-b")
    before = await _shadow_count(engine, org_b)
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_b,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token_a),
    )
    assert res.status_code == 404
    assert await _shadow_count(engine, org_b) == before
    own = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_a,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token_a),
    )
    assert own.status_code == 200
    assert await _shadow_count(engine, org_a) == 1


@pytest.mark.asyncio
async def test_viewer_cannot_persist_shadow(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_id, _user_id, token = await _member(identities, "war8-viewer", role=Role.VIEWER)
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_id,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token),
    )
    assert res.status_code == 403
    assert await _shadow_count(engine, org_id) == 0
    assert "VIEWER" not in res.text


@pytest.mark.asyncio
async def test_revoked_membership_fails_before_shadow_write(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_id, user_id, token = await _member(identities, "war8-revoked")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == user_id, web_memberships.c.org_id == org_id)
            .values(status="REVOKED")
        )
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_id,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token),
    )
    assert res.status_code in {401, 403}
    assert await _shadow_count(engine, org_id) == 0


@pytest.mark.asyncio
async def test_disabled_user_fails_before_shadow_write(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_id, user_id, token = await _member(identities, "war8-disabled-user")
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(disabled=1))
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_id,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token),
    )
    assert res.status_code in {401, 403}
    assert await _shadow_count(engine, org_id) == 0


@pytest.mark.asyncio
async def test_disabled_org_fails_before_shadow_write(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_id, _user_id, token = await _member(identities, "war8-disabled-org")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status="DISABLED")
        )
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_id,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token),
    )
    assert res.status_code in {401, 403}
    assert await _shadow_count(engine, org_id) == 0


@pytest.mark.asyncio
async def test_suspended_org_fails_before_shadow_write(sovereign_app) -> None:
    client, engine, identities = sovereign_app
    org_id, _user_id, token = await _member(identities, "war8-suspended-org")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status="SUSPENDED")
        )
    res = await client.post(
        "/api/sovereign/shadow",
        json={
            "organization_id": org_id,
            "agent_id": "agent",
            "action_type": "read",
            "persist": True,
        },
        headers=_bearer(token),
    )
    assert res.status_code in {401, 403}
    assert await _shadow_count(engine, org_id) == 0
    assert org_id not in res.text


@pytest.mark.asyncio
async def test_endpoint_summary_is_org_scoped() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    repo = AuditRepository(engine)
    await repo.write(AuditEntry(endpoint="/api/war8/a-only", method="GET", org_id="org-a"))
    await repo.write(AuditEntry(endpoint="/api/war8/b-only", method="GET", org_id="org-b"))
    summary_a = await repo.endpoint_summary("org-a", days=1)
    summary_b = await repo.endpoint_summary("org-b", days=1)
    endpoints_a = {row["endpoint"] for row in summary_a}
    endpoints_b = {row["endpoint"] for row in summary_b}
    assert endpoints_a == {"/api/war8/a-only"}
    assert endpoints_b == {"/api/war8/b-only"}
    with pytest.raises(ValueError):
        await repo.endpoint_summary("", days=1)


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)


@pytest.fixture(autouse=True)
def _reset_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def dashboard():
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client


async def _drain_audit() -> None:
    pending = list(app_module._pending_audit_writes)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.mark.asyncio
async def test_audit_summary_excludes_other_tenant(dashboard: AsyncClient) -> None:
    org_a, _key_id_a, raw_a = await seed_org_with_key(
        name="War8 Summary A",
        slug="war8-summary-a",
        key_name="analyst",
        role=Role.ANALYST,
    )
    org_b, _key_id_b, raw_b = await seed_org_with_key(
        name="War8 Summary B",
        slug="war8-summary-b",
        key_name="analyst",
        role=Role.ANALYST,
    )
    repo = app_module._audit_repo
    assert repo is not None
    await repo.write(AuditEntry(endpoint="/api/war8/summary-a", method="GET", org_id=org_a))
    await repo.write(AuditEntry(endpoint="/api/war8/summary-b", method="GET", org_id=org_b))
    left = await dashboard.get("/api/audit/summary", headers={"Authorization": f"Bearer {raw_a}"})
    right = await dashboard.get("/api/audit/summary", headers={"Authorization": f"Bearer {raw_b}"})
    assert left.status_code == 200
    assert right.status_code == 200
    left_paths = {row["endpoint"] for row in left.json()["endpoints"]}
    right_paths = {row["endpoint"] for row in right.json()["endpoints"]}
    assert "/api/war8/summary-a" in left_paths
    assert "/api/war8/summary-b" not in left_paths
    assert "/api/war8/summary-b" in right_paths
    assert "/api/war8/summary-a" not in right_paths


@pytest.mark.asyncio
async def test_audit_org_id_tamper_and_legacy_bypass_fail(dashboard: AsyncClient) -> None:
    org_b, _key_id, raw_b = await seed_org_with_key(
        name="War8 Tamper B",
        slug="war8-tamper-b",
        key_name="analyst",
        role=Role.ANALYST,
    )
    org_a, _key_id_a, raw_a = await seed_org_with_key(
        name="War8 Tamper A",
        slug="war8-tamper-a",
        key_name="analyst",
        role=Role.ANALYST,
    )
    repo = app_module._audit_repo
    assert repo is not None
    await repo.write(AuditEntry(endpoint="/api/war8/tamper-b", method="GET", org_id=org_b))
    tamper = await dashboard.get(
        "/api/audit/summary",
        params={"org_id": org_b},
        headers={"Authorization": f"Bearer {raw_a}"},
    )
    assert tamper.status_code == 404
    assert "/api/war8/tamper-b" not in tamper.text
    # Static legacy keys are VIEWER and have no organization. They must not
    # select another tenant or receive a global audit dump.
    legacy_log = await dashboard.get("/api/audit-log", params={"org_id": org_b}, headers=BOOTSTRAP)
    assert legacy_log.status_code == 403
    assert "/api/war8/tamper-b" not in legacy_log.text
    assert org_b not in legacy_log.text
    legacy_summary = await dashboard.get(
        "/api/audit/summary", params={"org_id": org_b}, headers=BOOTSTRAP
    )
    assert legacy_summary.status_code == 404
    assert "/api/war8/tamper-b" not in legacy_summary.text
    unscoped = await dashboard.get("/api/audit/summary", headers=BOOTSTRAP)
    assert unscoped.status_code == 200
    assert "/api/war8/tamper-b" not in {row["endpoint"] for row in unscoped.json()["endpoints"]}
    legacy_audit = await dashboard.get("/api/audit", params={"org_id": org_b}, headers=BOOTSTRAP)
    assert legacy_audit.status_code == 403
    assert "/api/war8/tamper-b" not in legacy_audit.text
    verify = await dashboard.get(
        "/api/audit/verify",
        headers={"Authorization": f"Bearer {raw_b}"},
    )
    assert verify.status_code == 403
    incident = build_incident_record(description="war8-tenant-b-incident-marker")
    assert app_module._incident_repo is not None
    await app_module._incident_repo.create(incident, org_id=org_b)
    incident_tamper = await dashboard.get(
        "/api/incidents",
        params={"org_id": org_b},
        headers={"Authorization": f"Bearer {raw_a}"},
    )
    assert incident_tamper.status_code == 404
    assert "war8-tenant-b-incident-marker" not in incident_tamper.text
    incident_legacy = await dashboard.get(
        "/api/incidents", params={"org_id": org_b}, headers=BOOTSTRAP
    )
    assert incident_legacy.status_code == 200
    assert incident_legacy.json()["incidents"] == []
    await _drain_audit()
