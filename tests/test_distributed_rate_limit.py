# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared rate-limit state across two limiter instances.

An in-memory limiter is not this test. The fake client proves the Redis
command path uses one shared sorted set and a wall clock. A live Redis
process is required when WHITEPACT_REQUIRE_REDIS=1.
"""

from __future__ import annotations

import os

import pytest

from responsibleai.dashboard import plan_rate_limiter as rate_module
from responsibleai.dashboard.plan_rate_limiter import PlanRateLimiter
from responsibleai.rbac.models import Plan


class _Pipe:
    def __init__(self, space: dict[str, dict[str, float]]) -> None:
        self._space = space
        self._ops: list[tuple[object, ...]] = []

    def zremrangebyscore(self, key: str, low: float, high: float) -> _Pipe:
        self._ops.append(("rem", key, float(low), float(high)))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> _Pipe:
        self._ops.append(("add", key, dict(mapping)))
        return self

    def zcard(self, key: str) -> _Pipe:
        self._ops.append(("card", key))
        return self

    def expire(self, key: str, ttl: int) -> _Pipe:
        self._ops.append(("exp", key, ttl))
        return self

    async def execute(self) -> list[object]:
        results: list[object] = []
        for op in self._ops:
            kind = op[0]
            key = str(op[1])
            bucket = self._space.setdefault(key, {})
            if kind == "rem":
                low, high = float(op[2]), float(op[3])
                for member, score in list(bucket.items()):
                    if low <= score <= high:
                        del bucket[member]
                results.append(1)
            elif kind == "add":
                mapping = op[2]
                assert isinstance(mapping, dict)
                for member, score in mapping.items():
                    bucket[str(member)] = float(score)
                results.append(1)
            elif kind == "card":
                results.append(len(bucket))
            else:
                results.append(True)
        return results


class _SharedRedis:
    def __init__(self) -> None:
        self.space: dict[str, dict[str, float]] = {}

    def pipeline(self) -> _Pipe:
        return _Pipe(self.space)


def _bind(limiter: PlanRateLimiter, client: _SharedRedis) -> None:
    async def _get() -> _SharedRedis:
        return client

    limiter._get_redis = _get  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_two_instances_share_one_redis_window(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = {"now": 1_700_000_000.0}
    monkeypatch.setattr(rate_module.time, "time", lambda: clock["now"])
    monkeypatch.setattr(rate_module.time, "monotonic", lambda: 10.0)
    shared = _SharedRedis()
    first = PlanRateLimiter(redis_url="redis://shared/0")
    second = PlanRateLimiter(redis_url="redis://shared/0")
    _bind(first, shared)
    _bind(second, shared)
    for _ in range(30):
        await first.check("org-shared", Plan.FREE)
    for _ in range(30):
        await second.check("org-shared", Plan.FREE)
    with pytest.raises(Exception, match="Rate limit exceeded") as raised:
        await second.check("org-shared", Plan.FREE)
    assert getattr(raised.value, "status_code", None) == 429
    scores = set(shared.space["rai:ratelimit:org-shared"].values())
    assert scores == {1_700_000_000.0}
    assert 10.0 not in scores


@pytest.mark.asyncio
async def test_live_redis_replicas_share_a_window() -> None:
    url = os.environ.get("WHITEPACT_REDIS_URL", "")
    required = os.environ.get("WHITEPACT_REQUIRE_REDIS", "") == "1"
    if not url:
        if required:
            pytest.fail("WHITEPACT_REQUIRE_REDIS=1 but WHITEPACT_REDIS_URL is empty")
        pytest.skip(
            "QUALIFICATION_SKIP purpose=live Redis shared rate limit. "
            "No WHITEPACT_REDIS_URL. The skip is not a distributed-limiter pass."
        )
    try:
        import redis.asyncio as redis_asyncio
    except ImportError:
        if required:
            pytest.fail("redis client is not installed and WHITEPACT_REQUIRE_REDIS=1")
        pytest.skip(
            "QUALIFICATION_SKIP purpose=live Redis shared rate limit. "
            "The redis package is not installed. The skip is not a pass."
        )
    client = redis_asyncio.from_url(url)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        if required:
            pytest.fail(f"Redis required for the distributed limiter test is unreachable: {exc}")
        pytest.skip(
            "QUALIFICATION_SKIP purpose=live Redis shared rate limit. "
            f"Redis is unreachable ({exc}). The skip is not a pass."
        )
    org = "org-live-limit"
    await client.delete(f"rai:ratelimit:{org}")
    first = PlanRateLimiter(redis_url=url)
    second = PlanRateLimiter(redis_url=url)
    try:
        for _ in range(60):
            await first.check(org, Plan.FREE)
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await second.check(org, Plan.FREE)
    finally:
        await client.delete(f"rai:ratelimit:{org}")
        await first.close()
        await second.close()
        await client.aclose()
