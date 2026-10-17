# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP SSE credential binding; fixture protocol test, not customer authority."""

import asyncio
import json

import httpx
import pytest

from responsibleai.db import OrgRepository
from responsibleai.rbac.models import Plan, Role

pytest_plugins = ["tests.test_mcp_wave1_compatibility"]


@pytest.mark.asyncio
async def test_real_sse_session_rejects_foreign_missing_and_revoked_credentials(tcp_mcp):
    origin, raw, org, engine, key_id = tcp_mcp
    repository = OrgRepository(engine)
    _, sibling_key = await repository.create_key(org, "sibling", role=Role.ADMIN)
    foreign_org = await repository.create_org("Foreign SSE", "foreign-sse", plan=Plan.ENTERPRISE)
    _, foreign_key = await repository.create_key(foreign_org.id, "foreign", role=Role.ADMIN)
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
