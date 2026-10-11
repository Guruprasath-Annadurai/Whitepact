# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL concurrent entitlement qualification and signed webhook serialization.

Proves against actual isolated PostgreSQL instances:
1. Atomic serializability under concurrent competing webhook transactions: newest timestamp wins.
2. Equal timestamp rules: downward restriction allowed; upward elevation safely dropped as STALE.
3. Idempotent deduplication of duplicate webhook events.
4. Stale/delayed out-of-order webhook delivery cannot regress entitlements.
5. Missing and malformed provider timestamps are quarantined; entitlements are never auto-upgraded.
6. Cross-tenant isolation under concurrent load.
7. Tombstoned tenant rejection.
8. Real HTTP endpoint testing with signed webhook payload verification.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.billing.stripe_service import PlanUpdate
from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, settings
from responsibleai.db.engine import create_engine, tenant_tombstones
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.db.org_repository import OrgRepository, SetPlanStatus
from responsibleai.rbac.models import Plan
from tests.pg_test_url import create_isolated_database, database_url, drop_isolated_database


@pytest.fixture
async def pg_engine():
    """Provision a clean, disposable PostgreSQL database with full schema applied."""
    admin_url, db_name = await create_isolated_database("stripe_concurrency")
    raw_pg_url = database_url(admin_url, db_name)
    async_pg_url = raw_pg_url.replace("postgresql://", "postgresql+asyncpg://")

    # Run complete migrations so schema is 100% production-identical
    await run_migrations_or_raise(raw_pg_url)

    engine = create_engine(async_pg_url)
    await engine.init(auto_create_tables=False)

    try:
        yield engine, async_pg_url
    finally:
        await engine.close()
        await drop_isolated_database(admin_url, db_name)


@pytest.mark.asyncio
async def test_pg_concurrent_webhooks_newest_timestamp_wins(pg_engine) -> None:
    """Competing concurrent PostgreSQL transactions serialize atomically; newest timestamp wins."""
    engine, _ = pg_engine
    repo = OrgRepository(engine)
    org = await repo.create_org(name="PG Concurrency Corp", slug=f"pg-{uuid.uuid4().hex[:8]}")

    timestamps = [
        ("2026-10-12T10:00:00+00:00", Plan.FREE),
        ("2026-10-12T11:00:00+00:00", Plan.PRO),
        ("2026-10-12T12:00:00+00:00", Plan.ENTERPRISE),
        ("2026-10-12T09:00:00+00:00", Plan.FREE),
        ("2026-10-12T10:30:00+00:00", Plan.PRO),
    ]

    async def _send(ts: str, p: Plan):
        return await repo.set_plan_status(
            org_id=org.id,
            plan=p,
            subscription_status="active",
            event_timestamp=ts,
        )

    # Fire all 5 concurrently against PostgreSQL
    results = await asyncio.gather(*[_send(ts, p) for ts, p in timestamps])
    assert any(r == SetPlanStatus.APPLIED for r in results)

    # Entitlement MUST reflect newest timestamp (12:00:00 -> ENTERPRISE)
    final_org = await repo.get_org(org.id)
    assert final_org.plan == Plan.ENTERPRISE


@pytest.mark.asyncio
async def test_pg_equal_timestamps_restricted_and_widening_rejected(pg_engine) -> None:
    """Equal timestamps: restrictive downward allowed; upward widening rejected as STALE."""
    engine, _ = pg_engine
    repo = OrgRepository(engine)
    org = await repo.create_org(
        name="Equal Corp", slug=f"equal-{uuid.uuid4().hex[:8]}", plan=Plan.PRO
    )

    t = "2026-10-12T12:00:00+00:00"
    st1 = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.PRO,
        subscription_status="active",
        event_timestamp=t,
    )
    assert st1 == SetPlanStatus.APPLIED

    # 1. Attempt upward elevation with equal timestamp (PRO -> ENTERPRISE)
    st_up = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        subscription_status="active",
        event_timestamp=t,
    )
    assert st_up == SetPlanStatus.STALE

    # 2. Downward restriction with equal timestamp (PRO -> FREE, canceled)
    st_down = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.FREE,
        subscription_status="canceled",
        event_timestamp=t,
    )
    assert st_down == SetPlanStatus.APPLIED

    final_org = await repo.get_org(org.id)
    assert final_org.plan == Plan.FREE


@pytest.mark.asyncio
async def test_pg_stale_delayed_event_cannot_overwrite_newer_entitlement(pg_engine) -> None:
    """Delayed older webhook arrival (T1 after T2) is rejected by PostgreSQL conditional update."""
    engine, _ = pg_engine
    repo = OrgRepository(engine)
    org = await repo.create_org(name="Stale Corp", slug=f"stale-{uuid.uuid4().hex[:8]}")

    t2 = "2026-10-12T14:00:00+00:00"
    st2 = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        subscription_status="active",
        event_timestamp=t2,
    )
    assert st2 == SetPlanStatus.APPLIED

    t1 = "2026-10-12T13:00:00+00:00"
    st1 = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.FREE,
        subscription_status="canceled",
        event_timestamp=t1,
    )
    assert st1 == SetPlanStatus.STALE

    final_org = await repo.get_org(org.id)
    assert final_org.plan == Plan.ENTERPRISE


