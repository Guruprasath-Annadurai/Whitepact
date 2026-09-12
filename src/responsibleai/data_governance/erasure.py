# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Data Erasure State Machine & Verification Engine for WhitePact Phase 5.

Guarantees:
- Explicit state machine: REQUESTED -> VALIDATED -> IN_PROGRESS -> COMPLETED / FAILED / BLOCKED_BY_HOLD.
- Zero False Completion: Never acknowledges COMPLETED if eligible data remains or if blocked by hold.
- Durable lifecycle audit record in data_lifecycle_requests.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    data_lifecycle_requests,
    eval_runs,
    incidents,
    mcp_tool_calls,
    org_api_keys,
    token_usage,
    tool_trust_scores,
    web_sessions,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class ErasureStatus(StrEnum):
    REQUESTED = "REQUESTED"
    VALIDATED = "VALIDATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED_BY_HOLD = "BLOCKED_BY_HOLD"


class ErasureError(Exception):
    """Base exception for data erasure failures."""


class FalseErasureCompletionError(ErasureError):
    """Raised if an erasure attempts to report COMPLETED when residual data exists."""


@dataclass(frozen=True)
class LifecycleRequest:
    id: str
    org_id: str
    request_type: str
    status: ErasureStatus
    requested_at: str
    completed_at: str | None
    requested_by: str
    details: dict[str, Any]
    verification_status: str | None


class DataErasureManager:
    """Governs the verified data erasure lifecycle."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._legal_hold = LegalHoldManager(engine)

    async def request_erasure(
        self,
        org_id: str,
        requested_by: str,
        reason: str,
    ) -> LifecycleRequest:
        """Register a new formal erasure request in REQUESTED state."""
        req_id = str(uuid.uuid4())
        now = _now()
        details = {"reason": reason, "history": [{"status": ErasureStatus.REQUESTED.value, "timestamp": now}]}

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(data_lifecycle_requests).values(
                    id=req_id,
                    org_id=org_id,
                    request_type="ERASURE",
                    status=ErasureStatus.REQUESTED.value,
                    requested_at=now,
                    completed_at=None,
                    requested_by=requested_by,
                    details_json=json.dumps(details),
                    verification_status=None,
                )
            )

        return LifecycleRequest(
            id=req_id,
            org_id=org_id,
            request_type="ERASURE",
            status=ErasureStatus.REQUESTED,
            requested_at=now,
            completed_at=None,
            requested_by=requested_by,
            details=details,
            verification_status=None,
        )

    async def execute_erasure(self, request_id: str) -> LifecycleRequest:
        """Executes a requested erasure through validation, purging, and verification."""
        # 1. Fetch request
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(data_lifecycle_requests).where(data_lifecycle_requests.c.id == request_id)
                )
            ).fetchone()

        if not row:
            raise ErasureError(f"Erasure request {request_id} not found")

        org_id = row.org_id
        details = json.loads(row.details_json) if row.details_json else {}

        # 2. Check legal holds
        if await self._legal_hold.is_held(org_id):
            now = _now()
            details["hold_blocked_at"] = now
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(data_lifecycle_requests)
                    .where(data_lifecycle_requests.c.id == request_id)
                    .values(
                        status=ErasureStatus.BLOCKED_BY_HOLD.value,
                        details_json=json.dumps(details),
                        verification_status="BLOCKED_BY_HOLD",
                    )
                )
            return LifecycleRequest(
                id=request_id,
                org_id=org_id,
                request_type=row.request_type,
                status=ErasureStatus.BLOCKED_BY_HOLD,
                requested_at=row.requested_at,
                completed_at=None,
                requested_by=row.requested_by,
                details=details,
                verification_status="BLOCKED_BY_HOLD",
            )

        # 3. Transition to IN_PROGRESS and purge data
        now = _now()
        deleted_counts: dict[str, int] = {}
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(data_lifecycle_requests)
                .where(data_lifecycle_requests.c.id == request_id)
                .values(status=ErasureStatus.IN_PROGRESS.value)
            )

            # Purge sessions
            r1 = await conn.execute(delete(web_sessions).where(web_sessions.c.org_id == org_id))
            deleted_counts["web_sessions"] = r1.rowcount or 0

            # Purge api keys
            r2 = await conn.execute(delete(org_api_keys).where(org_api_keys.c.org_id == org_id))
            deleted_counts["org_api_keys"] = r2.rowcount or 0

            # Purge incidents
            r3 = await conn.execute(delete(incidents).where(incidents.c.org_id == org_id))
            deleted_counts["incidents"] = r3.rowcount or 0

            # Purge tool trust scores
            r4 = await conn.execute(delete(tool_trust_scores).where(tool_trust_scores.c.org_id == org_id))
            deleted_counts["tool_trust_scores"] = r4.rowcount or 0

            # Purge eval runs
            r5 = await conn.execute(delete(eval_runs).where(eval_runs.c.org_id == org_id))
            deleted_counts["eval_runs"] = r5.rowcount or 0

            # Purge token usage
            r6 = await conn.execute(delete(token_usage).where(token_usage.c.org_id == org_id))
            deleted_counts["token_usage"] = r6.rowcount or 0

            # Purge tool calls
            r7 = await conn.execute(delete(mcp_tool_calls).where(mcp_tool_calls.c.org_id == org_id))
            deleted_counts["mcp_tool_calls"] = r7.rowcount or 0

        # 4. Independent verification: ensure 0 residual rows in purged tables
        residual_counts: dict[str, int] = {}
        async with self._engine.raw.connect() as conn:
            for tbl, name in [
                (web_sessions, "web_sessions"),
                (org_api_keys, "org_api_keys"),
                (incidents, "incidents"),
                (tool_trust_scores, "tool_trust_scores"),
                (eval_runs, "eval_runs"),
                (token_usage, "token_usage"),
                (mcp_tool_calls, "mcp_tool_calls"),
            ]:
                count = (
                    await conn.execute(
                        select(tbl).where(tbl.c.org_id == org_id)
                    )
                ).fetchall()
                if count:
                    residual_counts[name] = len(count)

        completed_at = _now()
        if residual_counts:
            # Verification failed! Record FAILED, never COMPLETED!
            details["residual_detected"] = residual_counts
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(data_lifecycle_requests)
                    .where(data_lifecycle_requests.c.id == request_id)
                    .values(
                        status=ErasureStatus.FAILED.value,
                        details_json=json.dumps(details),
                        verification_status="VERIFICATION_FAILED_RESIDUAL_DATA",
                    )
                )
            raise FalseErasureCompletionError(
                f"Erasure verification failed for {org_id}: residual rows {residual_counts}"
            )

        # 5. Success! Verification passed
        details["purged_records"] = deleted_counts
        details["verified_at"] = completed_at
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(data_lifecycle_requests)
                .where(data_lifecycle_requests.c.id == request_id)
                .values(
                    status=ErasureStatus.COMPLETED.value,
                    completed_at=completed_at,
                    details_json=json.dumps(details),
                    verification_status="VERIFIED_ZERO_RESIDUE",
                )
            )

        return LifecycleRequest(
            id=request_id,
            org_id=org_id,
            request_type=row.request_type,
            status=ErasureStatus.COMPLETED,
            requested_at=row.requested_at,
            completed_at=completed_at,
            requested_by=row.requested_by,
            details=details,
            verification_status="VERIFIED_ZERO_RESIDUE",
        )
