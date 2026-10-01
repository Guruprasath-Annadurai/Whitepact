# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Employee enrollment — separate from administrative grant issuance."""

from __future__ import annotations

from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.roles import CloudRole, role_allows


class EnrollmentError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class EmployeeEnrollmentService:
    def __init__(self, repo: AdminGrantRepository) -> None:
        self._repo = repo

    async def enroll(
        self,
        employee_id: str,
        role: CloudRole,
        authorized_permissions: list[str],
    ) -> None:
        for perm in authorized_permissions:
            if not role_allows(role, perm):
                raise EnrollmentError(f"role {role} cannot authorize {perm}")

        existing = await self._repo.get_employee_record(employee_id)
        if existing is not None:
            if existing["status"] in ("terminated", "suspended"):
                raise EnrollmentError("employee_not_eligible_for_reactivation_via_enroll")
            raise EnrollmentError("employee_already_enrolled")

        await self._repo.insert_employee(
            employee_id,
            str(role),
            authorized_permissions,
            status="active",
        )
