# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent ownership and admission counterexamples; never PID-only cleanup."""

import json
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from responsibleai.isolation import in_flight as tracking


def entry(org="tenant", execution="execution", authorization="authority"):
    return tracking.InFlightExecution(
        execution, org, "action", authorization, None, None, time.monotonic()
    )


@pytest.fixture
def directory(tmp_path, monkeypatch):
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    return tmp_path


def test_distinct_database_identifiers_do_not_nfc_alias(directory):
    assert tracking._tracking_filename("caf\u00e9", "x") != tracking._tracking_filename(
        "cafe\u0301", "x"
    )


def test_duplicate_authority_cannot_overwrite(directory):
    tracking._record_cross_worker_registration(entry())
    with pytest.raises((RuntimeError, FileExistsError)):
        tracking._record_cross_worker_registration(entry(authorization="other"))
    data = json.loads(next(directory.glob("*.json")).read_text())
    assert data["authorization_id"] == "authority"


def test_corrupted_record_cannot_be_replaced(directory):
    path = directory / tracking._tracking_filename("tenant", "execution")
    path.write_text("not-json")
    with pytest.raises((RuntimeError, FileExistsError)):
        tracking._record_cross_worker_registration(entry())
    assert path.read_text() == "not-json"


def test_unreadable_legacy_blocks_actual_admission(directory):
    (directory / "tenant_execution.json").write_text("not-json")
    assert tracking.InFlightExecutionRegistry().is_revoked("tenant", 0)


def test_concurrent_registration_has_one_owner(directory):
    def register(index):
        try:
            tracking._record_cross_worker_registration(entry(authorization=str(index)))
            return True
        except (RuntimeError, FileExistsError):
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(register, range(16)))
    assert sum(results) == 1


def test_symlink_tracking_is_not_followed(directory, tmp_path):
    target = tmp_path / "outside-record"
    target.write_text("sensitive")
    path = directory / tracking._tracking_filename("tenant", "execution")
    path.symlink_to(target)
    with pytest.raises((RuntimeError, FileExistsError, OSError)):
        tracking._record_cross_worker_registration(entry())
    assert target.read_text() == "sensitive"


def test_partial_json_cannot_prove_absence(directory):
    (directory / "legacy.json").write_text(
        json.dumps({"organization_id": "tenant", "execution_id": "execution"})
    )
    assert tracking.InFlightExecutionRegistry().is_revoked("tenant", 0)


def test_current_pid_without_local_runtime_ownership_is_unresolved(directory):
    tracking._record_cross_worker_registration(entry())
    assert tracking.InFlightExecutionRegistry().is_revoked("tenant", 0)


@pytest.mark.asyncio
async def test_duplicate_registry_preserves_original_runtime_owner(directory):
    registry = tracking.InFlightExecutionRegistry()
    terminated = []

    def terminate():
        terminated.append("original")
        return True

    original = await registry.register(
        "execution", "tenant", "action", terminate_callback=terminate
    )
    with pytest.raises(PermissionError):
        await registry.register("execution", "other-tenant", "other-action")
    assert registry._active["execution"] is original
    await registry.terminate_in_flight(organization_id="tenant")
    assert terminated == ["original"]


@pytest.mark.asyncio
async def test_retry_requires_explicit_containment_confirmation(directory):
    registry = tracking.InFlightExecutionRegistry()
    await registry.register("execution", "tenant", "action", terminate_callback=lambda: None)
    await registry.terminate_in_flight(organization_id="tenant")
    assert await registry.retry_unresolved("tenant") == []
    assert registry.has_unresolved("tenant")
