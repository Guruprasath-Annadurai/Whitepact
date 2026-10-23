# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Ordinary read-contract regression; no bootstrap, delegation or agent mutation."""

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
async def inventory_client(monkeypatch, tmp_path):
    db_file = tmp_path / "inventory-read.db"
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
        ) as client:
            yield client


async def owner_session(email: str, slug: str) -> tuple[str, str]:
    engine = get_enterprise_engine()
    identities = WebIdentityRepository(engine)
    user_id, verification = await identities.register(
        "Inventory Owner", email, "StrongPassword123!@#"
    )
    await identities.verify_email(verification)
    organization = await EnterpriseIAM(engine).create_workspace(
        actor_user_id=user_id, name="Inventory Workspace", slug=slug, kind="ORGANIZATION"
    )
    org_id = organization["id"]
    token, _csrf = await identities.create_session(user_id, org_id=org_id)
    return org_id, token


@pytest.mark.asyncio
async def test_customer_agent_read_is_tenant_scoped_and_does_not_mutate_inventory(inventory_client):
    own_org, token = await owner_session("inventory.owner@example.com", "inventory-own")
    other_org, _ = await owner_session("inventory.other@example.com", "inventory-other")
    writes = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")):
            writes.append(statement)

    engine = get_enterprise_engine().raw.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        unauthenticated = await inventory_client.get(
            f"/api/enterprise/organizations/{own_org}/authority/agents"
        )
        assert unauthenticated.status_code == 401, unauthenticated.text
        inventory_client.cookies.set("wp_session", token)
        own = await inventory_client.get(
            f"/api/enterprise/organizations/{own_org}/authority/agents"
        )
        assert own.status_code == 200, own.text
        assert own.json() == {"agents": []}
        foreign = await inventory_client.get(
            f"/api/enterprise/organizations/{other_org}/authority/agents"
        )
        assert foreign.status_code == 403, foreign.text
        assert "agents" not in foreign.json()
        # Existing authentication/session and request-audit bookkeeping only.
        assert writes
        assert all(
            statement.upper().startswith(
                ("UPDATE WEB_SESSIONS SET LAST_SEEN_AT=", "INSERT INTO AUDIT_LOG (")
            )
            for statement in writes
        ), writes
    finally:
        event.remove(engine, "before_cursor_execute", capture)
