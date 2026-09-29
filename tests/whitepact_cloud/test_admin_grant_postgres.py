# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update
from tests.pg_test_url import isolated_pg_url
from tests.whitepact_cloud.conftest import enroll_active_employee

from responsibleai.db.engine import cloud_employees, create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.admin_grant import GrantDecision
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.grant_service import AdminGrantService, GrantExecutionError
from responsibleai.whitepact_cloud.roles import CloudRole

SIGNING_KEY = b"test-signing-key-32-bytes-min!!!"


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_cloud_grant"):
        yield url


@pytest.mark.asyncio
async def test_issue_rejects_inactive_policy(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-pol", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-inactive"
    )
    await repo.upsert_policy("pol-inactive", active=False, requires_approver=False)
    service = AdminGrantService(repo, SIGNING_KEY)
    try:
        await service.issue_and_persist(
            employee_id="emp-pol",
            role=CloudRole.DEVELOPER,
            operation="infra.read",
            provider="hetzner",
            resource_target="project/dev",
            permissions=["cloud.infra.read"],
            policy_id="pol-inactive",
            approval=GrantDecision.APPROVED,
            approved_by="owner",
            ttl_seconds=300,
            founder_only_exception=True,
        )
    except GrantExecutionError as exc:
        assert exc.reason == "policy_inactive"
    else:
        raise AssertionError("expected GrantExecutionError")
    await engine.close()


@pytest.mark.asyncio
async def test_issue_rejects_terminated_employee(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-dead", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-dead"
    )
    await repo.terminate_local_access("emp-dead")
    service = AdminGrantService(repo, SIGNING_KEY)
    try:
        await service.issue_and_persist(
            employee_id="emp-dead",
            role=CloudRole.DEVELOPER,
            operation="infra.read",
            provider="hetzner",
            resource_target="project/dev",
            permissions=["cloud.infra.read"],
            policy_id="pol-dead",
            approval=GrantDecision.APPROVED,
            approved_by="owner",
            ttl_seconds=300,
            founder_only_exception=True,
        )
    except GrantExecutionError as exc:
        assert exc.reason == "employee_not_active"
    else:
        raise AssertionError("expected GrantExecutionError")
    await engine.close()


@pytest.mark.asyncio
async def test_issue_rejects_unknown_employee(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    service = AdminGrantService(AdminGrantRepository(engine), SIGNING_KEY)
    try:
        await service.issue_and_persist(
            employee_id="emp-unknown",
            role=CloudRole.DEVELOPER,
            operation="infra.read",
            provider="hetzner",
            resource_target="project/dev",
            permissions=["cloud.infra.read"],
            policy_id="pol-x",
            approval=GrantDecision.APPROVED,
            approved_by="owner",
            ttl_seconds=300,
            founder_only_exception=True,
        )
    except GrantExecutionError as exc:
        assert exc.reason == "employee_not_enrolled"
    else:
        raise AssertionError("expected GrantExecutionError")
    await engine.close()


@pytest.mark.asyncio
async def test_postgres_atomic_consume_single_winner(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-pg-1", CloudRole.PLATFORM_ENGINEER, ["cloud.infra.read"], "pol-pg"
    )
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
async def test_execution_requires_permission_in_grant_and_employee(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-pg-4", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-pg-4"
    )
    service = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await service.issue_and_persist(
        employee_id="emp-pg-4",
        role=CloudRole.DEVELOPER,
        operation="infra.read",
        provider="hetzner",
        resource_target="project/dev",
        permissions=["cloud.infra.read"],
        policy_id="pol-pg-4",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=300,
        founder_only_exception=True,
    )
    result = await service.verify_for_execution(
        claim.grant_id,
        sig,
        expected_operation="infra.read",
        expected_provider="hetzner",
        expected_resource="project/dev",
        required_permission="cloud.staging.write",
    )
    assert result["reason"] == "permission_not_in_grant"
    await engine.close()


@pytest.mark.asyncio
async def test_postgres_revoked_grant_cannot_execute(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-pg-2", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-pg-2"
    )
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
    await enroll_active_employee(
        repo, "emp-pg-3", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-pg-3"
    )
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


@pytest.mark.asyncio
async def test_execution_requires_permission_in_employee_allowlist(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-pg-5", CloudRole.DEVELOPER, ["cloud.infra.read"], "pol-pg-5"
    )
    service = AdminGrantService(repo, SIGNING_KEY)
    claim, sig = await service.issue_and_persist(
        employee_id="emp-pg-5",
        role=CloudRole.DEVELOPER,
        operation="infra.read",
        provider="hetzner",
        resource_target="project/dev",
        permissions=["cloud.infra.read"],
        policy_id="pol-pg-5",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=300,
        founder_only_exception=True,
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(cloud_employees)
            .where(cloud_employees.c.employee_id == "emp-pg-5")
            .values(authorized_permissions_json=json.dumps([]))
        )
    result = await service.verify_for_execution(
        claim.grant_id,
        sig,
        expected_operation="infra.read",
        expected_provider="hetzner",
        expected_resource="project/dev",
        required_permission="cloud.infra.read",
    )
    assert result["reason"] == "permission_not_authorized_for_employee"
    await engine.close()


@pytest.mark.asyncio
async def test_concurrent_issue_vs_termination(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await enroll_active_employee(
        repo, "emp-race", CloudRole.PLATFORM_ENGINEER, ["cloud.infra.read"], "pol-race"
    )
    service = AdminGrantService(repo, SIGNING_KEY)

    async def issue_grant() -> str | None:
        try:
            claim, _ = await service.issue_and_persist(
                employee_id="emp-race",
                role=CloudRole.PLATFORM_ENGINEER,
                operation="infra.plan",
                provider="hetzner",
                resource_target="server/x",
                permissions=["cloud.infra.read"],
                policy_id="pol-race",
                approval=GrantDecision.APPROVED,
                approved_by="owner",
                ttl_seconds=300,
                founder_only_exception=True,
            )
            return claim.grant_id
        except GrantExecutionError:
            return None

    async def terminate() -> None:
        await repo.terminate_local_access("emp-race")

    results = await asyncio.gather(issue_grant(), issue_grant(), terminate())
    assert results[2] is None
    status = await repo.get_employee_status("emp-race")
    assert status == "terminated"
    await engine.close()
