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

    async def test_claim_marks_status_so_second_caller_does_not_see_it(self, repo):
        """The atomic-claim fix for multi-replica double-delivery: once one
        caller (one replica's retry worker) claims a due row, a second,
        concurrent caller (another replica) must not also get it."""
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        from sqlalchemy import update

        from responsibleai.db.engine import webhook_deliveries
        past = "2000-01-01T00:00:00+00:00"
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(webhook_deliveries)
                .where(webhook_deliveries.c.id == did)
                .values(status="retrying", next_retry_at=past, attempts=1)
            )

        first = await repo.pending_retries()
        assert len(first) == 1
        assert first[0]["id"] == did

        # A second replica polling immediately after must not see the same row.
        second = await repo.pending_retries()
        assert second == []

    async def test_stale_claim_is_reclaimed_after_five_minutes(self, repo):
        """Safety net: a replica that claimed a delivery and crashed before
        firing it must not orphan that retry forever."""
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        from sqlalchemy import update

        from responsibleai.db.engine import webhook_deliveries
        stale = "2000-01-01T00:00:00+00:00"
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(webhook_deliveries)
                .where(webhook_deliveries.c.id == did)
                .values(status="claimed", next_retry_at=stale, attempts=1)
            )

        rows = await repo.pending_retries()
        assert len(rows) == 1
        assert rows[0]["id"] == did

    async def test_recently_claimed_is_not_reclaimed(self, repo):
        """A claim from seconds ago (still being processed by another
        replica) must not be swept up as if it were abandoned."""
        did = _uid()
        await repo.create(did, _uid(), "drift_alert", {}, max_retries=3)
        from datetime import UTC, datetime

        from sqlalchemy import update

        from responsibleai.db.engine import webhook_deliveries
        recent = datetime.now(UTC).isoformat()
        async with repo._engine.raw.begin() as conn:
            await conn.execute(
                update(webhook_deliveries)
                .where(webhook_deliveries.c.id == did)
                .values(status="claimed", next_retry_at=recent, attempts=1)
            )

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


# ── webhook config persistence (registrations, not deliveries) ──────────────

class TestWebhookConfigRepository:
    """WebhookManager used to hold registrations only in memory — they
    vanished on every restart. This covers the DB-backed replacement."""

    @pytest.fixture()
    async def config_repo(self, db_engine):
        from responsibleai.db.webhook_repository import WebhookConfigRepository
        return WebhookConfigRepository(db_engine)

    def _config(self, **overrides):
        from responsibleai.webhooks.models import WebhookConfig, WebhookEvent, WebhookProvider
        defaults = dict(
            url="https://hooks.example.com/generic",
            events=[WebhookEvent.TRUST_SCORE_CHANGED],
            provider=WebhookProvider.GENERIC,
            secret="s3cr3t",
            description="test webhook",
        )
        defaults.update(overrides)
        return WebhookConfig(**defaults)

    async def test_create_and_list_all(self, config_repo):
        cfg = self._config()
        await config_repo.create(cfg)
        loaded = await config_repo.list_all()
        assert len(loaded) == 1
        assert loaded[0].id == cfg.id
        assert loaded[0].url == cfg.url
        assert loaded[0].secret == "s3cr3t"

    async def test_created_at_is_set_if_missing(self, config_repo):
        cfg = self._config()
        assert cfg.created_at == ""
        await config_repo.create(cfg)
        loaded = await config_repo.list_all()
        assert loaded[0].created_at != ""

    async def test_events_round_trip(self, config_repo):
        from responsibleai.webhooks.models import WebhookEvent
        cfg = self._config(events=[WebhookEvent.DRIFT_ALERT, WebhookEvent.BUDGET_EXCEEDED])
        await config_repo.create(cfg)
        loaded = await config_repo.list_all()
        assert set(loaded[0].events) == {WebhookEvent.DRIFT_ALERT, WebhookEvent.BUDGET_EXCEEDED}

    async def test_org_id_round_trips(self, config_repo):
        cfg = self._config(org_id="org-123")
        await config_repo.create(cfg)
        loaded = await config_repo.list_all()
        assert loaded[0].org_id == "org-123"

    async def test_delete_removes_config(self, config_repo):
        cfg = self._config()
        await config_repo.create(cfg)
        assert await config_repo.delete(cfg.id) is True
        assert await config_repo.list_all() == []

    async def test_delete_nonexistent_returns_false(self, config_repo):
        assert await config_repo.delete("nonexistent") is False

    async def test_delete_scoped_to_wrong_org_fails(self, config_repo):
        cfg = self._config(org_id="org-a")
        await config_repo.create(cfg)
        assert await config_repo.delete(cfg.id, org_id="org-b") is False
        assert len(await config_repo.list_all()) == 1

    async def test_delete_scoped_to_correct_org_succeeds(self, config_repo):
        cfg = self._config(org_id="org-a")
        await config_repo.create(cfg)
        assert await config_repo.delete(cfg.id, org_id="org-a") is True

    async def test_manager_load_configs_repopulates_registry(self, config_repo):
        from responsibleai.webhooks.manager import WebhookManager
        cfg = self._config()
        await config_repo.create(cfg)

        manager = WebhookManager()
        manager.set_config_repository(config_repo)
        count = await manager.load_configs()

        assert count == 1
        assert manager.get(cfg.id) is not None
        assert manager.get(cfg.id).url == cfg.url

    async def test_manager_register_and_persist_survives_reload(self, config_repo):
        from responsibleai.webhooks.manager import WebhookManager

        manager_a = WebhookManager()
        manager_a.set_config_repository(config_repo)
        cfg = self._config()
        await manager_a.register_and_persist(cfg)

        # Simulate a process restart: a brand new manager, same repo.
        manager_b = WebhookManager()
        manager_b.set_config_repository(config_repo)
        assert manager_b.get(cfg.id) is None  # not loaded yet
        await manager_b.load_configs()
        assert manager_b.get(cfg.id) is not None

    async def test_manager_remove_and_persist_deletes_from_db(self, config_repo):
        from responsibleai.webhooks.manager import WebhookManager

        manager = WebhookManager()
        manager.set_config_repository(config_repo)
        cfg = self._config()
        await manager.register_and_persist(cfg)

        assert await manager.remove_and_persist(cfg.id) is True
        assert await config_repo.list_all() == []

    async def test_manager_remove_and_persist_respects_org_scope(self, config_repo):
        from responsibleai.webhooks.manager import WebhookManager

        manager = WebhookManager()
        manager.set_config_repository(config_repo)
        cfg = self._config(org_id="org-a")
        await manager.register_and_persist(cfg)

        assert await manager.remove_and_persist(cfg.id, org_id="org-b") is False
        assert manager.get(cfg.id) is not None
        assert await manager.remove_and_persist(cfg.id, org_id="org-a") is True
        assert manager.get(cfg.id) is None

    async def test_list_webhooks_filters_by_org(self):
        from responsibleai.webhooks.manager import WebhookManager
        manager = WebhookManager()
        manager.register(self._config(org_id="org-a"))
        manager.register(self._config(org_id="org-b"))
        manager.register(self._config(org_id="org-a"))

        assert len(manager.list_webhooks(org_id="org-a")) == 2
        assert len(manager.list_webhooks(org_id="org-b")) == 1
        assert len(manager.list_webhooks()) == 3


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
