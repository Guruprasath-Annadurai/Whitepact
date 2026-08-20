"""Async repository for persisted Outcome Observations
(``governance_outcomes``) -- see ``governance/outcome.py`` for what
constructs an ``OutcomeRecord`` in the first place. Append-only, same
"evidence that could be edited after the fact isn't evidence" reasoning
``EvidenceRepository`` states for its own table -- no ``update``/
``delete`` here either.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select

from responsibleai.db.engine import DatabaseEngine, governance_outcomes
from responsibleai.governance.outcome import OutcomeRecord, OutcomeStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> OutcomeRecord:
    return OutcomeRecord(
        outcome_id=row.id,
        evidence_id=row.evidence_id,
        action_id=row.action_id,
        organization_id=row.org_id,
        status=OutcomeStatus(row.status),
        result_summary=row.result_summary,
        observed_at=datetime.fromisoformat(row.observed_at),
    )


class OutcomeRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def record(self, outcome: OutcomeRecord) -> OutcomeRecord:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_outcomes).values(
                    id=outcome.outcome_id,
                    evidence_id=outcome.evidence_id,
                    action_id=outcome.action_id,
                    org_id=outcome.organization_id,
                    status=outcome.status.value,
                    result_summary=outcome.result_summary,
                    observed_at=outcome.observed_at.isoformat(),
                )
            )
        return outcome

    async def get_for_evidence(self, evidence_id: str) -> OutcomeRecord | None:
        """The most recently observed outcome for one evidence entry --
        normally exactly zero or one row (a permit is consumed once),
        but a resumed-after-approval or retried flow could in principle
        report more than one; the latest observation wins for
        reconciliation purposes."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_outcomes)
                    .where(governance_outcomes.c.evidence_id == evidence_id)
                    .order_by(governance_outcomes.c.observed_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _row_to_record(row) if row else None
