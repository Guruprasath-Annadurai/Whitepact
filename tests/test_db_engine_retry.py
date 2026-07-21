"""Tests for DatabaseEngine.init()'s connection-retry-with-backoff, added to
tolerate transient DB unavailability (e.g. a managed Postgres finishing a
failover, or a container starting before DNS repoints) rather than crashing
hard on the first connection attempt. Does not claim to implement replica
failover itself — see the docstring on DatabaseEngine for that distinction.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from responsibleai.db.engine import DatabaseEngine, create_engine


class _FakeConn:
    async def execute(self, *_args, **_kwargs) -> None:
        return None

    async def run_sync(self, *_args, **_kwargs) -> None:
        return None


class _FakeBeginContext:
    def __init__(self, fail_times: int, box: dict) -> None:
        self._fail_times = fail_times
        self._box = box

    async def __aenter__(self) -> _FakeConn:
        if self._box["calls"] < self._fail_times:
            self._box["calls"] += 1
            raise OperationalError("connect failed", {}, Exception("connection refused"))
        self._box["calls"] += 1
        return _FakeConn()

    async def __aexit__(self, *exc_info) -> None:
        return None


class _FakeEngine:
    def __init__(self, fail_times: int) -> None:
        self.url = "postgresql+asyncpg://user:pass@host/db"
        self._box = {"calls": 0}
        self._fail_times = fail_times

    def begin(self) -> _FakeBeginContext:
        return _FakeBeginContext(self._fail_times, self._box)


class TestDatabaseEngineRetry:
    async def test_succeeds_immediately_when_db_is_up(self):
        db = DatabaseEngine(_FakeEngine(fail_times=0))  # type: ignore[arg-type]
        await db.init(max_attempts=5, base_delay_seconds=0.001)
        assert db.raw._box["calls"] == 1  # type: ignore[attr-defined]

    async def test_retries_transient_failures_then_succeeds(self):
        engine = _FakeEngine(fail_times=3)
        db = DatabaseEngine(engine)  # type: ignore[arg-type]
        await db.init(max_attempts=5, base_delay_seconds=0.001)
        assert engine._box["calls"] == 4  # 3 failures + 1 success

    async def test_raises_after_exhausting_attempts(self):
        engine = _FakeEngine(fail_times=10)  # never succeeds within the attempt budget
        db = DatabaseEngine(engine)  # type: ignore[arg-type]
        with pytest.raises(OperationalError):
            await db.init(max_attempts=3, base_delay_seconds=0.001)
        assert engine._box["calls"] == 3

    async def test_real_sqlite_engine_still_initializes_normally(self):
        """Regression check: the retry loop must not change behavior for the
        happy path against a real (non-mocked) engine."""
        db = create_engine(":memory:")
        await db.init(max_attempts=5, base_delay_seconds=0.001)
        await db.close()