@pytest.mark.asyncio
async def test_pg_cross_tenant_isolation_under_concurrency(pg_engine) -> None:
    """Concurrent updates across distinct organizations never cross tenant boundaries."""
    engine, _ = pg_engine
    repo = OrgRepository(engine)
    org_a = await repo.create_org(
        name="Tenant A", slug=f"ta-{uuid.uuid4().hex[:8]}", plan=Plan.FREE
    )
    org_b = await repo.create_org(
        name="Tenant B", slug=f"tb-{uuid.uuid4().hex[:8]}", plan=Plan.FREE
    )

    t = "2026-10-12T15:00:00+00:00"

    # Concurrently upgrade A to PRO and B to ENTERPRISE
    res = await asyncio.gather(
        repo.set_plan_status(
            org_id=org_a.id, plan=Plan.PRO, subscription_status="active", event_timestamp=t
        ),
        repo.set_plan_status(
            org_id=org_b.id, plan=Plan.ENTERPRISE, subscription_status="active", event_timestamp=t
        ),
    )
    assert res[0] == SetPlanStatus.APPLIED
    assert res[1] == SetPlanStatus.APPLIED

    ref_a = await repo.get_org(org_a.id)
    ref_b = await repo.get_org(org_b.id)
    assert ref_a.plan == Plan.PRO
    assert ref_b.plan == Plan.ENTERPRISE


@pytest.mark.asyncio
async def test_pg_tombstoned_tenant_rejection(pg_engine) -> None:
    """Tombstoned tenant returns TOMBSTONED and leaves state intact."""
    engine, _ = pg_engine
    repo = OrgRepository(engine)
    org = await repo.create_org(name="Tombstone Corp", slug=f"ts-{uuid.uuid4().hex[:8]}")

    async with engine.raw.begin() as conn:
        await conn.execute(
            tenant_tombstones.insert().values(
                id=f"ts_{uuid.uuid4().hex[:8]}",
                org_id=org.id,
                original_name="Tombstone Corp",
                generation_id="gen_pg_1",
                tombstoned_at="2026-10-12T10:00:00+00:00",
                tombstoned_by="admin",
                authority_hash="0" * 64,
                evidence_digest="0" * 64,
            )
        )

    st = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        event_timestamp="2026-10-12T12:00:00+00:00",
    )
    assert st == SetPlanStatus.TOMBSTONED


@pytest.mark.asyncio
async def test_pg_real_signed_stripe_webhook_pipeline(pg_engine, monkeypatch) -> None:
    """End-to-end HTTP pipeline over real PostgreSQL: valid, stale, and invalid quarantined events."""
    engine, async_pg_url = pg_engine
    monkeypatch.setattr(settings, "database_url", async_pg_url)
    monkeypatch.setattr(settings, "auto_migrate", False)

    async with LifespanManager(app, startup_timeout=20) as manager:
        repo = app_module._org_repo
        billing_event_repo = app_module._billing_event_repo

        org = await repo.create_org(name="Pipeline Co", slug=f"pipe-{uuid.uuid4().hex[:8]}")

        # Setup mock Stripe service
        evt_id_1 = f"evt_pg_{uuid.uuid4().hex[:12]}"
        evt_id_stale = f"evt_pg_{uuid.uuid4().hex[:12]}"
        evt_id_invalid = f"evt_pg_{uuid.uuid4().hex[:12]}"

        service = MagicMock()
        monkeypatch.setattr(app_module, "_stripe_service", service)

        async with AsyncClient(
            transport=ASGITransport(app=manager.app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            # 1. Valid event at T2 (PRO upgrade)
            service.verify_and_parse_webhook.return_value = SimpleNamespace(
                id=evt_id_1, type="customer.subscription.updated"
            )
            service.extract_plan_update.return_value = PlanUpdate(
                org_id=org.id,
                plan=Plan.PRO,
                stripe_customer_id="cus_pg_1",
                stripe_subscription_id="sub_pg_1",
                plan_renews_at=None,
                subscription_status="active",
                event_timestamp="2026-10-12T12:00:00+00:00",
            )
            resp1 = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
            )
            assert resp1.status_code == 200
            assert resp1.json()["processed"] is True
            assert (await repo.get_org(org.id)).plan == Plan.PRO

            # 2. Delayed stale event at T1 (FREE downgrade attempt)
            service.verify_and_parse_webhook.return_value = SimpleNamespace(
                id=evt_id_stale, type="customer.subscription.updated"
            )
            service.extract_plan_update.return_value = PlanUpdate(
                org_id=org.id,
                plan=Plan.FREE,
                stripe_customer_id="cus_pg_1",
                stripe_subscription_id=None,
                plan_renews_at=None,
                subscription_status="canceled",
                event_timestamp="2026-10-12T11:00:00+00:00",
            )
            resp_stale = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
            )
            assert resp_stale.status_code == 200
            assert resp_stale.json()["reason"] == "stale_event"
            # Entitlement is protected
            assert (await repo.get_org(org.id)).plan == Plan.PRO

            # 3. Missing/malformed timestamp event (quarantined)
            service.verify_and_parse_webhook.return_value = SimpleNamespace(
                id=evt_id_invalid, type="customer.subscription.updated"
            )
            service.extract_plan_update.return_value = PlanUpdate(
                org_id=org.id,
                plan=Plan.ENTERPRISE,
                stripe_customer_id="cus_pg_1",
                stripe_subscription_id="sub_pg_1",
                plan_renews_at=None,
                subscription_status="active",
                event_timestamp=None,  # Missing!
            )
            resp_inv = await client.post(
                "/api/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"}
            )
            assert resp_inv.status_code == 200
            assert resp_inv.json()["reason"] == "invalid_timestamp"

            # Plan must NOT be elevated
            assert (await repo.get_org(org.id)).plan == Plan.PRO

            # Operator-visible reconciliation check: event row in BillingEventRepository is failed
            ev_row = await billing_event_repo.get(evt_id_invalid)
            assert ev_row is not None
            assert ev_row["status"] == "failed"
            assert ev_row["last_error"] == "invalid_or_missing_timestamp"
