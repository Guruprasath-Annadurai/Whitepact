"""Tests for AuditRepository — write, query, cleanup, endpoint summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.engine import create_engine
from responsibleai.rbac.models import AuditEntry


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return AuditRepository(db)


def _entry(**kwargs) -> AuditEntry:
    defaults = {
        "endpoint": "/api/evaluate",
        "method": "POST",
        "status_code": 200,
        "duration_ms": 45.2,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    defaults.update(kwargs)
    return AuditEntry(**defaults)


# ── Write & read ───────────────────────────────────────────────────────────────

class TestAuditWrite:
    async def test_write_single_entry(self, repo):
        await repo.write(_entry())
        count = await repo.count(days=1)
        assert count == 1

    async def test_write_multiple_entries(self, repo):
        for _ in range(5):
            await repo.write(_entry())
        assert await repo.count(days=1) == 5

    async def test_query_returns_list(self, repo):
        await repo.write(_entry())
        entries = await repo.query(days=1)
        assert isinstance(entries, list)
        assert len(entries) == 1

    async def test_query_entry_has_expected_fields(self, repo):
        await repo.write(_entry(org_id="org1", key_id="k1"))
        entries = await repo.query(days=1)
        e = entries[0]
        for field in ("id", "timestamp", "org_id", "key_id", "endpoint", "method", "status_code", "duration_ms"):
            assert field in e

    async def test_query_filters_by_org_id(self, repo):
        await repo.write(_entry(org_id="org1"))
        await repo.write(_entry(org_id="org2"))
        entries = await repo.query(org_id="org1", days=1)
        assert len(entries) == 1
        assert entries[0]["org_id"] == "org1"

    async def test_query_filters_by_endpoint(self, repo):
        await repo.write(_entry(endpoint="/api/evaluate"))
        await repo.write(_entry(endpoint="/api/scan"))
        entries = await repo.query(endpoint="/api/scan", days=1)
        assert len(entries) == 1
        assert entries[0]["endpoint"] == "/api/scan"

    async def test_query_limit(self, repo):
        for _ in range(10):
            await repo.write(_entry())
        entries = await repo.query(days=1, limit=3)
        assert len(entries) == 3

    async def test_query_offset(self, repo):
        for i in range(5):
            await repo.write(_entry(endpoint=f"/api/ep{i}"))
        all_entries = await repo.query(days=1)
        offset_entries = await repo.query(days=1, offset=2)
        assert len(offset_entries) == len(all_entries) - 2

    async def test_count_zero_initially(self, repo):
        assert await repo.count(days=7) == 0

    async def test_count_with_org_filter(self, repo):
        await repo.write(_entry(org_id="org-a"))
        await repo.write(_entry(org_id="org-b"))
        assert await repo.count(days=1, org_id="org-a") == 1

    async def test_timestamp_auto_set(self, repo):
        e = AuditEntry(endpoint="/test", method="GET")
        assert e.timestamp == ""
        await repo.write(e)
        entries = await repo.query(days=1)
        assert entries[0]["timestamp"] != ""


# ── Cleanup ────────────────────────────────────────────────────────────────────

class TestAuditCleanup:
    async def test_cleanup_removes_old_entries(self, repo):
        old_ts = (datetime.now(UTC) - timedelta(days=100)).isoformat()
        await repo.write(_entry(timestamp=old_ts))
        await repo.write(_entry())  # recent entry
        deleted = await repo.cleanup(retention_days=90)
        assert deleted == 1
        assert await repo.count(days=1) == 1

    async def test_cleanup_keeps_recent_entries(self, repo):
        await repo.write(_entry())
        deleted = await repo.cleanup(retention_days=90)
        assert deleted == 0
        assert await repo.count(days=1) == 1

    async def test_cleanup_returns_count(self, repo):
        old_ts = (datetime.now(UTC) - timedelta(days=200)).isoformat()
        for _ in range(3):
            await repo.write(_entry(timestamp=old_ts))
        deleted = await repo.cleanup(retention_days=90)
        assert deleted == 3


# ── Endpoint summary ───────────────────────────────────────────────────────────

class TestEndpointSummary:
    async def test_summary_empty(self, repo):
        summary = await repo.endpoint_summary(days=7)
        assert summary == []

    async def test_summary_counts_by_endpoint(self, repo):
        for _ in range(3):
            await repo.write(_entry(endpoint="/api/evaluate"))
        for _ in range(2):
            await repo.write(_entry(endpoint="/api/scan"))
        summary = await repo.endpoint_summary(days=1)
        counts = {s["endpoint"]: s["count"] for s in summary}
        assert counts["/api/evaluate"] == 3
        assert counts["/api/scan"] == 2

    async def test_summary_includes_avg_ms(self, repo):
        await repo.write(_entry(endpoint="/api/test", duration_ms=100.0))
        await repo.write(_entry(endpoint="/api/test", duration_ms=200.0))
        summary = await repo.endpoint_summary(days=1)
        assert summary[0]["avg_ms"] == 150.0

    async def test_summary_ordered_by_count_desc(self, repo):
        for _ in range(5):
            await repo.write(_entry(endpoint="/api/heavy"))
        for _ in range(2):
            await repo.write(_entry(endpoint="/api/light"))
        summary = await repo.endpoint_summary(days=1)
        assert summary[0]["endpoint"] == "/api/heavy"


# ── Hash chain tamper-evidence ─────────────────────────────────────────────────

class TestAuditHashChain:
    async def test_first_entry_chains_to_genesis(self, repo):
        await repo.write(_entry())
        entries = await repo.query(days=1)
        assert entries[0]["prev_hash"] == "0" * 64
        assert entries[0]["entry_hash"] is not None
        assert len(entries[0]["entry_hash"]) == 64

    async def test_entries_chain_sequentially(self, repo):
        await repo.write(_entry(endpoint="/api/a"))
        await repo.write(_entry(endpoint="/api/b"))
        entries = await repo.query(days=1)
        # query() returns newest first; sort ascending by write order.
        entries = sorted(entries, key=lambda e: e["timestamp"])
        assert entries[1]["prev_hash"] == entries[0]["entry_hash"]

    async def test_verify_chain_intact_on_untouched_log(self, repo):
        for _ in range(5):
            await repo.write(_entry())
        result = await repo.verify_chain(days=1)
        assert result["intact"] is True
        assert result["entries_checked"] == 5
        assert result["broken_links"] == []

    async def test_verify_chain_empty_log_is_intact(self, repo):
        result = await repo.verify_chain(days=1)
        assert result["intact"] is True
        assert result["entries_checked"] == 0

    async def test_verify_chain_detects_tampered_row(self, repo, db):
        await repo.write(_entry())
        await repo.write(_entry())

        from sqlalchemy import update as sa_update

        from responsibleai.db.engine import audit_log

        async with db.raw.begin() as conn:
            await conn.execute(
                sa_update(audit_log)
                .where(audit_log.c.endpoint == "/api/evaluate")
                .values(status_code=999)
            )

        result = await repo.verify_chain(days=1)
        assert result["intact"] is False
        assert len(result["broken_links"]) >= 1

    async def test_verify_chain_detects_deleted_row(self, repo, db):
        await repo.write(_entry(endpoint="/api/a"))
        await repo.write(_entry(endpoint="/api/b"))
        await repo.write(_entry(endpoint="/api/c"))

        from sqlalchemy import delete as sa_delete

        from responsibleai.db.engine import audit_log

        async with db.raw.begin() as conn:
            await conn.execute(
                sa_delete(audit_log).where(audit_log.c.endpoint == "/api/b")
            )

        result = await repo.verify_chain(days=1)
        assert result["intact"] is False

    async def test_hydration_resumes_chain_across_new_repo_instance(self, db):
        repo1 = AuditRepository(db)
        await repo1.write(_entry(endpoint="/api/first"))

        repo2 = AuditRepository(db)  # simulates a fresh process attaching to same DB
        await repo2.write(_entry(endpoint="/api/second"))

        result = await repo2.verify_chain(days=1)
        assert result["intact"] is True
        assert result["entries_checked"] == 2

    async def test_concurrent_writes_produce_valid_chain(self, repo):
        import asyncio

        await asyncio.gather(*[repo.write(_entry(endpoint=f"/api/c{i}")) for i in range(20)])
        result = await repo.verify_chain(days=1)
        assert result["intact"] is True
        assert result["entries_checked"] == 20
