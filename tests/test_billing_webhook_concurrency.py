# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Stripe webhook: concurrent delivery, tenant isolation and bounded abuse (REC-37 verification)."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

import responsibleai.dashboard.app as app_module
from responsibleai.billing.stripe_service import PlanUpdate, StripeBillingError
from responsibleai.dashboard.app import app, settings
from responsibleai.db.engine import stripe_webhook_events
from responsibleai.rbac.models import Plan, Role
from tests.org_http_fixtures import seed_org_with_key


@pytest.fixture()
async def world(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    async with LifespanManager(app, startup_timeout=15) as manager:
        org_a, _k, _r = await seed_org_with_key(
            name="Hook A", slug=f"hook-a-{uuid.uuid4().hex[:6]}", role=Role.OWNER
        )
        org_b, _k, _r = await seed_org_with_key(
            name="Hook B", slug=f"hook-b-{uuid.uuid4().hex[:6]}", role=Role.OWNER
        )
        async with AsyncClient(
            transport=ASGITransport(app=manager.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            yield client, org_a, org_b


def _service(monkeypatch, *, event, update):
    service = MagicMock()
    service.verify_and_parse_webhook.return_value = event
    service.extract_plan_update.return_value = update
    monkeypatch.setattr(app_module, "_stripe_service", service)
    return service


def _update(org_id: str, plan: Plan = Plan.PRO) -> PlanUpdate:
    return PlanUpdate(
        org_id=org_id,
        plan=plan,
        stripe_customer_id=f"cus_{org_id[:6]}",
        stripe_subscription_id=f"sub_{org_id[:6]}",
        plan_renews_at=None,
        subscription_status="active",
    )


async def _plan(org_id: str) -> Plan:
    return (await app_module._org_repo.get_org(org_id)).plan


async def test_concurrent_deliveries_of_one_event_apply_exactly_once(world, monkeypatch) -> None:
    client, org_a, _b = world
    event = SimpleNamespace(id=f"evt_{uuid.uuid4().hex}", type="customer.subscription.updated")
    _service(monkeypatch, event=event, update=_update(org_a))
    calls = {"n": 0}
    real = app_module._org_repo.set_plan

    async def counting(*a, **k):
        calls["n"] += 1
        await asyncio.sleep(0.05)  # widen the race window
        return await real(*a, **k)

    monkeypatch.setattr(app_module._org_repo, "set_plan", counting)
    replies = await asyncio.gather(
        *[
            client.post("/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"})
            for _ in range(10)
        ]
    )
    bodies = [r.json() for r in replies]
    assert all(r.status_code == 200 for r in replies)
    assert sum(1 for b in bodies if b.get("processed") is True) == 1
    assert sum(1 for b in bodies if b.get("duplicate") is True) == 9
    assert calls["n"] == 1
    assert await _plan(org_a) is Plan.PRO


async def test_an_event_changes_only_the_organization_it_names(world, monkeypatch) -> None:
    client, org_a, org_b = world
    event = SimpleNamespace(id=f"evt_{uuid.uuid4().hex}", type="customer.subscription.updated")
    _service(monkeypatch, event=event, update=_update(org_a, Plan.ENTERPRISE))
    await client.post("/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"})
    assert await _plan(org_a) is Plan.ENTERPRISE
    assert await _plan(org_b) is Plan.FREE


async def test_unknown_organization_is_not_recorded_as_processed(world, monkeypatch) -> None:
    client, _a, org_b = world
    event = SimpleNamespace(id=f"evt_{uuid.uuid4().hex}", type="customer.subscription.updated")
    _service(monkeypatch, event=event, update=_update(str(uuid.uuid4())))
    reply = await client.post(
        "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"}
    )
    assert reply.status_code == 200 and reply.json()["processed"] is False
    assert reply.json()["reason"] == "unknown_organization"
    row = await app_module._billing_event_repo.get(event.id)
    assert row["status"] == "failed" and row["last_error"] == "unknown organization"
    assert await _plan(org_b) is Plan.FREE


async def test_unsigned_floods_write_no_ledger_rows(world, monkeypatch) -> None:
    client, *_ = world
    service = MagicMock()
    service.verify_and_parse_webhook.side_effect = StripeBillingError("bad signature")
    monkeypatch.setattr(app_module, "_stripe_service", service)
    replies = await asyncio.gather(
        *[
            client.post(
                "/api/billing/webhook", content=b"x" * 64, headers={"stripe-signature": "bad"}
            )
            for _ in range(50)
        ]
    )
    # 400 = rejected for the signature; 503 = shed by admission control under this burst.
    assert {r.status_code for r in replies} <= {400, 503} and 400 in {
        r.status_code for r in replies
    }
    async with app_module._billing_event_repo._engine.raw.connect() as conn:
        count = (
            await conn.execute(select(func.count()).select_from(stripe_webhook_events))
        ).scalar()
    assert count == 0  # abuse cannot grow the ledger without a valid signature


async def test_oversized_webhook_bodies_are_rejected_before_processing(world, monkeypatch) -> None:
    client, *_ = world
    service = MagicMock()
    monkeypatch.setattr(app_module, "_stripe_service", service)
    from responsibleai.dashboard.middleware import MAX_REQUEST_BODY_BYTES

    reply = await client.post(
        "/api/billing/webhook",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"stripe-signature": "v1,x"},
    )
    assert reply.status_code == 413
    service.verify_and_parse_webhook.assert_not_called()
