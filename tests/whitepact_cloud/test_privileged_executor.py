# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from tests.pg_test_url import isolated_pg_url
from tests.whitepact_cloud.conftest import enroll_active_employee

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.admin_grant import GrantDecision
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.grant_service import AdminGrantService, GrantExecutionError
from responsibleai.whitepact_cloud.privileged_executor import PrivilegedOperationExecutor
from responsibleai.whitepact_cloud.roles import CloudRole

SIGNING_KEY = b"test-signing-key-32-bytes-min!!!"


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_cloud_exec"):
        yield url


@pytest.mark.asyncio
async def test_disabled_executor_refuses(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    grants = AdminGrantService(repo, SIGNING_KEY)
    executor = PrivilegedOperationExecutor(grants, enabled=False)
    with pytest.raises(GrantExecutionError, match="privileged_executor_disabled"):
        await executor.execute(
            grant_id="n/a",
            signature="n/a",
            expected_operation="x",
            expected_provider="hetzner",
            expected_resource="r",
            required_permission="cloud.infra.read",
            operation=lambda _v: _noop(),
        )
    await engine.close()


@pytest.mark.asyncio
async def test_executor_verifies_before_operation(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-ex", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-ex"
    )
    grants = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await grants.issue_and_persist(
        employee_id="emp-ex",
        role=CloudRole.DEVELOPER,
        operation="infra.read",
        provider="hetzner",
        resource_target="project/dev",
        permissions=["cloud.infra.read"],
        policy_id="pol-ex",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=300,
        founder_only_exception=True,
    )
    called = {"ok": False}

    async def op(verification: dict) -> str:
        called["ok"] = True
        assert verification["ok"] is True
        return "done"

    executor = PrivilegedOperationExecutor(grants, enabled=True)
    result = await executor.execute(
        grant_id=claim.grant_id,
        signature=sig,
        expected_operation="infra.read",
        expected_provider="hetzner",
        expected_resource="project/dev",
        required_permission="cloud.infra.read",
        operation=op,
    )
    assert result == "done"
    assert called["ok"]
    await engine.close()


async def _noop() -> None:
    return None
