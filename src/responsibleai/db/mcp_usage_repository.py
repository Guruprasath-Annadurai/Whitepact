"""Async repository for MCP tool call metering — the basis for PRO/ENTERPRISE usage billing.

Only the hosted HTTP/SSE MCP transport writes here (see mcp/server.py). Self-hosted
stdio usage has no org context and is never metered — it's free and unlimited by design.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, insert, select

from responsibleai.db.engine import DatabaseEngine, mcp_tool_calls


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _month_start() -> str:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()


def _days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


class McpUsageRepository:
    """Record and query MCP tool call volume per org."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def record_call(
        self,
        org_id: str | None,
        tool_name: str,
        tier: str,
        allowed: bool,
    ) -> None:
        """Log one MCP tool invocation. Fire-and-forget from the caller's perspective."""
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(mcp_tool_calls).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                tool_name=tool_name,
                tier=tier,
                timestamp=_now(),
                allowed=1 if allowed else 0,
            ))

    async def usage_this_month(self, org_id: str) -> dict[str, Any]:
        """Return this org's current billing-period MCP call volume."""
        cutoff = _month_start()
        stmt = (
            select(mcp_tool_calls)
            .where(mcp_tool_calls.c.org_id == org_id)
            .where(mcp_tool_calls.c.timestamp >= cutoff)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()

        total = len(rows)
        allowed = sum(1 for r in rows if r.allowed)
        blocked = total - allowed
        by_tool: dict[str, int] = {}
        for r in rows:
            by_tool[r.tool_name] = by_tool.get(r.tool_name, 0) + 1

        return {
            "org_id": org_id,
            "period_start": cutoff,
            "total_calls": total,
            "allowed_calls": allowed,
            "blocked_calls": blocked,
            "calls_by_tool": dict(sorted(by_tool.items(), key=lambda kv: -kv[1])),
        }

    async def count_since(self, org_id: str, since: str) -> int:
        """Count calls for *org_id* since an ISO8601 timestamp — used for quota checks."""
        stmt = (
            select(func.count())
            .select_from(mcp_tool_calls)
            .where(mcp_tool_calls.c.org_id == org_id)
            .where(mcp_tool_calls.c.timestamp >= since)
            .where(mcp_tool_calls.c.allowed == 1)
        )
        async with self._engine.raw.connect() as conn:
            result = (await conn.execute(stmt)).scalar()
        return result or 0

    async def top_orgs_by_volume(self, days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
        """Platform-wide MCP usage leaderboard — for the founder, not customer-facing."""
        cutoff = _days_ago(days)
        stmt = (
            select(
                mcp_tool_calls.c.org_id,
                func.count().label("calls"),
            )
            .where(mcp_tool_calls.c.timestamp >= cutoff)
            .where(mcp_tool_calls.c.org_id.is_not(None))
            .group_by(mcp_tool_calls.c.org_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [{"org_id": r.org_id, "calls": r.calls} for r in rows]
