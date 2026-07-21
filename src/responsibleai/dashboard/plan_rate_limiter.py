"""Per-org, plan-aware request rate limiting.

The slowapi/`limits`-backed limiter wired in `app.py` protects every route
with a flat ceiling (`RAI_RATE_LIMIT_DEFAULT`) regardless of who's calling —
an ENTERPRISE customer and an unauthenticated request share the same bucket
shape. This module adds a second, independent layer: a per-org requests-per-
minute budget that scales with the org's billing Plan, enforced once inside
`get_org_context` so every authenticated route gets it automatically without
touching each of the ~40 route decorators individually.

Backing store: Redis (sliding window, shared across replicas) when
`RAI_REDIS_URL` is set; an in-process sliding window otherwise. The
in-process fallback is per-replica only — same caveat as the audit hash
chain and MCP quota counters elsewhere in this codebase, and documented
here for the same reason: false confidence in a multi-replica deployment
is worse than an honestly-scoped single-instance guarantee.
"""

from __future__ import annotations

import time
from collections import deque
from typing import TYPE_CHECKING

from fastapi import HTTPException

from responsibleai.rbac.models import Plan

if TYPE_CHECKING:
    from redis.asyncio import Redis

# Requests per rolling 60s window. None = unlimited (still subject to the
# flat per-route slowapi ceiling, which exists to protect the server itself
# regardless of who's asking).
PLAN_REQUEST_LIMITS: dict[Plan, int | None] = {
    Plan.FREE: 60,
    Plan.PRO: 300,
    Plan.ENTERPRISE: None,
}

_WINDOW_SECONDS = 60.0


def plan_limit(plan: Plan) -> int | None:
    return PLAN_REQUEST_LIMITS.get(plan, 60)


class PlanRateLimiter:
    """Sliding-window request counter, keyed by org_id, scaled by Plan."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Redis | None = None
        self._local: dict[str, deque[float]] = {}

    async def _get_redis(self) -> Redis:
        # Only called from check() after confirming self._redis_url is set.
        assert self._redis_url is not None
        if self._redis is None:
            import redis.asyncio as redis_asyncio

            self._redis = redis_asyncio.from_url(self._redis_url)
        return self._redis

    async def check(self, org_id: str | None, plan: Plan) -> None:
        """Raise HTTPException(429) if *org_id* has exceeded its plan's
        requests-per-minute budget. No-op for unscoped (legacy/anon) callers
        and for plans with no configured limit."""
        if org_id is None:
            return
        limit = plan_limit(plan)
        if limit is None:
            return

        now = time.monotonic()
        if self._redis_url:
            used = await self._check_redis(org_id, now)
        else:
            used = self._check_local(org_id, now)

        if used > limit:
            raise HTTPException(
                429,
                detail=(
                    f"Rate limit exceeded: {limit} requests/minute on the "
                    f"{plan.value} plan. Upgrade for a higher limit or "
                    "retry after the current window."
                ),
            )

    def _check_local(self, org_id: str, now: float) -> int:
        window = self._local.setdefault(org_id, deque())
        cutoff = now - _WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        window.append(now)
        return len(window)

    async def _check_redis(self, org_id: str, now: float) -> int:
        client = await self._get_redis()
        key = f"rai:ratelimit:{org_id}"
        cutoff = now - _WINDOW_SECONDS
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, int(_WINDOW_SECONDS) + 5)
        results = await pipe.execute()
        return int(results[2])

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
