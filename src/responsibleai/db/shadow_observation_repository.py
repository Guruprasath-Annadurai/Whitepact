# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable Sovereign shadow observations — never execution evidence."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from responsibleai.db.engine import DatabaseEngine, sovereign_shadow_observations
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.protocol import PROTOCOL_VERSION
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.shadow import ShadowObservation

SHADOW_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ShadowObservationRow:
    shadow_observation_id: str
    org_id: str
    environment: str | None
    agent_id: str | None
    action_type: str | None
    target_redacted: str | None
    policy_version: int | None
    shadow_disposition: str
    reason_codes: list[str]
    protocol_version: str
    schema_version: str
    diagnostic: dict[str, object]
    created_at: str


class ShadowObservationRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def save(
        self,
        ctx: SovereignContext,
        observation: ShadowObservation,
        *,
        agent_id: str | None = None,
        action_type: str | None = None,
        target: str | None = None,
        policy_version: int | None = None,
    ) -> ShadowObservationRow:
        shadow_id = f"shadow-{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        diagnostic = redact_for_debugger(
            {
                "labels": ["SHADOW", "SIMULATED", "NON_AUTHORITATIVE"],
                "notes": observation.notes,
            }
        )
        row = {
            "shadow_observation_id": shadow_id,
            "org_id": ctx.organization_id,
            "environment": ctx.environment,
            "agent_id": agent_id,
            "action_type": action_type,
            "target_redacted": redact_for_debugger({"target": target or ""}).get("target"),
            "policy_version": policy_version,
            "shadow_disposition": observation.decision,
            "reason_codes_json": json.dumps(observation.reason_codes),
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": SHADOW_SCHEMA_VERSION,
            "diagnostic_json": json.dumps(diagnostic),
            "created_at": now,
        }
        async with self._engine.raw.begin() as conn:
            await conn.execute(sovereign_shadow_observations.insert().values(**row))
        return ShadowObservationRow(
            shadow_observation_id=shadow_id,
            org_id=ctx.organization_id,
            environment=ctx.environment,
            agent_id=agent_id,
            action_type=action_type,
            target_redacted=(
                str(row["target_redacted"]) if row["target_redacted"] is not None else None
            ),
            policy_version=policy_version,
            shadow_disposition=observation.decision,
            reason_codes=observation.reason_codes,
            protocol_version=PROTOCOL_VERSION,
            schema_version=SHADOW_SCHEMA_VERSION,
            diagnostic=diagnostic,
            created_at=now,
        )

    async def get_for_org(self, org_id: str, shadow_id: str) -> ShadowObservationRow | None:
        async with self._engine.raw.connect() as conn:
            db_row = (
                await conn.execute(
                    select(sovereign_shadow_observations).where(
                        sovereign_shadow_observations.c.shadow_observation_id == shadow_id,
                        sovereign_shadow_observations.c.org_id == org_id,
                    )
                )
            ).fetchone()
        if db_row is None:
            return None
        if db_row.org_id != org_id:
            raise SovereignTenantIsolationError("shadow observation not found")
        return ShadowObservationRow(
            shadow_observation_id=db_row.shadow_observation_id,
            org_id=db_row.org_id,
            environment=db_row.environment,
            agent_id=db_row.agent_id,
            action_type=db_row.action_type,
            target_redacted=db_row.target_redacted,
            policy_version=db_row.policy_version,
            shadow_disposition=db_row.shadow_disposition,
            reason_codes=json.loads(db_row.reason_codes_json or "[]"),
            protocol_version=db_row.protocol_version,
            schema_version=db_row.schema_version,
            diagnostic=json.loads(db_row.diagnostic_json or "{}"),
            created_at=db_row.created_at,
        )
