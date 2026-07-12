"""Tests for McpUsageRepository — MCP tool call metering for PRO/ENTERPRISE billing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.mcp_usage_repository import McpUsageRepository


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return McpUsageRepository(db)


class TestRecordCall:
    async def test_record_call_persists(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 1

    async def test_record_multiple_calls(self, repo):
        for _ in range(5):
            await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 5

    async def test_record_blocked_call(self, repo):
        await repo.record_call("org-1", "rai_passport_generate", "FREE", allowed=False)
        usage = await repo.usage_this_month("org-1")
        assert usage["blocked_calls"] == 1
        assert usage["allowed_calls"] == 0


class TestUsageThisMonth:
    async def test_usage_empty_initially(self, repo):
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 0
        assert usage["allowed_calls"] == 0
        assert usage["blocked_calls"] == 0

    async def test_usage_scoped_to_org(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-2", "rai_scan", "PRO", allowed=True)
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 1

    async def test_usage_by_tool_breakdown(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-1", "rai_trust_score", "PRO", allowed=True)
        usage = await repo.usage_this_month("org-1")
        assert usage["calls_by_tool"]["rai_scan"] == 2
        assert usage["calls_by_tool"]["rai_trust_score"] == 1

    async def test_usage_mixed_allowed_and_blocked(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-1", "rai_passport_generate", "PRO", allowed=False)
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 2
        assert usage["allowed_calls"] == 1
        assert usage["blocked_calls"] == 1

    async def test_usage_excludes_previous_month(self, repo, db):
        from sqlalchemy import insert

        from responsibleai.db.engine import mcp_tool_calls

        last_month = (datetime.now(UTC).replace(day=1) - timedelta(days=1)).isoformat()
        async with db.raw.begin() as conn:
            await conn.execute(insert(mcp_tool_calls).values(
                id="old-call", org_id="org-1", tool_name="rai_scan",
                tier="PRO", timestamp=last_month, allowed=1,
            ))
        usage = await repo.usage_this_month("org-1")
        assert usage["total_calls"] == 0


class TestCountSince:
    async def test_count_since_counts_allowed_only(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=False)
        since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        count = await repo.count_since("org-1", since)
        assert count == 1

    async def test_count_since_respects_cutoff(self, repo, db):
        from sqlalchemy import insert

        from responsibleai.db.engine import mcp_tool_calls

        old_ts = (datetime.now(UTC) - timedelta(days=40)).isoformat()
        async with db.raw.begin() as conn:
            await conn.execute(insert(mcp_tool_calls).values(
                id="old-call", org_id="org-1", tool_name="rai_scan",
                tier="PRO", timestamp=old_ts, allowed=1,
            ))
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        count = await repo.count_since("org-1", since)
        assert count == 1

    async def test_count_since_scoped_to_org(self, repo):
        await repo.record_call("org-1", "rai_scan", "PRO", allowed=True)
        await repo.record_call("org-2", "rai_scan", "PRO", allowed=True)
        since = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        assert await repo.count_since("org-1", since) == 1


class TestTopOrgsByVolume:
    async def test_leaderboard_orders_by_volume_desc(self, repo):
        for _ in range(5):
            await repo.record_call("org-heavy", "rai_scan", "PRO", allowed=True)
        for _ in range(2):
            await repo.record_call("org-light", "rai_scan", "PRO", allowed=True)
        top = await repo.top_orgs_by_volume(days=30)
        assert top[0]["org_id"] == "org-heavy"
        assert top[0]["calls"] == 5

    async def test_leaderboard_excludes_null_org(self, repo):
        await repo.record_call(None, "rai_scan", "FREE", allowed=True)
        top = await repo.top_orgs_by_volume(days=30)
        assert top == []

    async def test_leaderboard_respects_limit(self, repo):
        for i in range(5):
            await repo.record_call(f"org-{i}", "rai_scan", "PRO", allowed=True)
        top = await repo.top_orgs_by_volume(days=30, limit=2)
        assert len(top) == 2
