# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validation of out-of-order Stripe billing event rejection and monotonic entitlement integrity."""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.db.engine import create_engine, tenant_tombstones
from responsibleai.db.org_repository import OrgRepository, SetPlanStatus
from responsibleai.rbac.models import Plan


@pytest.mark.asyncio
async def test_stripe_out_of_order_event_does_not_regress_plan(tmp_path) -> None:
    db_path = str(tmp_path / "stripe_order_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    org = await repo.create_org(name="Acme Corp", slug="acme")

    # Event 1 at T2 (newer): upgrade to ENTERPRISE
    t2 = "2026-10-11T12:00:00+00:00"
    status1 = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        subscription_status="active",
        event_timestamp=t2,
    )
    assert status1 == SetPlanStatus.APPLIED
    updated = await repo.get_org(org.id)
    assert updated.plan == Plan.ENTERPRISE

    # Event 2 at T1 (older delayed event): downgrade to FREE
    t1 = "2026-10-11T11:00:00+00:00"
    status2 = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.FREE,
        stripe_customer_id="cus_123",
        stripe_subscription_id=None,
        subscription_status="canceled",
        event_timestamp=t1,
    )
    # Must be safely ignored as STALE
    assert status2 == SetPlanStatus.STALE

    # Entitlement must remain ENTERPRISE, not regressed by the stale out-of-order event
    unchanged = await repo.get_org(org.id)
    assert unchanged.plan == Plan.ENTERPRISE


@pytest.mark.asyncio
async def test_stripe_equal_timestamp_cannot_widen_plan(tmp_path) -> None:
    """Equal timestamps represent ambiguous chronology and cannot widen plan (zero-trust)."""
    db_path = str(tmp_path / "stripe_equal_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    org = await repo.create_org(name="Beta Corp", slug="beta", plan=Plan.PRO)

    t = "2026-10-11T12:00:00+00:00"
    # Establish current baseline at time T
    await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.PRO,
        subscription_status="active",
        event_timestamp=t,
    )

    # An equal-timestamp event attempting to elevate PRO -> ENTERPRISE must be rejected
    status_widen = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        subscription_status="active",
        event_timestamp=t,
    )
    assert status_widen == SetPlanStatus.STALE

    current = await repo.get_org(org.id)
    assert current.plan == Plan.PRO


@pytest.mark.asyncio
async def test_stripe_equal_timestamp_idempotent_event(tmp_path) -> None:
    """Equal timestamp with identical plan & status is treated idempotently."""
    db_path = str(tmp_path / "stripe_idempotent_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    org = await repo.create_org(name="Gamma Corp", slug="gamma", plan=Plan.PRO)

    t = "2026-10-11T12:00:00+00:00"
    await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.PRO,
        subscription_status="active",
        event_timestamp=t,
    )

    # Equal timestamp duplicate event with same plan & status
    status_dup = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.PRO,
        subscription_status="active",
        event_timestamp=t,
    )
    assert status_dup == SetPlanStatus.STALE


@pytest.mark.asyncio
async def test_stripe_unknown_org_returns_not_found(tmp_path) -> None:
    db_path = str(tmp_path / "stripe_not_found_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    status = await repo.set_plan_status(
        org_id="nonexistent_org_id",
        plan=Plan.PRO,
        event_timestamp="2026-10-11T12:00:00+00:00",
    )
    assert status == SetPlanStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_stripe_tombstoned_org_returns_tombstoned(tmp_path) -> None:
    db_path = str(tmp_path / "stripe_tombstone_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    org = await repo.create_org(name="Dead Corp", slug="dead")

    # Tombstone the org
    async with engine.raw.begin() as conn:
        await conn.execute(
            tenant_tombstones.insert().values(
                id="ts_1",
                org_id=org.id,
                original_name="Dead Corp",
                generation_id="gen_1",
                tombstoned_at="2026-10-11T10:00:00+00:00",
                tombstoned_by="admin",
                authority_hash="0" * 64,
                evidence_digest="0" * 64,
            )
        )

    status = await repo.set_plan_status(
        org_id=org.id,
        plan=Plan.PRO,
        event_timestamp="2026-10-11T12:00:00+00:00",
    )
    assert status == SetPlanStatus.TOMBSTONED


@pytest.mark.asyncio
async def test_stripe_concurrent_transactions_atomic_serialization(tmp_path) -> None:
    """Multiple concurrent transitions are serialized atomically; latest timestamp always wins."""
    db_path = str(tmp_path / "stripe_concurrent_test.db")
    engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await engine.init()

    repo = OrgRepository(engine)
    org = await repo.create_org(name="Concurrent Corp", slug="concurrent")

    # Prepare events with different timestamps
    timestamps = [
        ("2026-10-11T10:00:00+00:00", Plan.FREE),
        ("2026-10-11T11:00:00+00:00", Plan.PRO),
        ("2026-10-11T12:00:00+00:00", Plan.ENTERPRISE),
        ("2026-10-11T09:00:00+00:00", Plan.FREE),
        ("2026-10-11T10:30:00+00:00", Plan.PRO),
    ]

    async def _send_event(ts: str, p: Plan):
        return await repo.set_plan_status(
            org_id=org.id,
            plan=p,
            subscription_status="active",
            event_timestamp=ts,
        )

    # Execute all 5 concurrently
    results = await asyncio.gather(*[_send_event(ts, p) for ts, p in timestamps])
    assert any(r == SetPlanStatus.APPLIED for r in results)

    # Final state MUST reflect the chronologically newest event (12:00:00 -> ENTERPRISE)
    final_org = await repo.get_org(org.id)
    assert final_org.plan == Plan.ENTERPRISE
