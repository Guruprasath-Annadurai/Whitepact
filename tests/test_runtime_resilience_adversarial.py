# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial runtime and resilience qualification tests for TITAN-2.

Covers:
1. Single-use execution nonce admission rejection for missing/unregistered organizations
   (preventing silent admission on SQLite or raw IntegrityError 500 on PostgreSQL).
2. Distributed in-flight execution tracking resilience against cross-user / EPERM processes:
   When os.kill(pid, 0) raises PermissionError, the process is alive under another user/sandbox;
   it MUST NOT be treated as dead or unlinked, and containment failure must remain unresolved.
3. In-flight execution registry late-registration rejection and tenant isolation.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import aclosing
from pathlib import Path
from unittest.mock import patch

import pytest

from responsibleai.db.engine import create_engine, metadata
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    OrganizationNotGovernableError,
)
from responsibleai.isolation.in_flight import (
    _DISTRIBUTED_REGISTRY_DIR,
    InFlightExecutionRegistry,
    _check_remote_worker_active,
)
from tests.pg_test_url import isolated_pg_url


@pytest.fixture(autouse=True)
def reset_in_flight_registry():
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_nonce_consumption_missing_org_fails_closed_with_governable_error(
    tmp_path: Path,
) -> None:
    """Missing or unregistered organization MUST fail closed with OrganizationNotGovernableError.

    Must NOT silently succeed (e.g. SQLite without FK enforcement) or throw unhandled raw IntegrityError.
    """
    db_file = tmp_path / "sqlite_test.db"
    engine = create_engine(f"sqlite+aiosqlite:///{db_file}")
    async with engine.raw.begin() as conn:
        await conn.run_sync(metadata.create_all)

    nonce_repo = ExecutionNonceRepository(engine)
    missing_org_id = f"org-missing-{uuid.uuid4().hex[:8]}"
    nonce = f"nonce-{uuid.uuid4().hex[:8]}"
    auth_id = f"auth-{uuid.uuid4().hex[:8]}"

    # Missing organization must be rejected with OrganizationNotGovernableError
    with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
        await nonce_repo.consume(
            nonce,
            authorization_id=auth_id,
            organization_id=missing_org_id,
            expected_epoch=0,
        )


@pytest.mark.asyncio
async def test_nonce_consumption_missing_org_on_real_postgres() -> None:
    """On real PostgreSQL, missing organization MUST raise OrganizationNotGovernableError,

    not raw IntegrityError / ForeignKeyViolationError or admit missing tenant.
    """
    async with aclosing(isolated_pg_url("wp_test_nonce_missing")) as urls:
        async for url in urls:
            engine = create_engine(url)
            async with engine.raw.begin() as conn:
                await conn.run_sync(metadata.create_all)

            nonce_repo = ExecutionNonceRepository(engine)
            missing_org_id = f"org-missing-{uuid.uuid4().hex[:8]}"
            nonce = f"nonce-{uuid.uuid4().hex[:8]}"
            auth_id = f"auth-{uuid.uuid4().hex[:8]}"

            with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
                await nonce_repo.consume(
                    nonce,
                    authorization_id=auth_id,
                    organization_id=missing_org_id,
                    expected_epoch=0,
                )


@pytest.mark.asyncio
async def test_distributed_inflight_remote_worker_eperm_treated_as_alive(tmp_path: Path) -> None:
    """When os.kill(pid, 0) raises PermissionError (EPERM), the target process is alive

    in a different user/container security context.
    The registry MUST NOT treat it as dead, MUST NOT unlink its tracking record,
    and MUST preserve unresolved containment status.
    """
    dist_dir = _DISTRIBUTED_REGISTRY_DIR
    dist_dir.mkdir(parents=True, exist_ok=True)

    org_id = f"org_eperm_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_eperm_{uuid.uuid4().hex[:8]}"
    fake_pid = 999999

    tracking_file = dist_dir / f"{org_id}_{exec_id}.json"
    tracking_data = {
        "execution_id": exec_id,
        "organization_id": org_id,
        "action_id": "test.action",
        "authorization_id": "auth.eperm",
        "admission_epoch": 0,
        "pid": fake_pid,
        "created_at": time.time(),
    }
    tracking_file.write_text(json.dumps(tracking_data), encoding="utf-8")

    try:
        # Simulate os.kill(pid, 0) raising PermissionError (process is alive under another UID)
        def _mock_kill(pid, sig):
            if pid == fake_pid and sig == 0:
                raise PermissionError("EPERM: Operation not permitted")
            return os.kill(pid, sig)

        with patch("os.kill", side_effect=_mock_kill):
            active_remote = _check_remote_worker_active(org_id)

            # MUST recognize process is alive and append to active remote
            assert len(active_remote) == 1, "EPERM process must be recognized as alive"
            assert active_remote[0]["execution_id"] == exec_id

            # MUST NOT have deleted the tracking file
            assert tracking_file.exists(), (
                "Tracking file must not be unlinked while process is alive"
            )

            registry = InFlightExecutionRegistry.get_instance()
            # Calling terminate_in_flight must mark unresolved containment
            await registry.terminate_in_flight(organization_id=org_id)
            assert registry.has_unresolved(org_id) is True
            assert registry.count_unresolved(org_id) >= 1

            # Subsequent execution registration for this org must fail closed
            with pytest.raises(PermissionError, match="has been revoked in-flight"):
                await registry.register(
                    execution_id=f"exec_new_{uuid.uuid4().hex[:8]}",
                    organization_id=org_id,
                    action_id="test.new",
                    admission_epoch=5,
                )
    finally:
        if tracking_file.exists():
            tracking_file.unlink()
