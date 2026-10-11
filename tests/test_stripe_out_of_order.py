# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validation of out-of-order Stripe billing event rejection and monotonic entitlement integrity."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository
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
    ok1 = await repo.set_plan(
        org_id=org.id,
        plan=Plan.ENTERPRISE,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_123",
        subscription_status="active",
        event_timestamp=t2,
    )
    assert ok1 is True
    updated = await repo.get_org(org.id)
    assert updated.plan == Plan.ENTERPRISE

    # Event 2 at T1 (older delayed event): downgrade to FREE
    t1 = "2026-10-11T11:00:00+00:00"
    ok2 = await repo.set_plan(
        org_id=org.id,
        plan=Plan.FREE,
        stripe_customer_id="cus_123",
        stripe_subscription_id=None,
        subscription_status="canceled",
        event_timestamp=t1,
    )
    # Must be safely ignored (return False)
    assert ok2 is False

    # Entitlement must remain ENTERPRISE, not regressed by the stale out-of-order event
    unchanged = await repo.get_org(org.id)
    assert unchanged.plan == Plan.ENTERPRISE
