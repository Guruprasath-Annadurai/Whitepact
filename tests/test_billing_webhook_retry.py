# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A failed or abandoned billing webhook must be retryable, exactly once.

Before: ``begin()`` answered "duplicate" for ANY existing row, so after ``set_plan`` raised (the
event was marked failed and a 500 returned so the provider retries) the retry was swallowed and the
customer's plan change was lost permanently. A crash between ``begin`` and ``complete`` left the row
"processing" forever with the same result.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

import responsibleai.dashboard.app as app_module
from responsibleai.billing.stripe_service import PlanUpdate
from responsibleai.dashboard.app import app, settings
from responsibleai.db.billing_repository import (
    STALE_PROCESSING_AFTER,
    BillingEventRepository,
    is_reclaimable,
)
from responsibleai.db.engine import create_engine, paddle_webhook_events, stripe_webhook_events
from responsibleai.db.paddle_billing_repository import PaddleBillingEventRepository
from responsibleai.rbac.models import Plan, Role
from tests.org_http_fixtures import seed_org_with_key


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


def test_reclaim_rules() -> None:
    now = datetime(2026, 10, 11, tzinfo=UTC)
    old = (now - STALE_PROCESSING_AFTER - timedelta(seconds=1)).isoformat()
    fresh = (now - timedelta(seconds=5)).isoformat()
    assert is_reclaimable("failed", fresh, now=now)
    assert is_reclaimable("processing", old, now=now)
    assert not is_reclaimable("processing", fresh, now=now)
    assert not is_reclaimable("processed", old, now=now)
    assert is_reclaimable("processing", "not-a-date", now=now)  # never block a customer forever
    assert not is_reclaimable(None, None, now=now)


async def _age(engine, table, event_id: str) -> None:
    old = (datetime.now(UTC) - STALE_PROCESSING_AFTER - timedelta(minutes=1)).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(table).where(table.c.event_id == event_id).values(received_at=old)
        )


async def test_stripe_failed_event_is_retried_once_then_final(engine) -> None:
    repo = BillingEventRepository(engine)
    assert await repo.begin("e1", "checkout.session.completed", None) is True
    assert await repo.begin("e1", "checkout.session.completed", None) is False  # in flight
    await repo.fail("e1", "database unavailable")
    assert await repo.begin("e1", "checkout.session.completed", None) is True  # retry wins
    assert await repo.begin("e1", "checkout.session.completed", None) is False  # now in flight
    await repo.complete("e1")
    assert await repo.begin("e1", "checkout.session.completed", None) is False  # processed: final
    assert (await repo.get("e1"))["status"] == "processed"


async def test_stripe_abandoned_processing_row_is_taken_over_after_the_stale_window(engine) -> None:
    repo = BillingEventRepository(engine)
    assert await repo.begin("e2", "x", None) is True
    assert await repo.begin("e2", "x", None) is False
    await _age(engine, stripe_webhook_events, "e2")
    assert await repo.begin("e2", "x", None) is True


async def test_concurrent_retries_of_a_failed_event_have_exactly_one_winner(engine) -> None:
    repo = BillingEventRepository(engine)
    await repo.begin("e3", "x", None)
    await repo.fail("e3", "boom")
    results = await asyncio.gather(*[repo.begin("e3", "x", None) for _ in range(8)])
    assert results.count(True) == 1


async def test_paddle_failed_event_is_retried_once_and_conflicting_payload_still_rejected(
    engine,
) -> None:
    repo = PaddleBillingEventRepository(engine)
    assert await repo.begin("p1", "subscription.updated", "h1") is True
    assert await repo.begin("p1", "subscription.updated", "h1") is False
    await repo.fail("p1", "boom")
    assert await repo.begin("p1", "subscription.updated", "h1") is True
    assert await repo.begin("p1", "subscription.updated", "h1") is False
    with pytest.raises(ValueError, match="Conflicting payload"):
        await repo.begin("p1", "subscription.updated", "DIFFERENT")
    await repo.fail("p1", "boom again")
    with pytest.raises(ValueError, match="Conflicting payload"):  # failed rows stay protected
        await repo.begin("p1", "subscription.updated", "DIFFERENT")
    await repo.complete("p1")
    assert await repo.begin("p1", "subscription.updated", "h1") is False


async def test_paddle_abandoned_processing_row_is_taken_over(engine) -> None:
    repo = PaddleBillingEventRepository(engine)
    await repo.begin("p2", "subscription.updated", "h")
    await _age(engine, paddle_webhook_events, "p2")
    assert await repo.begin("p2", "subscription.updated", "h") is True


async def test_stripe_endpoint_applies_the_plan_when_the_provider_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End to end: first delivery fails inside set_plan (500), the retry must apply the plan."""
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    async with LifespanManager(app, startup_timeout=15) as manager:
        org_id, _k, _raw = await seed_org_with_key(
            name="Retry Co", slug=f"retry-{uuid.uuid4().hex[:8]}", role=Role.OWNER
        )
        event = SimpleNamespace(id=f"evt_{uuid.uuid4().hex}", type="customer.subscription.updated")
        service = MagicMock()
        service.verify_and_parse_webhook.return_value = event
        service.extract_plan_update.return_value = PlanUpdate(
            org_id=org_id,
            plan=Plan.PRO,
            stripe_customer_id="cus_1",
            stripe_subscription_id="sub_1",
            plan_renews_at=None,
            subscription_status="active",
            event_timestamp=datetime.now(UTC).isoformat(),
        )
        monkeypatch.setattr(app_module, "_stripe_service", service)

        real_set_plan_status = app_module._org_repo.set_plan_status
        calls = {"n": 0}

        async def flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("transient database error")
            return await real_set_plan_status(*args, **kwargs)

        monkeypatch.setattr(app_module._org_repo, "set_plan_status", flaky)
        async with AsyncClient(
            transport=ASGITransport(app=manager.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            first = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"}
            )
            assert first.status_code == 500
            assert (await app_module._org_repo.get_org(org_id)).plan == Plan.FREE

            retry = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"}
            )
            assert retry.status_code == 200 and retry.json()["processed"] is True
            assert (await app_module._org_repo.get_org(org_id)).plan == Plan.PRO

            third = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "v1,x"}
            )
            assert third.json()["duplicate"] is True  # processed events are final
            assert calls["n"] == 2
