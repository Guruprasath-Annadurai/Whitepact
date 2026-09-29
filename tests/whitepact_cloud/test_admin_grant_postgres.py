# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.admin_grant import GrantDecision
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.grant_service import AdminGrantService
from responsibleai.whitepact_cloud.roles import CloudRole

SIGNING_KEY = b"test-signing-key-32-bytes-min!!!"


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_cloud_grant"):
        yield url


@pytest.mark.asyncio
async def test_postgres_atomic_consume_single_winner(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    service = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await service.issue_and_persist(
        employee_id="emp-pg-1",
        role=CloudRole.PLATFORM_ENGINEER,
        operation="infra.plan",
        provider="hetzner",
        resource_target="server/wp-dev-saas-1",
        permissions=["cloud.infra.read"],
        policy_id="pol-pg",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=300,
        founder_only_exception=True,
    )

    async def try_consume() -> bool:
        eng = create_engine(pg_url)
        await eng.init()
        svc = AdminGrantService(AdminGrantRepository(eng), SIGNING_KEY)
        result = await svc.verify_for_execution(
            claim.grant_id,
            sig,
            expected_operation="infra.plan",
            expected_provider="hetzner",
            expected_resource="server/wp-dev-saas-1",
            required_permission="cloud.infra.read",
        )
        await eng.close()
        return result["ok"]

    results = await asyncio.gather(try_consume(), try_consume(), try_consume())
    assert sum(1 for r in results if r) == 1
    await engine.close()


@pytest.mark.asyncio
async def test_postgres_revoked_grant_cannot_execute(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    service = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await service.issue_and_persist(
        employee_id="emp-pg-2",
        role=CloudRole.DEVELOPER,
        operation="infra.read",
        provider="hetzner",
        resource_target="project/dev",
        permissions=["cloud.infra.read"],
        policy_id="pol-pg-2",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=300,
        founder_only_exception=True,
    )
    await repo.revoke_grant(claim.grant_id)
    result = await service.verify_for_execution(
        claim.grant_id,
        sig,
        expected_operation="infra.read",
        expected_provider="hetzner",
        expected_resource="project/dev",
        required_permission="cloud.infra.read",
    )
    assert result["ok"] is False
    assert result["reason"] == "revoked"
    await engine.close()


@pytest.mark.asyncio
async def test_postgres_expired_grant_rejected(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    service = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await service.issue_and_persist(
        employee_id="emp-pg-3",
        role=CloudRole.DEVELOPER,
        operation="infra.read",
        provider="hetzner",
        resource_target="project/dev",
        permissions=["cloud.infra.read"],
        policy_id="pol-pg-3",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=60,
        founder_only_exception=True,
    )
    future = datetime.now(UTC) + timedelta(hours=2)
    result = await service.verify_for_execution(
        claim.grant_id,
        sig,
        expected_operation="infra.read",
        expected_provider="hetzner",
        expected_resource="project/dev",
        required_permission="cloud.infra.read",
        now=future,
    )
    assert result["reason"] == "expired"
    await engine.close()
