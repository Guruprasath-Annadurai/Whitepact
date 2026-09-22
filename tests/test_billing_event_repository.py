# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for durable Stripe webhook idempotency."""

import pytest

from responsibleai.db.billing_repository import BillingEventRepository
from responsibleai.db.engine import create_engine


@pytest.fixture()
async def billing_repo():
    engine = create_engine(":memory:")
    await engine.init()
    yield BillingEventRepository(engine)
    await engine.close()


async def test_duplicate_event_is_rejected(billing_repo):
    assert await billing_repo.begin("evt_1", "checkout.session.completed", "org-1") is True
    assert await billing_repo.begin("evt_1", "checkout.session.completed", "org-1") is False


async def test_completed_event_is_durable(billing_repo):
    await billing_repo.begin("evt_2", "customer.subscription.updated", "org-1")
    await billing_repo.complete("evt_2")
    record = await billing_repo.get("evt_2")
    assert record is not None
    assert record["status"] == "processed"
    assert record["processed_at"] is not None
    assert record["last_error"] is None


async def test_failure_is_recorded_without_exposing_unbounded_error(billing_repo):
    await billing_repo.begin("evt_3", "invoice.payment_failed", "org-1")
    await billing_repo.fail("evt_3", "x" * 3000)
    record = await billing_repo.get("evt_3")
    assert record is not None
    assert record["status"] == "failed"
    assert len(str(record["last_error"])) == 2000
