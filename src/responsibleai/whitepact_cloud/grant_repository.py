# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable admin grant claims and transactional lifecycle state."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, text, update

from responsibleai.db.engine import (
    DatabaseEngine,
    cloud_admin_grant_claims,
    cloud_admin_grant_state,
    cloud_employees,
)
from responsibleai.whitepact_cloud.admin_grant import AdminGrantClaim


class AdminGrantRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def upsert_employee(self, employee_id: str, role: str, status: str = "active") -> None:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            existing = await conn.execute(
                select(cloud_employees.c.employee_id).where(cloud_employees.c.employee_id == employee_id)
            )
            if existing.first():
                await conn.execute(
                    update(cloud_employees)
                    .where(cloud_employees.c.employee_id == employee_id)
                    .values(role=role, status=status, updated_at=now)
                )
            else:
                await conn.execute(
                    insert(cloud_employees).values(
                        employee_id=employee_id,
                        role=role,
                        status=status,
                        updated_at=now,
                    )
                )

    async def get_employee_status(self, employee_id: str) -> str | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(cloud_employees.c.status).where(cloud_employees.c.employee_id == employee_id)
                )
            ).first()
            return row[0] if row else None

    async def set_employee_status(self, employee_id: str, status: str) -> None:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_employees)
                .where(cloud_employees.c.employee_id == employee_id)
                .values(status=status, updated_at=now)
            )

    async def persist_grant(self, claim: AdminGrantClaim, signature: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(cloud_admin_grant_claims).values(
                    grant_id=claim.grant_id,
                    employee_id=claim.employee_id,
                    role=str(claim.role),
                    operation=claim.operation,
                    provider=claim.provider,
                    resource_target=claim.resource_target,
                    permissions_json=json.dumps(list(claim.permissions)),
                    policy_id=claim.policy_id,
                    approved_by=claim.approved_by,
                    execution_id=claim.execution_id,
                    audit_correlation_id=claim.audit_correlation_id,
                    signature_hmac=signature,
                    issued_at=claim.issued_at,
                    expires_at=claim.expires_at,
                )
            )
            await conn.execute(
                insert(cloud_admin_grant_state).values(grant_id=claim.grant_id, updated_at=datetime.now(UTC))
            )

    async def revoke_grant(self, grant_id: str) -> bool:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(cloud_admin_grant_state)
                .where(
                    cloud_admin_grant_state.c.grant_id == grant_id,
                    cloud_admin_grant_state.c.revoked_at.is_(None),
                )
                .values(revoked_at=now, updated_at=now)
            )
            return result.rowcount > 0

    async def revoke_all_for_employee(self, employee_id: str) -> int:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            subq = select(cloud_admin_grant_claims.c.grant_id).where(
                cloud_admin_grant_claims.c.employee_id == employee_id
            )
            result = await conn.execute(
                update(cloud_admin_grant_state)
                .where(
                    cloud_admin_grant_state.c.grant_id.in_(subq),
                    cloud_admin_grant_state.c.revoked_at.is_(None),
                )
                .values(revoked_at=now, updated_at=now)
            )
            return result.rowcount or 0

    async def atomic_consume(
        self,
        grant_id: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Single-use consumption — returns True only for the winning worker."""
        now = now or datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    UPDATE cloud_admin_grant_state AS s
                    SET consumed_at = :now, updated_at = :now
                    FROM cloud_admin_grant_claims AS c
                    WHERE s.grant_id = c.grant_id
                      AND s.grant_id = :grant_id
                      AND s.revoked_at IS NULL
                      AND s.consumed_at IS NULL
                      AND c.expires_at > :now
                    RETURNING s.grant_id
                    """
                ),
                {"grant_id": grant_id, "now": now},
            )
            return result.first() is not None

    async def load_claim(self, grant_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(
                        cloud_admin_grant_claims,
                        cloud_admin_grant_state.c.revoked_at,
                        cloud_admin_grant_state.c.consumed_at,
                    )
                    .select_from(
                        cloud_admin_grant_claims.join(
                            cloud_admin_grant_state,
                            cloud_admin_grant_claims.c.grant_id == cloud_admin_grant_state.c.grant_id,
                        )
                    )
                    .where(cloud_admin_grant_claims.c.grant_id == grant_id)
                )
            ).mappings().first()
            return dict(row) if row else None
