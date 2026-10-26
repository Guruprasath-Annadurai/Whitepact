# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Additional deletion races against genuine protected PostgreSQL tenants."""

import asyncio
import multiprocessing
import os
import re
import subprocess
import sys

import asyncpg
import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import LifecycleState
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.isolation import in_flight as tracking
from tests.pg_test_url import resolve_admin_url
from tests.test_m13_referenced_approval_deletion import deletion_ready as deletion_ready


@pytest.mark.asyncio
async def test_worker_ignoring_sigterm_never_allows_successful_deletion(
    deletion_ready, monkeypatch, tmp_path
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="ignoring-worker",
        name="Ignoring worker",
        slug="ignoring-worker",
    )
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "ignoring-worker")
    registry = tracking.InFlightExecutionRegistry()
    monkeypatch.setattr(tracking.InFlightExecutionRegistry, "_instance", registry)
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
            "print('READY',flush=True); time.sleep(120)",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    signals = []

    async def attempt_termination():
        worker.terminate()
        signals.append("SIGTERM")
        await asyncio.sleep(0.05)
        return worker.poll() is not None

    try:
        assert await asyncio.wait_for(asyncio.to_thread(worker.stdout.readline), 5) == b"READY\n"
        await registry.register(
            "ignoring-worker",
            tenant,
            "harmless",
            admission_epoch=1,
            terminate_callback=attempt_termination,
        )
        with pytest.raises(TenantDeletionError, match="Containment unconfirmed"):
            await TenantDeletionOrchestrator(service.engine, service.provider).delete_tenant(
                tenant, "test-controller", "cannot-confirm-termination"
            )
        assert signals
        assert worker.poll() is None
        assert registry.has_unresolved(tenant)
        assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
        async with service.engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
                )
                == 0
            )
    finally:
        if worker.poll() is None:
            worker.kill()
        await asyncio.to_thread(worker.wait, timeout=5)
        worker.stdout.close()


def _crash_boundary_deleter(url, store_b, key, tenant, phase, sender):
    from responsibleai.data_governance.backup_defense import (
        RestoreReadinessGate,
        SqliteDurableLifecycleStateProvider,
        set_restore_readiness_gate,
    )
    from responsibleai.db.engine import create_engine

    os.environ["WHITEPACT_ENV"] = "staging"
    os.environ.pop("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", None)

    async def run():
        engine = create_engine(url)
        provider = SqliteDurableLifecycleStateProvider(store_b, secret_key=key)
        set_restore_readiness_gate(RestoreReadinessGate(provider=provider, db_engine=engine))

        async def stop_at(observed):
            if phase == observed:
                sender.send(observed)
                await asyncio.Event().wait()

        class Interrupted(TenantDeletionOrchestrator):
            async def _revoke_referenced_authority(self, *args, **kwargs):
                await stop_at("quarantine")
                return await super()._revoke_referenced_authority(*args, **kwargs)

            async def _erase_operational_rows(self, *args, **kwargs):
                result = await super()._erase_operational_rows(*args, **kwargs)
                await stop_at("erasure")
                return result

            async def _register_tombstone(self, *args, **kwargs):
                result = await super()._register_tombstone(*args, **kwargs)
                await stop_at("tombstone")
                return result

        try:
            await Interrupted(engine, provider).delete_tenant(tenant, "test-controller", phase)
        finally:
            await engine.close()

    asyncio.run(run())


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["quarantine", "erasure", "tombstone"])
async def test_real_deleter_crash_keeps_authority_closed_and_retry_is_monotonic(
    deletion_ready, phase
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="phase-crash-" + phase,
        name="Crash boundary",
        slug="phase-crash-" + phase,
    )
    generation = service.provider.get_state(tenant).generation_id
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(
        target=_crash_boundary_deleter,
        args=(
            service.engine.raw.url.render_as_string(hide_password=False),
            service.provider.path,
            service.provider._secret_key,
            tenant,
            phase,
            sender,
        ),
    )
    try:
        child.start()
        assert await asyncio.to_thread(receiver.poll, 30)
        assert receiver.recv() == phase
        child.terminate()
        await asyncio.to_thread(child.join, 10)
        assert child.exitcode is not None and child.exitcode != 0
        assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
        assert service.provider.get_state(tenant).generation_id == generation
        async with service.engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT governance_status FROM organizations WHERE id=:id"), {"id": tenant}
                )
                == "DISABLED"
            )
            count = await connection.scalar(
                text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
            )
            assert count == (1 if phase == "tombstone" else 0)
        result = await TenantDeletionOrchestrator(service.engine, service.provider).delete_tenant(
            tenant, "test-controller", "retry-after-actual-crash"
        )
        assert result.verification_passed
        assert result.generation_id == generation
        assert service.provider.get_state(tenant).state == LifecycleState.TOMBSTONED
        async with service.engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
                )
                == 1
            )
    finally:
        if child.is_alive():
            child.terminate()
            await asyncio.to_thread(child.join, 10)
        receiver.close()
        sender.close()


