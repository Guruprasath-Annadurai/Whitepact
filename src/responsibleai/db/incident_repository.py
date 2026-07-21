"""Async repository for persisted governance incident records.

Backs POST /api/incidents (manual/MCP-relayed incidents) and
POST /api/alerts/webhook (Prometheus Alertmanager → incident bridge) in
`responsibleai.dashboard.app`. Records are built by the shared, pure
`responsibleai.incidents.logic.build_incident_record` — this repository
only persists and queries the resulting dict, it does not compute any of
the severity/SLA/SIEM-classification logic itself.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert, select

from responsibleai.db.engine import DatabaseEngine, incidents


def _days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


class IncidentRepository:
    """Write and query the `incidents` table."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(
        self,
        record: dict[str, Any],
        *,
        org_id: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a record built by `build_incident_record`. Returns the
        stored row as a dict (same shape `get`/`list` return)."""
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(incidents).values(
                id=record["incident_id"],
                created_at=record["created_at"],
                org_id=org_id,
                source=record.get("source", "manual"),
                incident_type=record["incident_type"],
                severity=record["severity"],
                siem_event_type=record["siem_event_type"],
                model_name=record.get("model_name"),
                provider=record.get("provider"),
                description=record["description"],
                evidence_hash=record["evidence_hash"],
                evidence_keys=json.dumps(record.get("evidence_keys", [])),
                mitigated=int(bool(record.get("mitigated", False))),
                status=record["status"],
                sla_resolution_hours=record["sla_resolution_hours"],
                raw_payload=json.dumps(raw_payload) if raw_payload is not None else None,
            ))
        return await self.get(record["incident_id"])  # type: ignore[return-value]

    async def get(self, incident_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(incidents).where(incidents.c.id == incident_id)
            )).fetchone()
        return self._row_to_dict(row) if row else None

    async def list(
        self,
        org_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        days: int = 90,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        cutoff = _days_ago(days)
        stmt = (
            select(incidents)
            .where(incidents.c.created_at >= cutoff)
            .order_by(incidents.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if org_id:
            stmt = stmt.where(incidents.c.org_id == org_id)
        if severity:
            stmt = stmt.where(incidents.c.severity == severity)
        if status:
            stmt = stmt.where(incidents.c.status == status)

        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def cleanup(self, retention_days: int = 365) -> int:
        cutoff = _days_ago(retention_days)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(incidents).where(incidents.c.created_at < cutoff)
            )
        return result.rowcount

    @staticmethod
    def _row_to_dict(r: Any) -> dict[str, Any]:
        return {
            "incident_id": r.id,
            "created_at": r.created_at,
            "org_id": r.org_id,
            "source": r.source,
            "incident_type": r.incident_type,
            "severity": r.severity,
            "siem_event_type": r.siem_event_type,
            "model_name": r.model_name,
            "provider": r.provider,
            "description": r.description,
            "evidence_hash": r.evidence_hash,
            "evidence_keys": json.loads(r.evidence_keys) if r.evidence_keys else [],
            "mitigated": bool(r.mitigated),
            "status": r.status,
            "sla_resolution_hours": r.sla_resolution_hours,
        }
