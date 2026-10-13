# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.whitepact_cloud.employee_enrollment import (
    EmployeeEnrollmentService,
    EnrollmentError,
)
from responsibleai.whitepact_cloud.grant_repository import AdminGrantRepository
from responsibleai.whitepact_cloud.roles import CloudRole


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_cloud_enroll"):
        yield url


@pytest.mark.asyncio
async def test_enroll_inserts_active_employee(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    svc = EmployeeEnrollmentService(repo)
    perms = ["cloud.infra.read"]
    await svc.enroll("emp-1", CloudRole.DEVELOPER, perms)
    row = await repo.get_employee_record("emp-1")
    assert row is not None
    assert row["status"] == "active"
    assert json.loads(row["authorized_permissions_json"]) == perms
    await engine.close()


@pytest.mark.asyncio
async def test_enroll_rejects_permission_outside_role(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    svc = EmployeeEnrollmentService(AdminGrantRepository(engine))
    try:
        await svc.enroll("emp-2", CloudRole.DEVELOPER, ["cloud.admin.grant"])
    except EnrollmentError as exc:
        assert "cannot authorize" in exc.reason
    else:
        raise AssertionError("expected EnrollmentError")
    await engine.close()


@pytest.mark.asyncio
async def test_enroll_rejects_duplicate_active(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    svc = EmployeeEnrollmentService(repo)
    await svc.enroll("emp-3", CloudRole.DEVELOPER, ["cloud.infra.read"])
    try:
        await svc.enroll("emp-3", CloudRole.DEVELOPER, ["cloud.infra.read"])
    except EnrollmentError as exc:
        assert exc.reason == "employee_already_enrolled"
    else:
        raise AssertionError("expected EnrollmentError")
    await engine.close()


@pytest.mark.asyncio
async def test_enroll_does_not_reactivate_terminated(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await repo.insert_employee(
        "emp-term",
        str(CloudRole.DEVELOPER),
        ["cloud.infra.read"],
        status="terminated",
    )
    svc = EmployeeEnrollmentService(repo)
    try:
        await svc.enroll("emp-term", CloudRole.DEVELOPER, ["cloud.infra.read"])
    except EnrollmentError as exc:
        assert exc.reason == "employee_not_eligible_for_reactivation_via_enroll"
    else:
        raise AssertionError("expected EnrollmentError")
    await engine.close()


@pytest.mark.asyncio
async def test_enroll_does_not_reactivate_suspended(pg_url: str) -> None:
    await run_migrations_or_raise(pg_url)
    engine = create_engine(pg_url)
    await engine.init()
    repo = AdminGrantRepository(engine)
    await repo.insert_employee(
        "emp-susp",
        str(CloudRole.DEVELOPER),
        ["cloud.infra.read"],
        status="suspended",
    )
    svc = EmployeeEnrollmentService(repo)
    try:
        await svc.enroll("emp-susp", CloudRole.DEVELOPER, ["cloud.infra.read"])
    except EnrollmentError as exc:
        assert exc.reason == "employee_not_eligible_for_reactivation_via_enroll"
    else:
        raise AssertionError("expected EnrollmentError")
    await engine.close()
