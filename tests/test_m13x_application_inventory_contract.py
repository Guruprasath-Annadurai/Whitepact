# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-X Application inventory, ownership, and server-authoritative capability tests."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event

import responsibleai.dashboard.app as app_module
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.service import EnterpriseIAM


@pytest.fixture
async def client(monkeypatch, tmp_path):
    db_file = tmp_path / "m13x-apps.db"
    monkeypatch.setattr(app_module.settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(app_module.settings, "db_path", str(db_file))
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.settings, "api_keys", [])
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


async def create_owner_session(email: str, slug: str) -> tuple[str, str, str, str]:
    engine = get_enterprise_engine()
    identities = WebIdentityRepository(engine)
    user_id, verification = await identities.register(
        "Application Owner", email, "SecurePassword123!@#"
    )
    await identities.verify_email(verification)
    organization = await EnterpriseIAM(engine).create_workspace(
        actor_user_id=user_id, name="Test Organization", slug=slug, kind="ORGANIZATION"
    )
    org_id = organization["id"]
    token, csrf = await identities.create_session(user_id, org_id=org_id)
    return org_id, token, user_id, csrf


@pytest.mark.asyncio
async def test_application_lifecycle_and_tenant_boundary(client):
    own_org, own_token, own_user, own_csrf = await create_owner_session(
        "app.owner@example.com", "app-own"
    )
    other_org, other_token, _, other_csrf = await create_owner_session(
        "app.other@example.com", "app-other"
    )

    base = f"/api/enterprise/organizations/{own_org}/authority"

    # 1. Unauthenticated request denied
    unauth = await client.get(f"{base}/applications")
    assert unauth.status_code == 401

    # 2. Authenticated registration
    client.cookies.set("wp_session", own_token)
    client.cookies.set("wp_csrf", own_csrf)
    reg_resp = await client.post(
        f"{base}/applications",
        headers={"X-WP-CSRF": own_csrf},
        json={
            "name": "Customer Gateway App",
            "description": "Critical customer-facing LLM pipeline",
            "environment": "staging",
            "metadata": {"cluster": "us-east-1"},
        },
    )
    assert reg_resp.status_code == 200, reg_resp.text
    app_data = reg_resp.json()
    assert app_data["name"] == "Customer Gateway App"
    assert app_data["organization_id"] == own_org
    assert app_data["environment"] == "staging"
    assert app_data["lifecycle_state"] == "ACTIVE"
    assert app_data["has_execution_authority"] is False
    assert app_data["owner_user_id"] == own_user
    app_id = app_data["application_id"]

    # 3. List applications in own org
    list_resp = await client.get(f"{base}/applications")
    assert list_resp.status_code == 200
    apps = list_resp.json()["applications"]
    assert len(apps) == 1
    assert apps[0]["application_id"] == app_id
    assert apps[0]["agent_count"] == 0

    # 4. Cross-tenant access denied
    client.cookies.set("wp_session", other_token)
    client.cookies.set("wp_csrf", other_csrf)
    foreign_resp = await client.get(f"{base}/applications")
    assert foreign_resp.status_code == 403

    foreign_get = await client.get(f"{base}/applications/{app_id}")
    assert foreign_get.status_code == 403

    foreign_reg = await client.post(
        f"{base}/applications",
        headers={"X-WP-CSRF": other_csrf},
        json={"name": "Hacked App", "environment": "prod"},
    )
    assert foreign_reg.status_code == 403


