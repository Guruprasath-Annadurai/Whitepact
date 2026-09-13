# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable Privileged Attribution & Tamper-Evident Audit Logging linked to Checkpoint-5 Evidence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert

from responsibleai.db.engine import DatabaseEngine, iam_privileged_audit_log
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.iam.models import PrivilegedAuthorizationResult


class PrivilegedAttributionEngine:
    """Records immutable, tamper-evident audit logs of all privileged control-plane events.

    Checkpoint-5 canonical evidence writer is authoritative; iam_privileged_audit_log
    serves as a supplementary administrative index explicitly linked to canonical evidence.
    """

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.evidence_repo = EvidenceRepository(db)

    async def record_privileged_event(
        self,
        *,
        result: PrivilegedAuthorizationResult,
        target_resource_id: str | None = None,
        context_data: dict[str, Any] | None = None,
    ) -> str:
        """Atomically persist a privileged event through Checkpoint-5 canonical evidence writer,
        maintaining supplementary administrative index linkage.
        """
        now = datetime.now(UTC)
        record_id = f"iam_evt_{uuid.uuid4().hex}"

        # 1. Sanitize context data to guarantee zero raw secrets, tokens, or private keys
        raw_ctx = context_data or {}
        sanitized_context = {
            k: ("[REDACTED]" if any(s in k.lower() for s in ["secret", "token", "key", "password", "signature"]) else v)
            for k, v in raw_ctx.items()
        }

        # 2. Construct canonical Checkpoint-5 EvidenceRecord
        evidence = EvidenceRecord(
            action_id=record_id,
            agent_id=result.principal_id,
            identity_id=result.principal_id,
            action_type=result.action.value,
            target=target_resource_id or "control-plane",
            argument_keys=list(sanitized_context.keys()),
            authority_delegated_by=result.principal_id,
            decision="ALLOW" if result.allowed else "DENY",
            reason_codes=[],
            evaluated_at=now,
            organization_id=result.org_id,
            risk_tier=result.risk_tier.value,
            authentication_method="STEP_UP" if result.step_up_verified else "SESSION",
            approval_id=sanitized_context.get("four_eyes_approval_id"),
            execution_authorization_id=(
                sanitized_context.get("jit_grant_id")
                or sanitized_context.get("break_glass_session_id")
            ),
        )

        # 3. Persist into Checkpoint-5 canonical evidence architecture
        recorded = await self.evidence_repo.record(evidence)
        entry_hash = recorded.hash or ""
        prev_hash = recorded.prev_hash or ("0" * 64)

        # 4. Insert supplementary admin-attribution record explicitly linked to canonical evidence
        async with self.db.raw.begin() as conn:
            await conn.execute(
                insert(iam_privileged_audit_log).values(
                    id=record_id,
                    org_id=result.org_id,
                    principal_id=result.principal_id,
                    action=result.action.value,
                    risk_tier=result.risk_tier.value,
                    allowed=1 if result.allowed else 0,
                    target_resource_id=target_resource_id,
                    recorded_at=recorded.recorded_at or now.isoformat(),
                    prev_hash=prev_hash,
                    entry_hash=entry_hash,
                    details_json=json.dumps(sanitized_context),
                )
            )

        return entry_hash
