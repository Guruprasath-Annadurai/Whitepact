# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable Privileged Attribution & Tamper-Evident Audit Logging."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import desc, insert, select

from responsibleai.db.engine import DatabaseEngine, iam_privileged_audit_log
from responsibleai.iam.models import PrivilegedAuthorizationResult, canonical_hash


class PrivilegedAttributionEngine:
    """Records immutable, tamper-evident audit logs of all privileged control-plane events."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def record_privileged_event(
        self,
        *,
        result: PrivilegedAuthorizationResult,
        target_resource_id: str | None = None,
        context_data: dict[str, Any] | None = None,
    ) -> str:
        """Atomically persist a privileged event linked into the cryptographic audit chain."""
        now = datetime.now(UTC).isoformat()
        record_id = f"iam_evt_{uuid.uuid4().hex}"

        async with self.db.raw.begin() as conn:
            # 1. Fetch previous event hash for this tenant to maintain hash chain
            prev_stmt = (
                select(iam_privileged_audit_log.c.entry_hash)
                .where(iam_privileged_audit_log.c.org_id == result.org_id)
                .order_by(desc(iam_privileged_audit_log.c.recorded_at))
                .limit(1)
            )
            prev_hash = (await conn.execute(prev_stmt)).scalar() or "0" * 64

            # 2. Compute canonical entry hash
            payload = {
                "record_id": record_id,
                "org_id": result.org_id,
                "principal_id": result.principal_id,
                "action": result.action.value,
                "risk_tier": result.risk_tier.value,
                "allowed": result.allowed,
                "target_resource_id": target_resource_id,
                "recorded_at": now,
                "prev_hash": prev_hash,
                "context": context_data or {},
            }
            entry_hash = canonical_hash(payload)

            # 3. Insert record
            await conn.execute(
                insert(iam_privileged_audit_log).values(
                    id=record_id,
                    org_id=result.org_id,
                    principal_id=result.principal_id,
                    action=result.action.value,
                    risk_tier=result.risk_tier.value,
                    allowed=1 if result.allowed else 0,
                    target_resource_id=target_resource_id,
                    recorded_at=now,
                    prev_hash=prev_hash,
                    entry_hash=entry_hash,
                    details_json=json.dumps(context_data or {}),
                )
            )

        return entry_hash
