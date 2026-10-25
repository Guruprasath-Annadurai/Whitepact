# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real owned process containment, not a lease-revocation success surrogate."""

import asyncio
import multiprocessing
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreQuarantineError,
    get_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.db.containment_repository import ContainmentRepository
from responsibleai.isolation import in_flight as tracking
from responsibleai.runtime.authority_kernel import Phase7AAuthorityKernel
from responsibleai.runtime.errors import AuthorityKernelError
from tests.test_m13_referenced_approval_deletion import _seed_execution
from tests.test_m13_referenced_approval_deletion import deletion_ready as deletion_ready


def _interrupted_deleter(url, store_b, key, tenant, sender):
    """Disposable process: stop only after real durable quarantine/revocation."""
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

        class Interrupted(TenantDeletionOrchestrator):
            async def _revoke_referenced_authority(self, *args, **kwargs):
                result = await super()._revoke_referenced_authority(*args, **kwargs)
                sender.send("DURABLE_QUARANTINE_AND_REVOCATION")
                await asyncio.Event().wait()
                return result

        try:
            await Interrupted(engine, provider).delete_tenant(tenant, "fixture-controller", "crash")
        finally:
            await engine.close()

    asyncio.run(run())


@pytest.mark.asyncio
@pytest.mark.parametrize("acknowledge", [True, False, None, "exception"])
async def test_deletion_requires_actual_worker_exit_before_success(
    deletion_ready, monkeypatch, tmp_path, acknowledge
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="actual-worker-delete",
        name="Worker deletion",
        slug="worker-deletion",
    )
    generation = service.provider.get_state(tenant).generation_id
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "owned-process-tracking")
    registry = tracking.InFlightExecutionRegistry()
    monkeypatch.setattr(tracking.InFlightExecutionRegistry, "_instance", registry)
    process = subprocess.Popen(
        [sys.executable, "-c", "import time; print('READY', flush=True); time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    calls = []
    confirmation = acknowledge

    async def terminate():
        calls.append("termination-requested")
        if confirmation == "exception":
            raise RuntimeError("owned-worker termination remains unconfirmed")
        if confirmation is not True:
            return confirmation
        process.terminate()
        await asyncio.to_thread(process.wait, timeout=5)
        return process.poll() is not None

    try:
        assert (
            await asyncio.wait_for(asyncio.to_thread(process.stdout.readline), timeout=5)
            == b"READY\n"
        )
        assert process.poll() is None
        await registry.register(
            "owned-deletion-worker",
            tenant,
            "harmless-owned-test-worker",
            admission_epoch=1,
            terminate_callback=terminate,
        )
        orchestrator = TenantDeletionOrchestrator(service.engine, service.provider)
        if acknowledge is not True:
            with pytest.raises(TenantDeletionError, match="Containment unconfirmed"):
                await orchestrator.delete_tenant(tenant, "test-controller", "verify-containment")
            assert process.poll() is None
            assert registry.has_unresolved(tenant)
            assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
            assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
            assert service.provider.get_state(tenant).generation_id == generation
            async with service.engine.raw.connect() as connection:
                assert (
                    await connection.scalar(
                        text("SELECT governance_status FROM organizations WHERE id=:id"),
                        {"id": tenant},
                    )
                    == "DISABLED"
                )
            with pytest.raises(AuthorityKernelError, match="not ACTIVE"):
                await Phase7AAuthorityKernel(service.engine).issue(
                    organization_id=tenant,
                    principal_id="denied",
                    agent_id="denied",
                    identity_id="denied",
                    intent="must-not-run",
                    action_type="test",
                    target="test",
                    action_digest="0" * 64,
                    canonical_action_payload="{}",
                    approved_arguments={},
                    idempotency_key="denied-new-work",
                )
            confirmation = True
        result = await orchestrator.delete_tenant(
            tenant, "test-controller", "confirmed-containment"
        )
        assert calls
        assert result.verification_passed is True
        assert process.poll() is not None
        assert registry.count_active(tenant) == 0
        assert registry.count_unresolved(tenant) == 0
        assert service.provider.get_state(tenant).generation_id == generation
        assert service.provider.get_state(tenant).state == LifecycleState.TOMBSTONED
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait, timeout=5)
        process.stdout.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("uncertainty", ["journal", "external_effect"])
async def test_deletion_never_synthesizes_containment_or_effect_receipts(
    deletion_ready, uncertainty
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="uncertain-delete",
        name="Uncertain",
        slug="uncertain-delete",
    )
    if uncertainty == "journal":
        await ContainmentRepository(service.engine).begin(
            execution_id="preparing-deletion",
            organization_id=tenant,
            owner_generation="disposable-worker-generation",
            backend_identity="fixture-backend",
            authorization_id="fixture-only",
            action_digest="0" * 64,
            admission_epoch=1,
            expected_container_name="wp_iso_disposable",
        )
    else:
        async with service.engine.raw.begin() as connection:
            ids = await _seed_execution(connection, tenant, "uncertain-effect", referenced=True)
            await connection.execute(
                text(
                    "UPDATE runtime_execution_attempts SET state='UNCERTAIN',effect_state='EFFECT_UNCERTAIN' "
                    "WHERE attempt_id=:id"
                ),
                {"id": ids["attempt_id"]},
            )
    expected = RestoreQuarantineError if uncertainty == "journal" else TenantDeletionError
    pattern = "FAILED" if uncertainty == "journal" else "Containment unconfirmed"
    with pytest.raises(expected, match=pattern):
        await TenantDeletionOrchestrator(service.engine, service.provider).delete_tenant(
            tenant, "test-controller", "uncertainty-is-not-success"
        )
    if uncertainty == "journal":
        # Existing global admission detects the incomplete durable intent before
        # deletion runs. Do not bypass that earlier fail-closed security gate.
        assert service.provider.get_state(tenant).state == LifecycleState.ACTIVE
        assert not get_restore_readiness_gate().is_admitted()
    else:
        assert service.provider.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
    async with service.engine.raw.connect() as connection:
        if uncertainty == "journal":
            assert (
                await connection.scalar(
                    text(
                        "SELECT state FROM runtime_containment_records WHERE execution_id='preparing-deletion'"
                    )
                )
                == "PREPARING"
            )
        else:
            row = (
                await connection.execute(
                    text(
                        "SELECT state,effect_state FROM runtime_execution_attempts WHERE attempt_id=:id"
                    ),
                    {"id": ids["attempt_id"]},
                )
            ).one()
            assert tuple(row) == ("UNCERTAIN", "EFFECT_UNCERTAIN")


@pytest.mark.asyncio
async def test_quarantine_linearizes_before_new_grant_issuance(deletion_ready):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="concurrent-delete",
        name="Concurrent",
        slug="concurrent-delete",
    )
    reached, release = asyncio.Event(), asyncio.Event()

    class PausedDeletion(TenantDeletionOrchestrator):
        async def _revoke_referenced_authority(self, *args, **kwargs):
            reached.set()
            await release.wait()
            return await super()._revoke_referenced_authority(*args, **kwargs)

    operation = asyncio.create_task(
        PausedDeletion(service.engine, service.provider).delete_tenant(
            tenant, "test-controller", "quarantine-race"
        )
    )
    try:
        await asyncio.wait_for(reached.wait(), timeout=10)
        with pytest.raises(AuthorityKernelError, match="not ACTIVE"):
            await Phase7AAuthorityKernel(service.engine).issue(
                organization_id=tenant,
                principal_id="denied",
                agent_id="denied",
                identity_id="denied",
                intent="must-not-run",
                action_type="test",
                target="test",
                action_digest="0" * 64,
                canonical_action_payload="{}",
                approved_arguments={},
                idempotency_key="concurrent-denied",
            )
        async with service.engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM governance_execution_authorizations WHERE organization_id=:id"
                    ),
                    {"id": tenant},
                )
                == 0
            )
    finally:
        release.set()
        result = await operation
    assert result.verification_passed is True


