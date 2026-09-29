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
    cloud_admin_policies,
    cloud_employees,
)
from responsibleai.whitepact_cloud.admin_grant import (
    AdminGrantClaim,
    GrantDecision,
    verify_claim_signature,
)
from responsibleai.whitepact_cloud.roles import CloudRole, is_sensitive_permission, role_allows


class AdminGrantRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def insert_employee(
        self,
        employee_id: str,
        role: str,
        authorized_permissions: list[str],
        *,
        status: str = "active",
    ) -> None:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(cloud_employees).values(
                    employee_id=employee_id,
                    role=role,
                    status=status,
                    authorized_permissions_json=json.dumps(authorized_permissions),
                    updated_at=now,
                )
            )

    async def get_employee_record(self, employee_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                (
                    await conn.execute(
                        select(cloud_employees).where(cloud_employees.c.employee_id == employee_id)
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None

    async def get_employee_status(self, employee_id: str) -> str | None:
        record = await self.get_employee_record(employee_id)
        return record["status"] if record else None

    async def set_employee_status(self, employee_id: str, status: str) -> None:
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_employees)
                .where(cloud_employees.c.employee_id == employee_id)
                .values(status=status, updated_at=now)
            )

    async def terminate_local_access(self, employee_id: str) -> None:
        """Fail-closed local revocation: terminated + all grants revoked atomically."""
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_employees)
                .where(cloud_employees.c.employee_id == employee_id)
                .values(status="terminated", updated_at=now)
            )
            await conn.execute(
                text(
                    """
                    UPDATE cloud_admin_grant_state AS s
                    SET revoked_at = :now, updated_at = :now
                    FROM cloud_admin_grant_claims AS c
                    WHERE s.grant_id = c.grant_id
                      AND c.employee_id = :employee_id
                      AND s.revoked_at IS NULL
                    """
                ),
                {"employee_id": employee_id, "now": now},
            )

    async def upsert_policy(
        self, policy_id: str, *, active: bool = True, requires_approver: bool = False
    ) -> None:
        async with self._engine.raw.begin() as conn:
            existing = await conn.execute(
                select(cloud_admin_policies.c.policy_id).where(
                    cloud_admin_policies.c.policy_id == policy_id
                )
            )
            if existing.first():
                await conn.execute(
                    update(cloud_admin_policies)
                    .where(cloud_admin_policies.c.policy_id == policy_id)
                    .values(active=active, requires_approver=requires_approver)
                )
            else:
                await conn.execute(
                    insert(cloud_admin_policies).values(
                        policy_id=policy_id,
                        active=active,
                        requires_approver=requires_approver,
                    )
                )

    async def is_policy_active(self, policy_id: str) -> bool:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(cloud_admin_policies.c.active).where(
                        cloud_admin_policies.c.policy_id == policy_id
                    )
                )
            ).first()
            if not row:
                return False
            return bool(row[0])

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
                insert(cloud_admin_grant_state).values(
                    grant_id=claim.grant_id, updated_at=datetime.now(UTC)
                )
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
            result = await conn.execute(
                text(
                    """
                    UPDATE cloud_admin_grant_state AS s
                    SET revoked_at = :now, updated_at = :now
                    FROM cloud_admin_grant_claims AS c
                    WHERE s.grant_id = c.grant_id
                      AND c.employee_id = :employee_id
                      AND s.revoked_at IS NULL
                    """
                ),
                {"employee_id": employee_id, "now": now},
            )
            return result.rowcount or 0

    async def verify_and_consume_transactional(
        self,
        grant_id: str,
        signature: str,
        signing_key: bytes,
        *,
        expected_operation: str,
        expected_provider: str,
        expected_resource: str,
        required_permission: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT c.*, s.revoked_at, s.consumed_at,
                               e.status AS employee_status,
                               e.authorized_permissions_json,
                               p.active AS policy_active,
                               p.requires_approver
                        FROM cloud_admin_grant_claims AS c
                        INNER JOIN cloud_admin_grant_state AS s ON s.grant_id = c.grant_id
                        INNER JOIN cloud_employees AS e ON e.employee_id = c.employee_id
                        LEFT JOIN cloud_admin_policies AS p ON p.policy_id = c.policy_id
                        WHERE c.grant_id = :grant_id
                        FOR UPDATE OF s, e
                        """
                        ),
                        {"grant_id": grant_id},
                    )
                )
                .mappings()
                .first()
            )

            if not row:
                return {"ok": False, "reason": "not_found"}

            claim = AdminGrantClaim(
                grant_id=row["grant_id"],
                employee_id=row["employee_id"],
                role=CloudRole(row["role"]),
                operation=row["operation"],
                provider=row["provider"],
                resource_target=row["resource_target"],
                permissions=tuple(json.loads(row["permissions_json"])),
                policy_id=row["policy_id"],
                approval_decision=GrantDecision.APPROVED,
                approved_by=row["approved_by"],
                expires_at=row["expires_at"],
                execution_id=row["execution_id"],
                audit_correlation_id=row["audit_correlation_id"],
                issued_at=row["issued_at"],
            )

            if not verify_claim_signature(claim, signature, signing_key):
                return {"ok": False, "reason": "bad_signature"}
            if row["revoked_at"] is not None:
                return {"ok": False, "reason": "revoked"}
            if row["consumed_at"] is not None:
                return {"ok": False, "reason": "replay"}
            if now >= claim.expires_at:
                return {"ok": False, "reason": "expired"}
            if row["employee_status"] != "active":
                return {"ok": False, "reason": "employee_not_active"}
            if row["policy_active"] is not True:
                return {"ok": False, "reason": "policy_inactive"}

            employee_perms = set(json.loads(row["authorized_permissions_json"]))
            grant_perms = set(claim.permissions)
            if required_permission not in grant_perms:
                return {"ok": False, "reason": "permission_not_in_grant"}
            if required_permission not in employee_perms:
                return {"ok": False, "reason": "permission_not_authorized_for_employee"}
            if not role_allows(claim.role, required_permission):
                return {"ok": False, "reason": "permission_denied"}

            if row["requires_approver"] or any(is_sensitive_permission(p) for p in grant_perms):
                if not claim.approved_by:
                    return {"ok": False, "reason": "approval_required"}

            if claim.operation != expected_operation:
                return {"ok": False, "reason": "operation_mismatch"}
            if claim.provider != expected_provider:
                return {"ok": False, "reason": "provider_mismatch"}
            if claim.resource_target != expected_resource:
                return {"ok": False, "reason": "resource_mismatch"}

            consumed = (
                await conn.execute(
                    text(
                        """
                        UPDATE cloud_admin_grant_state
                        SET consumed_at = :now, updated_at = :now
                        WHERE grant_id = :grant_id
                          AND revoked_at IS NULL
                          AND consumed_at IS NULL
                        RETURNING grant_id
                        """
                    ),
                    {"grant_id": grant_id, "now": now},
                )
            ).first()
            if not consumed:
                return {"ok": False, "reason": "consume_failed"}

            return {"ok": True, "execution_id": claim.execution_id}

    async def load_claim(self, grant_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                (
                    await conn.execute(
                        select(
                            cloud_admin_grant_claims,
                            cloud_admin_grant_state.c.revoked_at,
                            cloud_admin_grant_state.c.consumed_at,
                        )
                        .select_from(
                            cloud_admin_grant_claims.join(
                                cloud_admin_grant_state,
                                cloud_admin_grant_claims.c.grant_id
                                == cloud_admin_grant_state.c.grant_id,
                            )
                        )
                        .where(cloud_admin_grant_claims.c.grant_id == grant_id)
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None
