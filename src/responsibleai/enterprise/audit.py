# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable enterprise security audit. Never stores secrets."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert

from responsibleai.db.engine import DatabaseEngine, enterprise_security_audit


def _now() -> str:
    return datetime.now(UTC).isoformat()


class EnterpriseAuditLog:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def record(
        self,
        *,
        action: str,
        actor_type: str,
        actor_id: str,
        target_type: str,
        result: str,
        org_id: str | None = None,
        environment_id: str | None = None,
        target_id: str | None = None,
        request_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        conn: Any | None = None,
    ) -> str:
        event_id = str(uuid.uuid4())
        safe = {
            k: v
            for k, v in (metadata or {}).items()
            if "token" not in k.lower() and "secret" not in k.lower() and "key" not in k.lower()
        }
        values = dict(
            event_id=event_id,
            org_id=org_id,
            environment_id=environment_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            timestamp=_now(),
            request_id=request_id,
            metadata_json=json.dumps(safe, separators=(",", ":")),
        )

        async def _write(connection: Any) -> None:
            await connection.execute(insert(enterprise_security_audit).values(**values))

        if conn is not None:
            await _write(conn)
            return event_id
        async with self._engine.raw.begin() as connection:
            await _write(connection)
        return event_id
