"""Tests for DB-backed webhook delivery repository and retry worker."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from responsibleai.db.engine import DatabaseEngine, metadata
from responsibleai.db.webhook_repository import WebhookDeliveryRepository


@pytest.fixture()
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    db = DatabaseEngine(engine)
    yield db
    await engine.dispose()


@pytest.fixture()
async def repo(db_engine):
    return WebhookDeliveryRepository(db_engine)


def _uid() -> str:
    return str(uuid.uuid4())


# ── create ────────────────────────────────────────────────────────────────────

class TestCreate:
    async def test_create_stores_row(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {"score": 0.9})
        row = await repo._get(did)
        assert row is not None
        assert row["status"] == "pending"
        assert row["attempts"] == 0
        assert row["payload"] == {"score": 0.9}

    async def test_create_sets_max_retries(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "budget_exceeded", {}, max_retries=5)
        row = await repo._get(did)
        assert row["max_retries"] == 5

    async def test_create_default_max_retries(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "trust_score_changed", {})
        row = await repo._get(did)
        assert row["max_retries"] == 3


# ── record_attempt ────────────────────────────────────────────────────────────

class TestRecordAttempt:
    async def test_success_marks_delivered(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {})
        await repo.record_attempt(did, 1, 200, None, success=True)
        row = await repo._get(did)
        assert row["status"] == "delivered"
        assert row["delivered_at"] is not None
        assert row["next_retry_at"] is None

    async def test_failure_within_retries_marks_retrying(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        await repo.record_attempt(did, 1, 503, "Service Unavailable", success=False)
        row = await repo._get(did)
        assert row["status"] == "retrying"
        assert row["next_retry_at"] is not None

    async def test_failure_at_max_retries_marks_failed(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        await repo.record_attempt(did, 3, 503, "still down", success=False)
        row = await repo._get(did)
        assert row["status"] == "failed"
        assert row["next_retry_at"] is None

    async def test_records_status_code_and_error(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "budget_exceeded", {})
        await repo.record_attempt(did, 1, 422, "Unprocessable Entity", success=False)
        row = await repo._get(did)
        assert row["status_code"] == 422
        assert row["last_error"] == "Unprocessable Entity"


# ── pending_retries ───────────────────────────────────────────────────────────

class TestPendingRetries:
    async def test_empty_initially(self, repo):
        rows = await repo.pending_retries()
        assert rows == []

    async def test_retrying_row_returned_when_due(self, repo):
        did = _uid()
        wid = _uid()
        await repo.create(did, wid, "drift_alert", {"x": 1}, max_retries=3)
        # Force next_retry_at into the past by using 0-second delay indirectly.
        # record_attempt uses _at(delay) where delay >= 1s. We'll set it manually.
        from sqlalchemy import update

        from responsibleai.db.engine import webhook_deliveries
        past = "2000-01-01T00:00:00+00:00"
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(webhook_deliveries)
                .where(webhook_deliveries.c.id == did)
                .values(status="retrying", next_retry_at=past, attempts=1)
            )
        rows = await repo.pending_retries()
        assert len(rows) == 1
        assert rows[0]["id"] == did
        assert rows[0]["webhook_id"] == wid

    async def test_future_retry_not_returned(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        from sqlalchemy import update

        from responsibleai.db.engine import webhook_deliveries
        future = "2099-01-01T00:00:00+00:00"
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(webhook_deliveries)
                .where(webhook_deliveries.c.id == did)
                .values(status="retrying", next_retry_at=future, attempts=1)
            )
        rows = await repo.pending_retries()
        assert rows == []

    async def test_delivered_not_returned(self, repo):
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {})
        await repo.record_attempt(did, 1, 200, None, success=True)
        rows = await repo.pending_retries()
        assert rows == []


# ── list + stats ──────────────────────────────────────────────────────────────

class TestListAndStats:
    async def test_list_empty(self, repo):
        assert await repo.list() == []

    async def test_list_returns_created_rows(self, repo):
        ids = [_uid() for _ in range(3)]
        for did in ids:
            await repo.create(did, _uid(), "trust_score_changed", {})
        rows = await repo.list()
        assert len(rows) == 3

    async def test_list_respects_limit(self, repo):
        for _ in range(10):
            await repo.create(_uid(), _uid(), "drift_alert", {})
        rows = await repo.list(limit=5)
        assert len(rows) == 5

    async def test_stats_counts_by_status(self, repo):
        d1, d2, d3 = _uid(), _uid(), _uid()
        await repo.create(d1, _uid(), "drift_alert", {})
        await repo.create(d2, _uid(), "drift_alert", {})
        await repo.create(d3, _uid(), "drift_alert", {})
        await repo.record_attempt(d1, 1, 200, None, success=True)
        await repo.record_attempt(d2, 3, 503, "err", success=False)
        stats = await repo.stats()
        assert stats.get("delivered", 0) >= 1
        assert stats.get("failed", 0) >= 1
        assert stats.get("pending", 0) >= 1


# ── per-org rate limit key function ──────────────────────────────────────────

class TestRateLimitKeyFunction:
    """Rate limit key must isolate by Bearer token, fall back to IP."""

    def _make_request(self, auth_header: str | None = None, client_ip: str = "1.2.3.4"):
        from unittest.mock import MagicMock
        req = MagicMock()
        req.headers = {}
        if auth_header:
            req.headers = {"Authorization": auth_header}
        req.client = MagicMock()
        req.client.host = client_ip
        return req

    def test_bearer_token_produces_key_prefix(self):
        import hashlib

        from responsibleai.dashboard.app import _get_rate_limit_key
        req = self._make_request("Bearer mytoken123")
        key = _get_rate_limit_key(req)
        assert key.startswith("key:")
        expected = "key:" + hashlib.sha256(b"mytoken123").hexdigest()[:24]
        assert key == expected

    def test_different_tokens_produce_different_keys(self):
        from responsibleai.dashboard.app import _get_rate_limit_key
        req1 = self._make_request("Bearer token_org_a")
        req2 = self._make_request("Bearer token_org_b")
        assert _get_rate_limit_key(req1) != _get_rate_limit_key(req2)

    def test_same_token_produces_same_key(self):
        from responsibleai.dashboard.app import _get_rate_limit_key
        req1 = self._make_request("Bearer stable_token")
        req2 = self._make_request("Bearer stable_token")
        assert _get_rate_limit_key(req1) == _get_rate_limit_key(req2)

    def test_no_auth_falls_back_to_ip(self):
        from responsibleai.dashboard.app import _get_rate_limit_key
        req = self._make_request(None, client_ip="10.0.0.1")
        key = _get_rate_limit_key(req)
        assert not key.startswith("key:")

    def test_non_bearer_falls_back_to_ip(self):
        from responsibleai.dashboard.app import _get_rate_limit_key
        req = self._make_request("Basic dXNlcjpwYXNz")
        key = _get_rate_limit_key(req)
        assert not key.startswith("key:")


# ── migration file sanity ─────────────────────────────────────────────────────

class TestMigrationFile:
    def test_initial_migration_exists(self):
        from pathlib import Path
        versions = Path(__file__).resolve().parents[1] / "migrations" / "versions"
        files = list(versions.glob("*.py"))
        assert len(files) >= 1

    def test_initial_migration_importable(self):
        pytest.importorskip("alembic", reason="alembic not installed")
        import importlib.util
        from pathlib import Path
        f = next(
            (Path(__file__).resolve().parents[1] / "migrations" / "versions").glob("0001*.py")
        )
        spec = importlib.util.spec_from_file_location("migration_0001", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "0001"
        assert mod.down_revision is None
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_alembic_ini_exists(self):
        from pathlib import Path
        ini = Path(__file__).resolve().parents[1] / "alembic.ini"
        assert ini.exists()

    def test_env_py_exists(self):
        from pathlib import Path
        env = Path(__file__).resolve().parents[1] / "migrations" / "env.py"
        assert env.exists()
