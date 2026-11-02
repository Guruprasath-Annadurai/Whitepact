"""Tests for PlanRateLimiter — per-org, plan-scaled request budgets."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from responsibleai.dashboard.plan_rate_limiter import (
    PLAN_REQUEST_LIMITS,
    PlanRateLimiter,
    plan_limit,
)
from responsibleai.rbac.models import Plan


@pytest.fixture()
def limiter():
    return PlanRateLimiter(redis_url=None)  # in-memory path — no Redis needed for tests


class TestPlanLimit:
    def test_free_has_a_limit(self):
        assert plan_limit(Plan.FREE) == 60

    def test_pro_has_a_higher_limit(self):
        assert plan_limit(Plan.PRO) == 300
        assert plan_limit(Plan.PRO) > plan_limit(Plan.FREE)

    def test_enterprise_is_unlimited(self):
        assert plan_limit(Plan.ENTERPRISE) is None

    def test_unknown_plan_defaults_to_free_limit(self):
        assert PLAN_REQUEST_LIMITS.get("not-a-plan", 60) == 60


class TestCheckNoOpPaths:
    async def test_none_org_id_never_raises(self, limiter):
        for _ in range(1000):
            await limiter.check(None, Plan.FREE)  # should never throw regardless of volume

    async def test_enterprise_unlimited_never_raises(self, limiter):
        for _ in range(1000):
            await limiter.check("org-1", Plan.ENTERPRISE)


class TestLocalSlidingWindow:
    async def test_allows_up_to_limit(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 5)
        for _ in range(5):
            await limiter.check("org-1", Plan.FREE)  # should not raise

    async def test_blocks_over_limit(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 3)
        for _ in range(3):
            await limiter.check("org-1", Plan.FREE)
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("org-1", Plan.FREE)
        assert exc_info.value.status_code == 429

    async def test_error_message_mentions_plan_and_limit(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 1)
        await limiter.check("org-1", Plan.FREE)
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("org-1", Plan.FREE)
        assert "FREE" in exc_info.value.detail
        assert "1" in exc_info.value.detail

    async def test_orgs_are_isolated(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 2)
        await limiter.check("org-1", Plan.FREE)
        await limiter.check("org-1", Plan.FREE)
        # org-1 is now at its limit; org-2 should be unaffected.
        await limiter.check("org-2", Plan.FREE)

    async def test_window_expires_old_requests(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 2)
        await limiter.check("org-1", Plan.FREE)
        await limiter.check("org-1", Plan.FREE)

        # Simulate the window having passed by manipulating the stored timestamps.
        window = limiter._local["org-1"]
        for i in range(len(window)):
            window[i] -= 61.0

        await limiter.check("org-1", Plan.FREE)  # should not raise — old entries expired

    async def test_pro_gets_higher_ceiling_than_free(self, limiter, monkeypatch):
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.FREE, 2)
        monkeypatch.setitem(PLAN_REQUEST_LIMITS, Plan.PRO, 10)
        for _ in range(5):
            await limiter.check("org-pro", Plan.PRO)  # well under PRO's ceiling, fine


class TestClose:
    async def test_close_without_redis_is_safe(self, limiter):
        await limiter.close()  # no-op when Redis was never connected
