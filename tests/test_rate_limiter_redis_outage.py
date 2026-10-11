# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Redis outage behaviour of the two rate limiters (founder list: "Redis failure behavior").

Policy: rate limiting is an availability/abuse control, not an authority control. When the shared
store is unreachable both limiters degrade to bounded per-replica in-memory enforcement and report
it; they neither fail open without limit nor turn every authenticated request into a 500.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from responsibleai.dashboard.app import _build_limiter
from responsibleai.dashboard.plan_rate_limiter import PlanRateLimiter, plan_limit
from responsibleai.rbac.models import Plan

DEAD_REDIS = "redis://127.0.0.1:1/0"  # nothing listens on port 1


async def test_plan_limiter_degrades_to_a_bounded_local_window(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from fastapi import HTTPException

    limiter = PlanRateLimiter(redis_url=DEAD_REDIS)
    budget = plan_limit(Plan.FREE)
    assert budget is not None
    with caplog.at_level(logging.ERROR):
        for _ in range(budget):
            await limiter.check("org-1", Plan.FREE)  # no ConnectionError escapes
        with pytest.raises(HTTPException) as over:
            await limiter.check("org-1", Plan.FREE)
    assert over.value.status_code == 429  # still bounded, not fail-open
    await limiter.check("org-2", Plan.FREE)  # still per organization
    assert limiter.degraded_events >= budget
    assert any("plan_rate_limiter_degraded" in r.message for r in caplog.records)
    assert sum("plan_rate_limiter_degraded" in r.message for r in caplog.records) == 1  # no flood


async def test_plan_limiter_enterprise_stays_unlimited_during_an_outage() -> None:
    limiter = PlanRateLimiter(redis_url=DEAD_REDIS)
    for _ in range(100):
        await limiter.check("org-ent", Plan.ENTERPRISE)  # unlimited plan never touches the store


async def test_route_limiter_serves_requests_and_still_limits_during_an_outage() -> None:
    limiter = _build_limiter(DEAD_REDIS)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

    @app.get("/x")
    @limiter.limit("5/minute")
    async def x(request: Request) -> dict[str, int]:
        return {"ok": 1}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        codes = [(await c.get("/x")).status_code for _ in range(8)]
    assert 500 not in codes
    assert codes[:5] == [200] * 5 and set(codes[5:]) == {429}
