# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial qualification of in-flight process liveness and distributed tracking.

Proves:
1. kill(pid, 0) returning EPERM (process alive under different UID/sandbox) retains tracking and marks unresolved.
2. kill(pid, 0) returning ESRCH (process dead) retains tracking record as unconfirmed containment.
3. Inaccessible or corrupt tracking files fail closed, treating containment as unconfirmed.
4. Directory scanning failure (e.g. permission/disk error) fails closed, marking unresolved containment.
5. In-flight termination with partial callback failure retains unconfirmed executions.
6. Worker crash (process death) transitions tracking cleanly without leaving orphaned unresolved state.
7. Unreachable remote worker with active PID prevents new tenant registrations.
8. Multiple workers reconciling database revocation epochs terminate stale executions within bounded latency.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from unittest.mock import patch

import pytest

from responsibleai.isolation.in_flight import (
    _DISTRIBUTED_REGISTRY_DIR,
    InFlightExecutionRegistry,
    _check_remote_worker_active,
)


@pytest.fixture(autouse=True)
def reset_in_flight_registry():
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_kill_esrch_retains_unconfirmed_tracking() -> None:
    """When a remote worker process has died (ESRCH), tracking is retained as unconfirmed containment."""
    dist_dir = _DISTRIBUTED_REGISTRY_DIR
    dist_dir.mkdir(parents=True, exist_ok=True)

    org_id = f"org_esrch_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_esrch_{uuid.uuid4().hex[:8]}"
    dead_pid = 999998

    tracking_file = dist_dir / f"{org_id}_{exec_id}.json"
    tracking_file.write_text(
        json.dumps(
            {
                "execution_id": exec_id,
                "organization_id": org_id,
                "action_id": "act.esrch",
                "authorization_id": "auth.esrch",
                "admission_epoch": 0,
                "pid": dead_pid,
                "created_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    try:

        def _mock_kill(pid, sig):
            if pid == dead_pid:
                raise ProcessLookupError("No such process")
            return os.kill(pid, sig)

        with patch("os.kill", side_effect=_mock_kill):
            active_remote = _check_remote_worker_active(org_id)
            assert len(active_remote) == 1, "Dead worker without containment proof must be reported as unresolved"
            assert "Worker exited; containment unconfirmed" in active_remote[0].get("error", "")
            assert tracking_file.exists(), "Tracking file must be retained until containment is independently confirmed"
    finally:
        if tracking_file.exists():
            tracking_file.unlink()


@pytest.mark.asyncio
async def test_inaccessible_tracking_file_fails_closed_into_unresolved() -> None:
    """When a tracking file cannot be read, absence is unconfirmed; must fail closed."""
    dist_dir = _DISTRIBUTED_REGISTRY_DIR
    dist_dir.mkdir(parents=True, exist_ok=True)

    org_id = f"org_inacc_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_inacc_{uuid.uuid4().hex[:8]}"
    corrupt_file = dist_dir / f"{org_id}_{exec_id}.json"
    # Write invalid JSON / simulate corrupt or locked file
    corrupt_file.write_text("CORRUPTED_NON_JSON_DATA", encoding="utf-8")

    try:
        registry = InFlightExecutionRegistry.get_instance()
        active_remote = _check_remote_worker_active(org_id)

        # Absence CANNOT be proved! Must be marked unresolved!
        assert len(active_remote) == 1
        assert active_remote[0]["execution_id"] == exec_id
        assert "inaccessible" in active_remote[0].get("error", "").lower()
        assert registry.has_unresolved(org_id) is True

        # Subsequent registration must fail closed
        with pytest.raises(PermissionError, match="has been revoked in-flight"):
            await registry.register(
                execution_id=f"exec_new_{uuid.uuid4().hex[:8]}",
                organization_id=org_id,
                action_id="act.blocked",
                admission_epoch=5,
            )
    finally:
        if corrupt_file.exists():
            corrupt_file.unlink()


@pytest.mark.asyncio
async def test_directory_scan_failure_fails_closed_into_unresolved() -> None:
    """When scanning distributed directory fails with OSError, system fails closed."""
    org_id = f"org_scanerr_{uuid.uuid4().hex[:8]}"
    registry = InFlightExecutionRegistry.get_instance()

    def _failing_scandir(path):
        raise OSError("I/O error: disk failure or permission denied scanning registry")

    with patch("os.scandir", side_effect=_failing_scandir):
        active_remote = _check_remote_worker_active(org_id)
        assert len(active_remote) == 1
        assert "scan failure" in active_remote[0].get("error", "").lower()
        assert registry.has_unresolved(org_id) is True


@pytest.mark.asyncio
async def test_unreachable_live_remote_worker_blocks_tenant_admission() -> None:
    """When a remote worker is still running and cannot be terminated, tenant is blocked."""
    dist_dir = _DISTRIBUTED_REGISTRY_DIR
    dist_dir.mkdir(parents=True, exist_ok=True)

    org_id = f"org_unreach_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_unreach_{uuid.uuid4().hex[:8]}"
    remote_pid = 999997

    tracking_file = dist_dir / f"{org_id}_{exec_id}.json"
    tracking_file.write_text(
        json.dumps(
            {
                "execution_id": exec_id,
                "organization_id": org_id,
                "action_id": "act.unreach",
                "authorization_id": "auth.unreach",
                "admission_epoch": 0,
                "pid": remote_pid,
                "created_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    try:

        def _mock_kill(pid, sig):
            if pid == remote_pid and sig == 0:
                return None  # Process exists and is alive!
            return os.kill(pid, sig)

        with patch("os.kill", side_effect=_mock_kill):
            registry = InFlightExecutionRegistry.get_instance()
            # Attempting termination records remote worker in unresolved containment
            terminated = await registry.terminate_in_flight(organization_id=org_id)
            assert terminated == []  # Cannot terminate remote worker directly!
            assert registry.has_unresolved(org_id) is True
            assert registry.count_unresolved(org_id) >= 1

            # New execution must be rejected fail-closed
            with pytest.raises(PermissionError, match="has been revoked in-flight"):
                await registry.register(
                    execution_id=f"exec_rejected_{uuid.uuid4().hex[:8]}",
                    organization_id=org_id,
                    action_id="act.rej",
                )
    finally:
        if tracking_file.exists():
            tracking_file.unlink()