@pytest.mark.asyncio
async def test_application_agent_association_and_cascading_disable(client):
    own_org, own_token, _, own_csrf = await create_owner_session(
        "assoc.owner@example.com", "assoc-own"
    )
    base = f"/api/enterprise/organizations/{own_org}/authority"
    client.cookies.set("wp_session", own_token)
    client.cookies.set("wp_csrf", own_csrf)

    # 1. Register application
    app_res = await client.post(
        f"{base}/applications",
        headers={"X-WP-CSRF": own_csrf},
        json={"name": "Finance Router", "environment": "production"},
    )
    assert app_res.status_code == 200
    app_id = app_res.json()["application_id"]

    # 2. Register agent associated with this application
    agent_res = await client.post(
        f"{base}/agents",
        headers={"X-WP-CSRF": own_csrf},
        json={
            "name": "Ledger Audit Agent",
            "framework": "langchain",
            "purpose": "Verify accounting records",
            "application_id": app_id,
        },
    )
    assert agent_res.status_code == 200, agent_res.text
    agent_data = agent_res.json()
    assert agent_data["application_id"] == app_id
    assert agent_data["has_delegated_authority"] is False
    agent_id = agent_data["agent_id"]

    # 3. Registering with non-existent or cross-tenant application fails
    bad_app = await client.post(
        f"{base}/agents",
        headers={"X-WP-CSRF": own_csrf},
        json={"name": "Bad Agent", "application_id": "app_nonexistent99"},
    )
    assert bad_app.status_code == 404

    # 4. Application get reflects associated agent
    get_res = await client.get(f"{base}/applications/{app_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert len(detail["agents"]) == 1
    assert detail["agents"][0]["agent_id"] == agent_id
    assert detail["agents"][0]["display_name"] == "Ledger Audit Agent"

    # 5. List applications reflects agent count
    list_res = await client.get(f"{base}/applications")
    assert list_res.status_code == 200
    assert list_res.json()["applications"][0]["agent_count"] == 1

    # 6. Disable application cascades to agents
    dis_res = await client.post(
        f"{base}/applications/{app_id}/disable",
        headers={"X-WP-CSRF": own_csrf},
        json={"reason": "Audit cycle completed"},
    )
    assert dis_res.status_code == 200
    assert dis_res.json()["status"] == "DISABLED"
    assert agent_id in dis_res.json()["disabled_agents"]

    # Verify agent is now DISABLED
    agents_res = await client.get(f"{base}/agents")
    assert agents_res.status_code == 200
    agent_list = agents_res.json()["agents"]
    assert agent_list[0]["lifecycle_state"] == "DISABLED"

    # Cannot register new agent under disabled application
    dis_reg = await client.post(
        f"{base}/agents",
        headers={"X-WP-CSRF": own_csrf},
        json={"name": "Post Disable Agent", "application_id": app_id},
    )
    assert dis_reg.status_code == 403


@pytest.mark.asyncio
async def test_server_authoritative_capabilities(client):
    own_org, own_token, _, own_csrf = await create_owner_session(
        "caps.owner@example.com", "caps-own"
    )
    base = f"/api/enterprise/organizations/{own_org}/authority"
    client.cookies.set("wp_session", own_token)
    client.cookies.set("wp_csrf", own_csrf)

    # 1. Register agent
    agent_res = await client.post(
        f"{base}/agents",
        headers={"X-WP-CSRF": own_csrf},
        json={"name": "Research Agent", "purpose": "Document retrieval"},
    )
    assert agent_res.status_code == 200, agent_res.text
    agent_id = agent_res.json()["agent_id"]

    # 2. Query capabilities: without root authority or delegation, capability is PENDING_DELEGATION
    caps_res = await client.get(f"{base}/agents/{agent_id}/capabilities")
    assert caps_res.status_code == 200
    caps = caps_res.json()["capabilities"]
    assert len(caps) >= 1
    assert caps[0]["agent_id"] == agent_id
    assert caps[0]["status"] == "PENDING_DELEGATION"
    assert caps[0]["authority_enforced"] is True

    # 3. Query all tenant capabilities
    all_caps = await client.get(f"{base}/capabilities")
    assert all_caps.status_code == 200
    assert len(all_caps.json()["capabilities"]) >= 1

    # 4. Safe read invariant: GET requests do not perform mutating database writes
    writes = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            writes.append(statement)

    engine = get_enterprise_engine().raw.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        read_res = await client.get(f"{base}/capabilities")
        assert read_res.status_code == 200
        # Only session activity/audit updates permitted, no mutations to authority state
        assert all(
            st.upper().startswith(
                ("UPDATE WEB_SESSIONS SET LAST_SEEN_AT=", "INSERT INTO AUDIT_LOG (")
            )
            for st in writes
        ), writes
    finally:
        event.remove(engine, "before_cursor_execute", capture)
