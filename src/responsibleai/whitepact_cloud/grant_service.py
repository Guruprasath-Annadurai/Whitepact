# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Issue and execute admin grants with DB-enforced lifecycle."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from responsibleai.whitepact_cloud.admin_grant import (
    MAX_ADMIN_GRANT_TTL_SECONDS,
    AdminGrantClaim,
    GrantDecision,
    issue_admin_grant_claim,
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

        employee = await self._repo.get_employee_record(employee_id)
        if employee is None:
            raise GrantExecutionError("employee_not_enrolled")
        if employee["status"] != "active":
            raise GrantExecutionError("employee_not_active")

        if str(role) != employee["role"]:
            raise GrantExecutionError("role_mismatch")

        authorized = set(json.loads(employee["authorized_permissions_json"]))
        for perm in permissions:
            if perm not in authorized:
                raise GrantExecutionError("permission_not_authorized_for_employee")
            if not role_allows(role, perm):
                raise GrantExecutionError("permission_denied")

        if not await self._repo.is_policy_active(policy_id):
            raise GrantExecutionError("policy_inactive")

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
        return await self._repo.verify_and_consume_transactional(
            grant_id,
            signature,
            self._signing_key,
            expected_operation=expected_operation,
            expected_provider=expected_provider,
            expected_resource=expected_resource,
            required_permission=required_permission,
            now=now,
        )
