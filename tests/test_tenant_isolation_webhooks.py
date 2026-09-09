# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reproduction test for ANT-P1-001: Cross-tenant isolation in webhook deliveries."""

from __future__ import annotations

import uuid

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.app import app, settings
from responsibleai.rbac.models import Role
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent


@pytest.fixture(autouse=True)
def _fake_dns(monkeypatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(
        "responsibleai.webhooks.manager.socket.getaddrinfo",
        lambda host, *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )


@pytest.mark.asyncio
async def test_cross_tenant_webhook_deliveries_isolation():
    async with LifespanManager(app, startup_timeout=15):
        org_repo = app_module._org_repo
        webhook_mgr = app_module._webhook_manager

        run_id = uuid.uuid4().hex[:8]

        # Create Org A and Org B
        org_a = await org_repo.create_org("Org A", f"org-a-wh-{run_id}")
        key_a, raw_key_a = await org_repo.create_key(org_a.id, "key-a", Role.ANALYST)

        org_b = await org_repo.create_org("Org B", f"org-b-wh-{run_id}")
        key_b, raw_key_b = await org_repo.create_key(org_b.id, "key-b", Role.ANALYST)

        # Register webhook for Org A
        wh_a = WebhookConfig(
            url=f"https://hooks.example.com/org-a-{run_id}",
            events=[WebhookEvent.DRIFT_ALERT],
            org_id=org_a.id,
        )
        webhook_mgr.register(wh_a)

        # Register webhook for Org B
        wh_b = WebhookConfig(
            url=f"https://hooks.example.com/org-b-{run_id}",
            events=[WebhookEvent.DRIFT_ALERT],
            org_id=org_b.id,
        )
        webhook_mgr.register(wh_b)

        # Fire event to deliver to both
        with respx.mock(assert_all_called=False) as mock:
            mock.post(f"https://hooks.example.com/org-a-{run_id}").mock(return_value=httpx.Response(200))
            mock.post(f"https://hooks.example.com/org-b-{run_id}").mock(return_value=httpx.Response(200))
            await webhook_mgr.fire(WebhookEvent.DRIFT_ALERT, {"metric": "drift", "value": 0.42})

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {raw_key_a}"}
            headers_b = {"Authorization": f"Bearer {raw_key_b}"}

            # Org A queries deliveries
            resp_a = await client.get("/api/webhooks/deliveries", headers=headers_a)
            assert resp_a.status_code == 200, resp_a.text
            data_a = resp_a.json()

            # Org A must only see Org A's delivery, NOT Org B's delivery
            ids_a = {delivery["webhook_id"] for delivery in data_a["deliveries"]}
            assert data_a["total"] == len(data_a["deliveries"])
            assert wh_a.id in ids_a
            assert wh_b.id not in ids_a
            assert all(delivery["org_id"] == org_a.id for delivery in data_a["deliveries"])

            # Org B queries deliveries
            resp_b = await client.get("/api/webhooks/deliveries", headers=headers_b)
            assert resp_b.status_code == 200, resp_b.text
            data_b = resp_b.json()

            # Org B must only see Org B's delivery
            ids_b = {delivery["webhook_id"] for delivery in data_b["deliveries"]}
            assert data_b["total"] == len(data_b["deliveries"])
            assert wh_b.id in ids_b
            assert wh_a.id not in ids_b
            assert all(delivery["org_id"] == org_b.id for delivery in data_b["deliveries"])