@pytest.mark.asyncio
async def test_duplicate_deletion_has_one_generation_and_one_tombstone(deletion_ready):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="duplicate-deletion",
        name="Duplicate deletion",
        slug="duplicate-deletion",
    )
    generation = service.provider.get_state(tenant).generation_id
    both_arrived = asyncio.Event()
    arrivals = 0

    class ConcurrentDeletion(TenantDeletionOrchestrator):
        async def _register_tombstone(self, *args, **kwargs):
            nonlocal arrivals
            arrivals += 1
            if arrivals == 2:
                both_arrived.set()
            await asyncio.wait_for(both_arrived.wait(), timeout=10)
            return await super()._register_tombstone(*args, **kwargs)

    outcomes = await asyncio.gather(
        *(
            ConcurrentDeletion(service.engine, service.provider).delete_tenant(
                tenant, "test-controller", "duplicate-race"
            )
            for _ in range(2)
        ),
        return_exceptions=True,
    )
    successes = [value for value in outcomes if not isinstance(value, BaseException)]
    failures = [value for value in outcomes if isinstance(value, BaseException)]
    assert successes
    assert all(isinstance(value, TenantDeletionError) for value in failures), failures
    assert all(
        value.verification_passed and value.generation_id == generation for value in successes
    )
    async with service.engine.raw.connect() as connection:
        rows = (
            await connection.execute(
                text("SELECT id,generation_id FROM tenant_tombstones WHERE org_id=:id"),
                {"id": tenant},
            )
        ).all()
    assert len(rows) == 1
    assert rows[0].generation_id == generation
    assert all(value.tombstone_id == rows[0].id for value in successes)
    assert service.provider.get_state(tenant).state == LifecycleState.TOMBSTONED


@pytest.mark.asyncio
async def test_registration_after_deletion_fence_is_rejected_and_retained(
    deletion_ready, monkeypatch, tmp_path
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="late-deletion-worker",
        name="Late deletion worker",
        slug="late-deletion-worker",
    )
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "late-worker")
    registry = tracking.InFlightExecutionRegistry()
    monkeypatch.setattr(tracking.InFlightExecutionRegistry, "_instance", registry)
    fence_reached, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def unconfirmed():
        calls.append("attempted")
        return False

    class PausedDeletion(TenantDeletionOrchestrator):
        async def _erase_operational_rows(self, *args, **kwargs):
            fence_reached.set()
            await release.wait()
            return await super()._erase_operational_rows(*args, **kwargs)

    operation = asyncio.create_task(
        PausedDeletion(service.engine, service.provider).delete_tenant(
            tenant, "test-controller", "late-registration"
        )
    )
    try:
        await asyncio.wait_for(fence_reached.wait(), timeout=10)
        with pytest.raises(PermissionError, match="revoked"):
            await registry.register(
                "late-worker",
                tenant,
                "harmless",
                admission_epoch=1,
                terminate_callback=unconfirmed,
            )
        assert calls == ["attempted"]
        assert registry.has_unresolved(tenant)
    finally:
        release.set()
    with pytest.raises(TenantDeletionError, match="Containment unconfirmed"):
        await operation
    assert registry.has_unresolved(tenant)
    assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
    async with service.engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
            )
            == 0
        )


@pytest.mark.asyncio
async def test_database_unavailable_after_revocation_cannot_complete_deletion(deletion_ready):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="outage-deletion",
        name="Outage deletion",
        slug="outage-deletion",
    )
    generation = service.provider.get_state(tenant).generation_id
    database = service.engine.raw.url.database
    # Never operate on a shared/server database: this fixture owns a uniquely
    # named disposable database created by isolated_controller_context.
    assert re.fullmatch(r"wp_m13_approval_del_[a-z0-9]+", database)
    admin = await asyncpg.connect(await resolve_admin_url())

    class OutageDeletion(TenantDeletionOrchestrator):
        async def _revoke_referenced_authority(self, *args, **kwargs):
            result = await super()._revoke_referenced_authority(*args, **kwargs)
            await admin.execute(f'ALTER DATABASE "{database}" ALLOW_CONNECTIONS false')
            await service.engine.raw.dispose()
            return result

    try:
        with pytest.raises(TenantDeletionError, match="Containment unconfirmed"):
            await OutageDeletion(service.engine, service.provider).delete_tenant(
                tenant, "test-controller", "database-outage"
            )
        assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
        assert service.provider.get_state(tenant).generation_id == generation
    finally:
        await admin.execute(f'ALTER DATABASE "{database}" ALLOW_CONNECTIONS true')
        await admin.close()
    async with service.engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT governance_status FROM organizations WHERE id=:id"), {"id": tenant}
            )
            == "DISABLED"
        )
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM tenant_tombstones WHERE org_id=:id"), {"id": tenant}
            )
            == 0
        )
    result = await TenantDeletionOrchestrator(service.engine, service.provider).delete_tenant(
        tenant, "test-controller", "retry-after-database-return"
    )
    assert result.verification_passed
    assert result.generation_id == generation