@pytest.mark.asyncio
async def test_actual_deleter_death_preserves_fence_then_retry_contains_worker(
    deletion_ready, monkeypatch, tmp_path
):
    service, token, csrf = deletion_ready
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="crashed-deleter",
        name="Crash retry",
        slug="crashed-deleter",
    )
    generation = service.provider.get_state(tenant).generation_id
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "crash-tracking")
    registry = tracking.InFlightExecutionRegistry()
    monkeypatch.setattr(tracking.InFlightExecutionRegistry, "_instance", registry)
    worker = subprocess.Popen(
        [sys.executable, "-c", "import time; print('READY',flush=True); time.sleep(120)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    context = multiprocessing.get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(
        target=_interrupted_deleter,
        args=(
            service.engine.raw.url.render_as_string(hide_password=False),
            service.provider.path,
            service.provider._secret_key,
            tenant,
            sender,
        ),
    )

    async def terminate_worker():
        worker.terminate()
        await asyncio.to_thread(worker.wait, timeout=5)
        return worker.poll() is not None

    try:
        assert (
            await asyncio.wait_for(asyncio.to_thread(worker.stdout.readline), timeout=5)
            == b"READY\n"
        )
        await registry.register(
            "crash-owned-worker",
            tenant,
            "harmless-worker",
            admission_epoch=1,
            terminate_callback=terminate_worker,
        )
        child.start()
        assert await asyncio.to_thread(receiver.poll, 30)
        assert receiver.recv() == "DURABLE_QUARANTINE_AND_REVOCATION"
        child.terminate()
        await asyncio.to_thread(child.join, 10)
        assert child.exitcode is not None and child.exitcode != 0
        assert worker.poll() is None
        assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
        from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider

        reopened = SqliteDurableLifecycleStateProvider(
            service.provider.path, secret_key=service.provider._secret_key
        )
        assert reopened.get_state(tenant).state == LifecycleState.DELETION_IN_PROGRESS
        assert reopened.get_state(tenant).generation_id == generation
        async with service.engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT governance_status FROM organizations WHERE id=:id"), {"id": tenant}
                )
                == "DISABLED"
            )
        result = await TenantDeletionOrchestrator(service.engine, reopened).delete_tenant(
            tenant, "fixture-controller", "actual-crash-retry"
        )
        assert result.verification_passed is True
        assert worker.poll() is not None
        assert reopened.get_state(tenant).generation_id == generation
        assert registry.count_unresolved(tenant) == 0
    finally:
        if child.is_alive():
            child.terminate()
            await asyncio.to_thread(child.join, 10)
        if worker.poll() is None:
            worker.terminate()
            await asyncio.to_thread(worker.wait, timeout=5)
        worker.stdout.close()
        receiver.close()
        sender.close()
