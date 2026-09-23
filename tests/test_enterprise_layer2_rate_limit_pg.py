# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WP-L2-FIND-001: real PostgreSQL concurrency for identity rate limiting.

Antigravity reproduced a lost-update race at SHA
7a4055343a63abdde3f1363604b0979fed2a4abb: 30 concurrent calls with limit=5
allowed more than 5 requests (this workspace reproduced 12 allowed, DB count 2,
and unique-insert collisions surfaced as IDENTITY_PROTECTION_UNAVAILABLE).
SQLite evidence is not sufficient.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from responsibleai.db.engine import create_engine, identity_rate_counters
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_l2_rate"):
        engine = create_engine(url)
        try:
            await engine.init()
        finally:
            await engine.close()
        yield url


async def _bucket_count(engine, key: str) -> tuple[int, int]:
    async with engine.raw.begin() as conn:
        row = (
            await conn.execute(
                select(identity_rate_counters).where(identity_rate_counters.c.bucket_key == key)
            )
        ).fetchone()
        rows = (
            await conn.execute(
                select(func.count())
                .select_from(identity_rate_counters)
                .where(identity_rate_counters.c.bucket_key == key)
            )
        ).scalar_one()
    if row is None:
        return 0, int(rows)
    return int(row._mapping["count"]), int(rows)


async def _burst(limiter: DurableIdentityRateLimiter, key: str, *, limit: int, n: int) -> list[str]:
    async def one() -> str:
        try:
            await limiter.check(key, limit=limit, window_seconds=60)
            return "ok"
        except EnterpriseError as exc:
            return exc.code

    return list(await asyncio.gather(*[one() for _ in range(n)]))


def _assert_limit(results: list[str], *, limit: int) -> tuple[int, int]:
    ok = results.count("ok")
    limited = results.count("RATE_LIMITED")
    unavailable = results.count("IDENTITY_PROTECTION_UNAVAILABLE")
    assert unavailable == 0, results
    assert ok <= limit
    assert ok + limited == len(results)
    return ok, limited


@pytest.mark.asyncio
async def test_wp_l2_find_001_limit5_30_concurrent(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "login:find001-limit5"
        results = await _burst(limiter, key, limit=5, n=30)
        ok, limited = _assert_limit(results, limit=5)
        db_count, row_count = await _bucket_count(engine, key)
        assert ok == 5
        assert limited == 25
        assert db_count == 5
        assert row_count == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_two_limiter_instances(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        a = DurableIdentityRateLimiter(engine_a)
        b = DurableIdentityRateLimiter(engine_b)
        key = "login:find001-multi"
        limit = 5

        async def one(limiter: DurableIdentityRateLimiter) -> str:
            try:
                await limiter.check(key, limit=limit, window_seconds=60)
                return "ok"
            except EnterpriseError as exc:
                return exc.code

        results = list(
            await asyncio.gather(*([one(a) for _ in range(15)] + [one(b) for _ in range(15)]))
        )
        ok, limited = _assert_limit(results, limit=limit)
        db_count, row_count = await _bucket_count(engine_a, key)
        assert ok == 5
        assert limited == 25
        assert db_count == 5
        assert row_count == 1
    finally:
        await engine_a.close()
        await engine_b.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_fresh_bucket_race(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "oauth:find001-fresh"
        db_count, row_count = await _bucket_count(engine, key)
        assert db_count == 0
        assert row_count == 0
        results = await _burst(limiter, key, limit=3, n=25)
        ok, limited = _assert_limit(results, limit=3)
        db_count, row_count = await _bucket_count(engine, key)
        assert ok == 3
        assert limited == 22
        assert db_count == 3
        assert row_count == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_existing_bucket_race(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "login:find001-existing"
        await limiter.check(key, limit=5, window_seconds=60)
        await limiter.check(key, limit=5, window_seconds=60)
        results = await _burst(limiter, key, limit=5, n=20)
        ok, limited = _assert_limit(results, limit=3)
        db_count, row_count = await _bucket_count(engine, key)
        assert ok == 3
        assert limited == 17
        assert db_count == 5
        assert row_count == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_limit1_20_concurrent(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "recovery:find001-limit1"
        results = await _burst(limiter, key, limit=1, n=20)
        ok, limited = _assert_limit(results, limit=1)
        db_count, row_count = await _bucket_count(engine, key)
        assert ok == 1
        assert limited == 19
        assert db_count == 1
        assert row_count == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_window_rollover_race(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "sso:find001-rollover"
        expired = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        now = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                identity_rate_counters.insert().values(
                    bucket_key=key,
                    window_start=expired,
                    count=9,
                    updated_at=now,
                )
            )
        results = await _burst(limiter, key, limit=2, n=20)
        ok, limited = _assert_limit(results, limit=2)
        db_count, row_count = await _bucket_count(engine, key)
        assert ok == 2
        assert limited == 18
        assert db_count == 2
        assert row_count == 1
        async with engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(identity_rate_counters).where(identity_rate_counters.c.bucket_key == key)
                )
            ).fetchone()
        assert row is not None
        assert str(row._mapping["window_start"]) > expired
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wp_l2_find_001_storage_failure_fail_closed() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    class FakeRaw:
        def begin(self):
            raise SQLAlchemyError("storage down")

    class FakeEngine:
        raw = FakeRaw()

    broken = DurableIdentityRateLimiter(FakeEngine())  # type: ignore[arg-type]
    with pytest.raises(EnterpriseError) as unavailable:
        await broken.check("recovery:owner@example.com", limit=5, window_seconds=60)
    assert unavailable.value.code == "IDENTITY_PROTECTION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_wp_l2_find_001_stale_window_cannot_overwrite_new(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        limiter = DurableIdentityRateLimiter(engine)
        key = "login:find001-stale-window"
        await limiter.check(key, limit=2, window_seconds=60)
        stale = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        async with engine.raw.begin() as conn:
            result = await conn.execute(
                update(identity_rate_counters)
                .where(
                    identity_rate_counters.c.bucket_key == key,
                    identity_rate_counters.c.window_start < stale,
                )
                .values(count=99)
            )
            assert int(result.rowcount or 0) == 0
        db_count, row_count = await _bucket_count(engine, key)
        assert db_count == 1
        assert row_count == 1
    finally:
        await engine.close()
