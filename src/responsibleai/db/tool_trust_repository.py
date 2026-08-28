# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for the Tool Trust Network's persisted scores
(``tool_trust_scores``) -- see ``governance/tool_trust.py`` for how a
``ToolTrustScore`` is computed. This repository only ever persists
scores this module or an explicit admin action constructed; it never
computes one itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, tool_trust_scores
from responsibleai.governance.tool_trust import ToolTrustScore, ToolTrustTier


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_score(row: Any) -> ToolTrustScore:
    return ToolTrustScore(
        server_id=row.server_id,
        org_id=row.org_id,
        score=row.score,
        tier=ToolTrustTier(row.tier),
        has_been_scanned=bool(row.has_been_scanned),
        incident_count=row.incident_count,
        scan_report_id=row.scan_report_id,
        scan_summary=row.scan_summary,
        last_scanned_at=(
            datetime.fromisoformat(row.last_scanned_at) if row.last_scanned_at else None
        ),
        admin_override_tier=(
            ToolTrustTier(row.admin_override_tier) if row.admin_override_tier else None
        ),
        admin_override_by=row.admin_override_by,
        admin_override_reason=row.admin_override_reason,
        admin_override_at=(
            datetime.fromisoformat(row.admin_override_at) if row.admin_override_at else None
        ),
        updated_at=datetime.fromisoformat(row.updated_at),
    )


def _score_to_values(score: ToolTrustScore) -> dict[str, Any]:
    return {
        "server_id": score.server_id,
        "org_id": score.org_id,
        "score": score.score,
        "tier": score.tier.value,
        "has_been_scanned": 1 if score.has_been_scanned else 0,
        "incident_count": score.incident_count,
        "scan_report_id": score.scan_report_id,
        "scan_summary": score.scan_summary,
        "last_scanned_at": score.last_scanned_at.isoformat() if score.last_scanned_at else None,
        "admin_override_tier": score.admin_override_tier.value
        if score.admin_override_tier
        else None,
        "admin_override_by": score.admin_override_by,
        "admin_override_reason": score.admin_override_reason,
        "admin_override_at": score.admin_override_at.isoformat()
        if score.admin_override_at
        else None,
        "updated_at": _now(),
    }


class ToolTrustRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get(self, server_id: str) -> ToolTrustScore | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(tool_trust_scores).where(tool_trust_scores.c.server_id == server_id)
                )
            ).fetchone()
        return _row_to_score(row) if row else None

    async def upsert(self, score: ToolTrustScore) -> ToolTrustScore:
        """Insert-or-replace by ``server_id`` -- a fresh scan or a new
        admin override always fully supersedes whatever row existed,
        since ``ToolTrustScore`` is always constructed as a complete,
        self-consistent object (never a partial patch) by
        ``governance/tool_trust.py``. Plain select-then-update-or-insert
        rather than a dialect-specific ``ON CONFLICT`` clause, matching
        every other repository in this package -- one row per
        ``server_id``, written at most once per scan/override, so the
        extra round trip costs nothing that matters here."""
        values = _score_to_values(score)
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(tool_trust_scores.c.server_id).where(
                        tool_trust_scores.c.server_id == score.server_id
                    )
                )
            ).fetchone()
            if existing is not None:
                await conn.execute(
                    update(tool_trust_scores)
                    .where(tool_trust_scores.c.server_id == score.server_id)
                    .values(**{k: v for k, v in values.items() if k != "server_id"})
                )
            else:
                await conn.execute(insert(tool_trust_scores).values(**values))
        return score

    async def list_for_org(self, org_id: str) -> list[ToolTrustScore]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(tool_trust_scores).where(tool_trust_scores.c.org_id == org_id)
                )
            ).fetchall()
        return [_row_to_score(r) for r in rows]
