# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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

import logging
import time
import uuid
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

logger = logging.getLogger(__name__)
# Log the degraded state at most this often; an outage must be visible, not a log flood.
_DEGRADED_LOG_INTERVAL_SECONDS = 30.0


def plan_limit(plan: Plan) -> int | None:
    return PLAN_REQUEST_LIMITS.get(plan, 60)


# Per-route ceiling for an ENTERPRISE organization, whose plan budget is "unlimited". The flat
# per-route slowapi limits exist to protect the server; they must not make a paying plan's
# documented budget unreachable (REC-28), but "unlimited" still needs a finite server-side bound.
ENTERPRISE_ROUTE_CEILING_PER_MINUTE = 1200

# Only throughput limits scale. Anything below this base is a deliberate abuse/step-up control
# (key issuance, login, MFA, billing mutations) and is never raised by plan.
MIN_SCALED_BASE_PER_MINUTE = 30


def scaled_route_limit(base_per_minute: int, plan: Plan | None) -> int:
    """The per-route requests/minute an organization on *plan* gets for a route whose flat
    limit is *base_per_minute*: never below the base, never below the plan's own budget."""
    if plan is None or base_per_minute < MIN_SCALED_BASE_PER_MINUTE:
        return base_per_minute
    budget = plan_limit(plan)
    if budget is None:
        budget = ENTERPRISE_ROUTE_CEILING_PER_MINUTE
    return max(base_per_minute, budget)


class OrgPlanDirectory:
    """Bounded, process-local map org_id -> plan, filled by the authentication dependency on
    every request so the route limiter (which only sees the rate-limit key) can scale."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._max = max_entries
        self._plans: dict[str, Plan] = {}

    def remember(self, org_id: str | None, plan: Plan) -> None:
        if not org_id:
            return
        if org_id not in self._plans and len(self._plans) >= self._max:
            self._plans.pop(next(iter(self._plans)))
        self._plans[org_id] = plan

    def plan_for_key(self, rate_key: str) -> Plan | None:
        if not rate_key.startswith("org:"):
            return None
        return self._plans.get(rate_key[4:])


class PlanRateLimiter:
    """Sliding-window request counter, keyed by org_id, scaled by Plan."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url
        self._redis: Redis | None = None
        self._local: dict[str, deque[float]] = {}
        self._last_degraded_log: float | None = None
        self.degraded_events = 0

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

        # Redis scores must use a clock shared by every replica.
        # time.monotonic() is process-local and would split one tenant
        # across unrelated windows.
        if self._redis_url:
            try:
                used = await self._check_redis(org_id, time.time())
            except Exception as exc:  # redis.exceptions.* and OSError/timeouts alike
                # Rate limiting is an availability/abuse control, not an authority control:
                # authority state (nonces, epochs, approvals) lives in the database and is
                # unaffected. A cache outage must not turn every authenticated request into a
                # 500, so degrade to the in-process window (per replica -- weaker than the shared
                # window, still bounded) and say so loudly.
                self._note_degraded(exc)
                used = self._check_local(org_id, time.monotonic())
        else:
            used = self._check_local(org_id, time.monotonic())

        if used > limit:
            raise HTTPException(
                429,
                detail=(
                    f"Rate limit exceeded: {limit} requests/minute on the "
                    f"{plan.value} plan. Upgrade for a higher limit or "
                    "retry after the current window."
                ),
            )

    def _note_degraded(self, exc: Exception) -> None:
        now = time.monotonic()
        if (
            self._last_degraded_log is None
            or now - self._last_degraded_log >= _DEGRADED_LOG_INTERVAL_SECONDS
        ):
            self._last_degraded_log = now
            logger.error(
                "plan_rate_limiter_degraded backend=redis error=%s fallback=in_process_per_replica",
                type(exc).__name__,
            )
        self.degraded_events += 1

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
        member = f"{now:.6f}:{uuid.uuid4().hex}"
        pipe = client.pipeline()
        pipe.zremrangebyscore(key, 0, cutoff)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, int(_WINDOW_SECONDS) + 5)
        results = await pipe.execute()
        return int(results[2])

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
