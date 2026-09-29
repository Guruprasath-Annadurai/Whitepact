# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.offboarding import (
    OffboardingService,
    StepStatus,
    offboarding_complete,
)


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
    svc = OffboardingService(engine, repo, _OkIntegrations())
    state = await svc.run("emp-off-1", max_attempts=1)
    assert offboarding_complete(state)
    assert state.partial is False
    await engine.close()


@pytest.mark.asyncio
async def test_offboarding_partial_on_session_failure(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    svc = OffboardingService(engine, repo, _FailSessions())
    state = await svc.run("emp-off-2", max_attempts=1)
    assert state.partial is True
    assert not offboarding_complete(state)
    failed = [s for s in state.steps if s.status == StepStatus.FAILED]
    assert failed and failed[0].step_name == "revoke_sessions"
    await engine.close()
