# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP SSE credential binding; fixture protocol test, not customer authority."""

import asyncio
import json

import httpx
import pytest
from asgi_lifespan import LifespanManager

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.db import OrgRepository
from responsibleai.mcp.tools import TOOL_DEFS
from responsibleai.rbac.models import Role
from tests.test_stage3_controller_postgres import controller as controller

pytest_plugins = ["tests.test_mcp_wave1_compatibility"]


@pytest.fixture
async def governed_app_with_key(controller, monkeypatch, seed_runtime_authority):
    """Real provisioned protocol identities, not paid entitlement/customer acceptance."""
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.server import _build_http_app

    service, _, _, token, csrf = controller
    tenant = await service.create(
        session_token=token, csrf=csrf, request_id="sse-own", name="SSE Own", slug="sse-own"
    )
    other = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="sse-foreign",
        name="Foreign SSE",
        slug="foreign-sse",
    )
    repository = OrgRepository(service.engine)
    key, raw = await repository.create_key(tenant, "test-key", role=Role.ANALYST)
    _, foreign = await repository.create_key(other, "foreign", role=Role.ADMIN)
    names = tuple(definition.name for definition in TOOL_DEFS)
    await seed_runtime_authority(
        service.engine,
        organization_id=tenant,
        principal_id=key.id,
        action_types=names,
        targets=names,
    )
    monkeypatch.setattr(get_settings(), "mcp_governance_enabled", True)
    monkeypatch.setattr(db_module, "create_engine", lambda _url: service.engine)
    monkeypatch.setattr(service.engine, "sse_fixture_foreign_key", foreign, raising=False)
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(
        RestoreReadinessGate(provider=service.provider, db_engine=service.engine)
    )
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(service.provider.path))
    monkeypatch.setenv("WHITEPACT_STORE_B_KEY", service.provider._secret_key)
    try:
        async with LifespanManager(_build_http_app()) as manager:
            yield manager.app, raw, tenant, service.engine, key.id
    finally:
        set_restore_readiness_gate(previous)


@pytest.mark.asyncio
async def test_real_sse_session_rejects_foreign_missing_and_revoked_credentials(tcp_mcp):
    origin, raw, org, engine, key_id = tcp_mcp
    repository = OrgRepository(engine)
    _, sibling_key = await repository.create_key(org, "sibling", role=Role.ADMIN)
    foreign_key = engine.sse_fixture_foreign_key
    headers = {"Authorization": f"Bearer {raw}"}
    async with asyncio.timeout(30), httpx.AsyncClient(base_url=origin, timeout=10) as client:
        async with client.stream("GET", "/sse", headers=headers) as events:
            assert events.status_code == 200
            lines = events.aiter_lines()

            async def data():
                async for line in lines:
                    if line.startswith("data:"):
                        return line[5:].strip()
                raise AssertionError("SSE closed before expected protocol message")

            endpoint = await data()
            assert endpoint.startswith("/messages/")
            initialized = await client.post(
                endpoint,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "APEX real TCP", "version": "1"},
                    },
                },
            )
            assert initialized.status_code == 202
            assert json.loads(await data())["id"] == 1
            notification = await client.post(
                endpoint,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                },
            )
            assert notification.status_code == 202
            ping = {"jsonrpc": "2.0", "id": 7, "method": "ping"}
            for token, expected in [
                (None, 401),
                ("invalid", 401),
                (foreign_key, 403),
                (sibling_key, 403),
            ]:
                response = await client.post(
                    endpoint,
                    headers={"Authorization": f"Bearer {token}"} if token else {},
                    json=ping,
                )
                assert response.status_code == expected
            assert (await client.post(endpoint, headers=headers, json=ping)).status_code == 202
            assert json.loads(await data())["id"] == 7
            assert await repository.revoke_key(key_id, org)
            assert (await client.post(endpoint, headers=headers, json=ping)).status_code == 401
