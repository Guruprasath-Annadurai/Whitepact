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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scopes", [("governance", "tenant_global"), ("tenant_global", "governance")]
)
async def test_reconciliation_uses_only_canonical_governance_scope(directory, scopes):
    from sqlalchemy import insert

    from responsibleai.db.engine import create_engine, governance_revocation_epochs

    database = create_engine(":memory:")
    await database.init()
    registry = tracking.InFlightExecutionRegistry()
    terminated = []

    def terminate():
        terminated.append(True)
        return True

    try:
        await registry.register(
            "execution", "tenant", "action", admission_epoch=5, terminate_callback=terminate
        )
        async with database.raw.begin() as conn:
            for scope in scopes:
                await conn.execute(
                    insert(governance_revocation_epochs).values(
                        organization_id="tenant",
                        scope=scope,
                        epoch=7 if scope == "governance" else 2,
                        updated_at="2026-10-18T00:00:00Z",
                    )
                )
        assert await registry.reconcile_epochs(database) == ["execution"]
        assert terminated == [True]
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_confirmed_termination_does_not_erase_conflicting_legacy_authority(directory):
    import os

    registry = tracking.InFlightExecutionRegistry()
    await registry.register(
        "execution", "tenant", "action", authorization_id="current", terminate_callback=lambda: True
    )
    legacy = directory / "tenant_execution.json"
    legacy.write_text(
        json.dumps(
            {
                "organization_id": "tenant",
                "execution_id": "execution",
                "authorization_id": "different-authority",
                "pid": os.getpid(),
                "containment_status": "active",
            }
        )
    )
    await registry.terminate_in_flight(organization_id="tenant")
    assert legacy.exists()
    assert registry.has_unresolved("tenant")


def test_concurrent_cleanup_cannot_unlink_a_republished_owner(directory, monkeypatch):
    import threading
    from pathlib import Path

    original = entry()
    replacement = entry(authorization="replacement")
    tracking._record_cross_worker_registration(original)
    path = directory / tracking._tracking_filename("tenant", "execution")
    paused = threading.Event()
    resume = threading.Event()
    published = threading.Event()
    errors = []
    unlink = Path.unlink

    def intercept(candidate, *args, **kwargs):
        if candidate == path and threading.current_thread().name == "paused-cleanup":
            paused.set()
            assert resume.wait(3)
        return unlink(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", intercept)

    def cleanup():
        tracking._remove_cross_worker_registration(
            "tenant", "execution", registration_id=original.registration_id
        )

    def replace():
        try:
            cleanup()
            tracking._record_cross_worker_registration(replacement)
            published.set()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(target=cleanup, name="paused-cleanup")
    second = threading.Thread(target=replace)
    first.start()
    try:
        assert paused.wait(2)
        second.start()
        published.wait(0.5)
    finally:
        resume.set()
        first.join(3)
        if second.ident is not None:
            second.join(3)
    assert not errors
    assert published.is_set()
    assert path.exists()
    assert json.loads(path.read_text())["registration_id"] == replacement.registration_id


def test_symlink_ownership_lock_cannot_redirect_registration(directory):
    target = directory / "outside-lock"
    target.write_text("unchanged")
    (directory / ".registry.lock").symlink_to(target)
    with pytest.raises(OSError):
        tracking._record_cross_worker_registration(entry())
    assert target.read_text() == "unchanged"
    assert not list(directory.glob("*.json"))


def test_contended_ownership_lock_is_bounded_and_fails_closed(directory):
    import fcntl
    import os

    descriptor = os.open(directory / ".registry.lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        with pytest.raises(TimeoutError, match="ownership lock unavailable"):
            tracking._record_cross_worker_registration(entry())
        assert not list(directory.glob("*.json"))
    finally:
        os.close(descriptor)
