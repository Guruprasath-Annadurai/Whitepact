# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.roles import CloudRole


async def enroll_active_employee(
    repo: AdminGrantRepository,
    employee_id: str,
    role: CloudRole,
    permissions: list[str],
    policy_id: str,
) -> None:
    await repo.insert_employee(employee_id, str(role), permissions, status="active")
    await repo.upsert_policy(policy_id, active=True, requires_approver=False)
