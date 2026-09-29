# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from tests.pg_test_url import isolated_pg_url
from tests.whitepact_cloud.conftest import enroll_active_employee

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.offboarding import (
    LOCAL_STEP,
    OffboardingService,
    StepStatus,
    offboarding_complete,
)
from responsibleai.whitepact_cloud.roles import CloudRole


class _OkIntegrations:
    def disable_identity(self, employee_id: str) -> bool:
        return True

    def revoke_sessions(self, employee_id: str) -> bool:
        return True

    def revoke_provider_permissions(self, employee_id: str) -> bool:
        return True

    def revoke_api_credentials(self, employee_id: str) -> bool:
        return True


class _FailSessions:
    def disable_identity(self, employee_id: str) -> bool:
        return True

    def revoke_sessions(self, employee_id: str) -> bool:
        return False

    def revoke_provider_permissions(self, employee_id: str) -> bool:
        return True

    def revoke_api_credentials(self, employee_id: str) -> bool:
        return True


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_cloud_offboard"):
        yield url


@pytest.mark.asyncio
async def test_offboarding_complete_success(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(repo, "emp-off-1", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-off")
    svc = OffboardingService(engine, repo, _OkIntegrations())
    state = await svc.run("emp-off-1", max_attempts=1)
    assert state.local_revoked
    assert offboarding_complete(state)
    assert state.steps[0].step_name == LOCAL_STEP
    await engine.close()


@pytest.mark.asyncio
async def test_offboarding_not_complete_when_external_unresolved(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(repo, "emp-off-2", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-off-2")
    svc = OffboardingService(engine, repo, _FailSessions())
    state = await svc.run("emp-off-2", max_attempts=1)
    assert state.local_revoked
    assert state.external_unresolved
    assert not offboarding_complete(state)
    unresolved = [s for s in state.steps if s.status == StepStatus.UNRESOLVED]
    assert unresolved and unresolved[0].step_name == "revoke_sessions"
    status = await repo.get_employee_status("emp-off-2")
    assert status == "terminated"
    await engine.close()
