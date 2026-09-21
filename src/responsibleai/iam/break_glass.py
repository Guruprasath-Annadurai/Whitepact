# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Emergency Break-Glass Privileged Governance Service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, insert, update

from responsibleai.db.engine import DatabaseEngine, iam_break_glass_sessions
from responsibleai.iam.enums import BreakGlassCapability
from responsibleai.iam.errors import BreakGlassInvalidError
from responsibleai.iam.models import BreakGlassSession


class BreakGlassService:
    """Emergency break-glass access: scoped capabilities, incident-bound, short TTL, zero permanent privilege."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def initiate_break_glass(
        self,
        *,
        org_id: str,
        principal_id: str,
        incident_id: str,
        capabilities: list[BreakGlassCapability],
        justification: str,
        ttl_minutes: int = 60,
    ) -> BreakGlassSession:
        """Initiate an emergency break-glass session."""
        if not incident_id or not incident_id.strip() or len(incident_id.strip()) < 3:
            raise BreakGlassInvalidError(
                "Break-glass requires a valid, documented incident identifier."
            )

        if ttl_minutes <= 0 or ttl_minutes > 60:
            raise BreakGlassInvalidError(
                "Emergency break-glass TTL must be between 1 and 60 minutes (cannot exceed 60 minutes)."
            )

        if not capabilities:
            raise BreakGlassInvalidError("Break-glass requires explicitly declared capabilities.")

        for c in capabilities:
            if c not in BreakGlassCapability:
                raise BreakGlassInvalidError(f"Invalid break-glass capability: {c!r}")

        session_id = f"bg_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        expires_at = (now + timedelta(minutes=ttl_minutes)).isoformat()

        session = BreakGlassSession(
            id=session_id,
            org_id=org_id,
            principal_id=principal_id,
            incident_id=incident_id,
            capabilities=capabilities,
            justification=justification,
            status="ACTIVE",
            started_at=now.isoformat(),
            expires_at=expires_at,
        )

        async with self.db.raw.begin() as conn:
            await conn.execute(
                insert(iam_break_glass_sessions).values(
                    id=session.id,
                    org_id=session.org_id,
                    principal_id=session.principal_id,
                    incident_id=session.incident_id,
                    capabilities_json=json.dumps([c.value for c in session.capabilities]),
                    justification=session.justification,
                    status=session.status,
                    started_at=session.started_at,
                    expires_at=session.expires_at,
                    terminated_at=None,
                )
            )

        return session

    async def terminate_break_glass(self, *, org_id: str, session_id: str) -> bool:
        """Explicitly terminate an emergency session prior to TTL expiration."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            res = await conn.execute(
                update(iam_break_glass_sessions)
                .where(
                    and_(
                        iam_break_glass_sessions.c.id == session_id,
                        iam_break_glass_sessions.c.org_id == org_id,
                    )
                )
                .values(status="TERMINATED", terminated_at=now)
            )
            return (res.rowcount or 0) > 0
