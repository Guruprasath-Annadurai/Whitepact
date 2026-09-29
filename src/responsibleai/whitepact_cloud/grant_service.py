# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Issue and execute admin grants with DB-enforced lifecycle."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from responsibleai.whitepact_cloud.admin_grant import (
    MAX_ADMIN_GRANT_TTL_SECONDS,
    AdminGrantClaim,
    GrantDecision,
    issue_admin_grant_claim,
    verify_claim_signature,
)
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.roles import CloudRole, role_allows


class GrantExecutionError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class AdminGrantService:
    def __init__(self, repo: AdminGrantRepository, signing_key: bytes) -> None:
        self._repo = repo
        self._signing_key = signing_key

    async def issue_and_persist(
        self,
        *,
        employee_id: str,
        role: CloudRole,
        operation: str,
        provider: str,
        resource_target: str,
        permissions: list[str],
        policy_id: str,
        approval: GrantDecision,
        approved_by: str | None,
        ttl_seconds: int,
        founder_only_exception: bool = False,
    ) -> tuple[AdminGrantClaim, str]:
        if ttl_seconds <= 0 or ttl_seconds > MAX_ADMIN_GRANT_TTL_SECONDS:
            raise ValueError(f"ttl_seconds must be 1..{MAX_ADMIN_GRANT_TTL_SECONDS}")

        status = await self._repo.get_employee_status(employee_id)
        if status is not None and status != "active":
            raise GrantExecutionError("employee_not_active")

        claim, sig = issue_admin_grant_claim(
            employee_id=employee_id,
            role=role,
            operation=operation,
            provider=provider,
            resource_target=resource_target,
            permissions=permissions,
            policy_id=policy_id,
            approval=approval,
            approved_by=approved_by,
            ttl_seconds=ttl_seconds,
            signing_key=self._signing_key,
            founder_only_exception=founder_only_exception,
        )
        await self._repo.upsert_employee(employee_id, str(role), "active")
        await self._repo.persist_grant(claim, sig)
        return claim, sig

    async def verify_for_execution(
        self,
        grant_id: str,
        signature: str,
        *,
        expected_operation: str,
        expected_provider: str,
        expected_resource: str,
        required_permission: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        now = now or datetime.now(UTC)
        row = await self._repo.load_claim(grant_id)
        if not row:
            return {"ok": False, "reason": "not_found"}

        claim = AdminGrantClaim(
            grant_id=row["grant_id"],
            employee_id=row["employee_id"],
            role=CloudRole(row["role"]),
            operation=row["operation"],
            provider=row["provider"],
            resource_target=row["resource_target"],
            permissions=tuple(json_permissions(row["permissions_json"])),
            policy_id=row["policy_id"],
            approval_decision=GrantDecision.APPROVED,
            approved_by=row["approved_by"],
            expires_at=row["expires_at"],
            execution_id=row["execution_id"],
            audit_correlation_id=row["audit_correlation_id"],
            issued_at=row["issued_at"],
        )
        sig_ok = verify_claim_signature(claim, signature, self._signing_key)
        if not sig_ok:
            return {"ok": False, "reason": "bad_signature"}
        if row["revoked_at"] is not None:
            return {"ok": False, "reason": "revoked"}
        if row["consumed_at"] is not None:
            return {"ok": False, "reason": "replay"}
        if now >= claim.expires_at:
            return {"ok": False, "reason": "expired"}

        status = await self._repo.get_employee_status(claim.employee_id)
        if status != "active":
            return {"ok": False, "reason": "employee_not_active"}

        if claim.operation != expected_operation:
            return {"ok": False, "reason": "operation_mismatch"}
        if claim.provider != expected_provider:
            return {"ok": False, "reason": "provider_mismatch"}
        if claim.resource_target != expected_resource:
            return {"ok": False, "reason": "resource_mismatch"}
        if not role_allows(claim.role, required_permission):
            return {"ok": False, "reason": "permission_denied"}

        consumed = await self._repo.atomic_consume(grant_id, now=now)
        if not consumed:
            return {"ok": False, "reason": "consume_failed"}
        return {"ok": True, "execution_id": claim.execution_id}


def json_permissions(raw: str) -> list[str]:
    return list(json.loads(raw))
