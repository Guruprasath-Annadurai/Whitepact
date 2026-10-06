# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Employee offboarding — local fail-closed first, external revocations confirmed separately."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from sqlalchemy import insert, update

from responsibleai.db.engine import DatabaseEngine, cloud_offboarding_runs, cloud_offboarding_steps
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository

LOCAL_STEP = "local_fail_closed"
EXTERNAL_STEPS = (
    "revoke_sessions",
    "revoke_provider_permissions",
    "revoke_api_credentials",
    "disable_identity_external",
)


class StepStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNRESOLVED = "unresolved"


@dataclass
class OffboardingStepResult:
    step_name: str
    status: StepStatus
    error: str | None = None
    attempts: int = 0


@dataclass
class OffboardingState:
    run_id: str
    employee_id: str
    steps: list[OffboardingStepResult] = field(default_factory=list)
    local_revoked: bool = False
    complete: bool = False
    partial: bool = False
    external_unresolved: bool = False


class IdentityRevocationPort(Protocol):
    def disable_identity(self, employee_id: str) -> bool: ...

    def revoke_sessions(self, employee_id: str) -> bool: ...

    def revoke_provider_permissions(self, employee_id: str) -> bool: ...

    def revoke_api_credentials(self, employee_id: str) -> bool: ...


class OffboardingService:
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

        local = await self._run_local_fail_closed(run_id, employee_id)
        state.steps.append(local)
        state.local_revoked = local.status == StepStatus.SUCCEEDED
        if not state.local_revoked:
            state.partial = True
            await self._finalize_run(run_id, "partial_local_failed")
            return state

        for step_name in EXTERNAL_STEPS:
            result = await self._run_external_step(
                run_id, employee_id, step_name, max_attempts=max_attempts
            )
            state.steps.append(result)
            if result.status != StepStatus.SUCCEEDED:
                state.partial = True
                state.external_unresolved = True

        if state.external_unresolved:
            state.complete = False
            await self._finalize_run(run_id, "partial_external_unresolved")
        else:
            state.complete = True
            await self._finalize_run(run_id, "complete")
        return state

    async def _run_local_fail_closed(self, run_id: str, employee_id: str) -> OffboardingStepResult:
        step_id = str(uuid.uuid4())
        await self._insert_step(run_id, step_id, LOCAL_STEP)
        try:
            await self._grants.terminate_local_access(employee_id)
            await self._mark_step_succeeded(step_id)
            return OffboardingStepResult(step_name=LOCAL_STEP, status=StepStatus.SUCCEEDED)
        except Exception as exc:
            await self._mark_step_failed(step_id, str(exc))
            return OffboardingStepResult(
                step_name=LOCAL_STEP, status=StepStatus.FAILED, error=str(exc)
            )

    async def _run_external_step(
        self,
        run_id: str,
        employee_id: str,
        step_name: str,
        *,
        max_attempts: int,
    ) -> OffboardingStepResult:
        step_id = str(uuid.uuid4())
        await self._insert_step(run_id, step_id, step_name)
        last_error: str | None = None
        for attempt in range(1, max_attempts + 1):
            ok, err = self._call_external(employee_id, step_name)
            await self._record_attempt(step_id, attempt, err)
            if ok:
                await self._mark_step_succeeded(step_id)
                return OffboardingStepResult(
                    step_name=step_name, status=StepStatus.SUCCEEDED, attempts=attempt
                )
            last_error = err or "external_revocation_failed"

        await self._mark_step_unresolved(step_id, last_error)
        return OffboardingStepResult(
            step_name=step_name,
            status=StepStatus.UNRESOLVED,
            error=last_error,
            attempts=max_attempts,
        )

    def _call_external(self, employee_id: str, step_name: str) -> tuple[bool, str | None]:
        if step_name == "revoke_sessions":
            ok = self._integrations.revoke_sessions(employee_id)
            return ok, None if ok else "session_revoke_failed"
        if step_name == "revoke_provider_permissions":
            ok = self._integrations.revoke_provider_permissions(employee_id)
            return ok, None if ok else "provider_revoke_failed"
        if step_name == "revoke_api_credentials":
            ok = self._integrations.revoke_api_credentials(employee_id)
            return ok, None if ok else "api_credential_revoke_failed"
        if step_name == "disable_identity_external":
            ok = self._integrations.disable_identity(employee_id)
            return ok, None if ok else "identity_disable_failed"
        return False, "unknown_step"

    async def _insert_step(self, run_id: str, step_id: str, step_name: str) -> None:
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

    async def _record_attempt(self, step_id: str, attempt: int, err: str | None) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_steps)
                .where(cloud_offboarding_steps.c.step_id == step_id)
                .values(attempts=attempt, last_error=err)
            )

    async def _mark_step_succeeded(self, step_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_steps)
                .where(cloud_offboarding_steps.c.step_id == step_id)
                .values(status=StepStatus.SUCCEEDED.value, completed_at=datetime.now(UTC))
            )

    async def _mark_step_failed(self, step_id: str, error: str | None) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_steps)
                .where(cloud_offboarding_steps.c.step_id == step_id)
                .values(
                    status=StepStatus.FAILED.value,
                    completed_at=datetime.now(UTC),
                    last_error=error,
                )
            )

    async def _mark_step_unresolved(self, step_id: str, error: str | None) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_steps)
                .where(cloud_offboarding_steps.c.step_id == step_id)
                .values(
                    status=StepStatus.UNRESOLVED.value,
                    completed_at=datetime.now(UTC),
                    last_error=error,
                )
            )

    async def _finalize_run(self, run_id: str, status: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(cloud_offboarding_runs)
                .where(cloud_offboarding_runs.c.run_id == run_id)
                .values(status=status, completed_at=datetime.now(UTC))
            )


def offboarding_complete(state: OffboardingState) -> bool:
    return (
        state.complete
        and state.local_revoked
        and not state.external_unresolved
        and all(s.status == StepStatus.SUCCEEDED for s in state.steps)
    )
