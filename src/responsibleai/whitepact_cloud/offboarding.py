# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Employee offboarding with confirmed per-step outcomes (no false completion)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from sqlalchemy import insert, update

from responsibleai.db.engine import DatabaseEngine, cloud_offboarding_runs, cloud_offboarding_steps
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository


class StepStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass
class OffboardingStepResult:
    step_name: str
    status: StepStatus
    error: str | None = None


@dataclass
class OffboardingState:
    run_id: str
    employee_id: str
    steps: list[OffboardingStepResult] = field(default_factory=list)
    complete: bool = False
    partial: bool = False


class IdentityRevocationPort(Protocol):
    def disable_identity(self, employee_id: str) -> bool: ...

    def revoke_sessions(self, employee_id: str) -> bool: ...

    def revoke_provider_permissions(self, employee_id: str) -> bool: ...

    def revoke_api_credentials(self, employee_id: str) -> bool: ...


class OffboardingService:
    STEPS = (
        "disable_identity",
        "revoke_sessions",
        "revoke_grants",
        "revoke_provider_permissions",
        "revoke_api_credentials",
    )

    def __init__(
        self,
        engine: DatabaseEngine,
        grants: AdminGrantRepository,
        integrations: IdentityRevocationPort,
    ) -> None:
        self._engine = engine
        self._grants = grants
        self._integrations = integrations

    async def run(self, employee_id: str, *, max_attempts: int = 3) -> OffboardingState:
        run_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(cloud_offboarding_runs).values(
                    run_id=run_id,
                    employee_id=employee_id,
                    status="in_progress",
                    started_at=now,
                )
            )

        state = OffboardingState(run_id=run_id, employee_id=employee_id)
        for step_name in self.STEPS:
            result = await self._run_step(run_id, employee_id, step_name, max_attempts=max_attempts)
            state.steps.append(result)
            if result.status == StepStatus.FAILED:
                state.partial = True
                await self._finalize_run(run_id, "partial")
                return state

        state.complete = True
        await self._finalize_run(run_id, "complete")
        return state

    async def _run_step(
        self,
        run_id: str,
        employee_id: str,
        step_name: str,
        *,
        max_attempts: int,
    ) -> OffboardingStepResult:
        step_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(cloud_offboarding_steps).values(
                    step_id=step_id,
                    run_id=run_id,
                    step_name=step_name,
                    status=StepStatus.PENDING.value,
                    attempts=0,
                )
            )

        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            ok, err = await self._execute_step(employee_id, step_name)
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(cloud_offboarding_steps)
                    .where(cloud_offboarding_steps.c.step_id == step_id)
                    .values(attempts=attempt, last_error=err)
                )
            if ok:
                async with self._engine.raw.begin() as conn:
                    await conn.execute(
                        update(cloud_offboarding_steps)
                        .where(cloud_offboarding_steps.c.step_id == step_id)
                        .values(
                            status=StepStatus.SUCCEEDED.value,
                            completed_at=datetime.now(UTC),
                        )
                    )
                return OffboardingStepResult(step_name=step_name, status=StepStatus.SUCCEEDED)
            last_error = err or "unknown_error"

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_steps)
                .where(cloud_offboarding_steps.c.step_id == step_id)
                .values(
                    status=StepStatus.FAILED.value,
                    completed_at=datetime.now(UTC),
                    last_error=last_error,
                )
            )
        return OffboardingStepResult(step_name=step_name, status=StepStatus.FAILED, error=last_error)

    async def _execute_step(self, employee_id: str, step_name: str) -> tuple[bool, str | None]:
        if step_name == "disable_identity":
            ok = self._integrations.disable_identity(employee_id)
            if ok:
                await self._grants.set_employee_status(employee_id, "terminated")
            return ok, None if ok else "identity_disable_failed"
        if step_name == "revoke_sessions":
            ok = self._integrations.revoke_sessions(employee_id)
            return ok, None if ok else "session_revoke_failed"
        if step_name == "revoke_grants":
            count = await self._grants.revoke_all_for_employee(employee_id)
            return True, None if count >= 0 else "grant_revoke_failed"
        if step_name == "revoke_provider_permissions":
            ok = self._integrations.revoke_provider_permissions(employee_id)
            return ok, None if ok else "provider_revoke_failed"
        if step_name == "revoke_api_credentials":
            ok = self._integrations.revoke_api_credentials(employee_id)
            return ok, None if ok else "api_credential_revoke_failed"
        return False, "unknown_step"

    async def _finalize_run(self, run_id: str, status: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_runs)
                .where(cloud_offboarding_runs.c.run_id == run_id)
                .values(status=status, completed_at=datetime.now(UTC))
            )


def offboarding_complete(state: OffboardingState) -> bool:
    return state.complete and all(s.status == StepStatus.SUCCEEDED for s in state.steps)
