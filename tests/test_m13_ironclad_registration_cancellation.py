# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent controlled lifecycle barriers; no native Docker qualification claim."""

import asyncio
from pathlib import Path

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import IsolatedExecutionRequest
from tests.test_m13_ironclad_container_ownership import Process
from tests.test_m13_ironclad_container_ownership import backend as backend


async def cancellation_barrier(monkeypatch, tmp_path, *, during_spawn):
    InFlightExecutionRegistry.reset_instance()
    registry = InFlightExecutionRegistry.get_instance()
    backend = DockerContainerBackend()
    spawned = asyncio.Event()
    spawn_release = asyncio.Event()
    cleanup_entered = asyncio.Event()
    cleanup_release = asyncio.Event()
    events = []
    selected = []
    owned_cid = "b" * 64

    class Process:
        returncode = None
        pid = 12345

        def kill(self):
            events.append("kill")
            self.returncode = -9

        async def communicate(self, input=None):
            events.append("drain")
            return b"", b""

        async def wait(self):
            return self.returncode

    process = Process()

    async def spawn(*command, **kwargs):
        receipt = Path(next(x.split("=", 1)[1] for x in command if x.startswith("--cidfile=")))
        assert receipt.parent.stat().st_mode & 0o777 == 0o700
        receipt.write_text(owned_cid)
        spawned.set()
        if during_spawn:
            await spawn_release.wait()
        return process

    async def cleanup(targets, **kwargs):
        selected.extend(targets)
        cleanup_entered.set()
        await cleanup_release.wait()
        events.append("confirmed-container-absence")

    monkeypatch.setattr(
        "responsibleai.isolation.in_flight._DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking"
    )
    monkeypatch.setattr(backend, "is_available", lambda: True)
    monkeypatch.setattr(EphemeralWorkspace, "prepare_for_container", lambda *a, **k: None)
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.grant_container_read", lambda *a: None
    )
    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", cleanup)
    locked = False
    task = None
    if not during_spawn:
        await registry._lock.acquire()
        locked = True
    try:
        task = asyncio.create_task(
            backend.execute(
                IsolatedExecutionRequest(
                    action_id="cancel-creation",
                    organization_id="cancellation-owner",
                    action_type="noop",
                    arguments={},
                )
            )
        )
        await asyncio.wait_for(spawned.wait(), timeout=3)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        # Cancellation cannot discard ownership of a client/container already
        # created while the corresponding await has not yet returned.
        assert not task.done(), "Cancellation escaped before owned creation/registration completed"
        if locked:
            registry._lock.release()
            locked = False
        spawn_release.set()
        await asyncio.wait_for(cleanup_entered.wait(), timeout=3)
        assert not task.done(), "Cancellation escaped before containment was confirmed"
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "Repeated cancellation interrupted owned cleanup"
        cleanup_release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), timeout=3)
        assert task.cancelling() == 2
        assert "kill" in events and "drain" in events
        assert events[-1] == "confirmed-container-absence"
        assert owned_cid in selected
        assert all(
            value == owned_cid or value.startswith("wp_iso_cancellation-owner_")
            for value in selected
        )
        assert registry.count_active("cancellation-owner") == 0
        assert registry.count_unresolved("cancellation-owner") == 0
    finally:
        if locked:
            registry._lock.release()
        spawn_release.set()
        cleanup_release.set()
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=3)
            except asyncio.CancelledError:
                pass
        InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_cancel_during_spawn_wait_preserves_created_container_ownership(
    monkeypatch, tmp_path
):
    await cancellation_barrier(monkeypatch, tmp_path, during_spawn=True)


@pytest.mark.asyncio
async def test_cancel_during_registration_lock_wait_preserves_container_ownership(
    monkeypatch, tmp_path
):
    await cancellation_barrier(monkeypatch, tmp_path, during_spawn=False)


@pytest.mark.asyncio
async def test_uncanceled_admission_rejection_does_not_add_cancellation(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=Process())
    )
    monkeypatch.setattr(
        backend, "_remove_containers_uninterruptible", lambda *a, **k: asyncio.sleep(0)
    )
    before = asyncio.current_task().cancelling()
    outcome = await backend.execute(
        IsolatedExecutionRequest(
            action_id="rejected", organization_id="owner", action_type="noop", arguments={}
        )
    )
    assert outcome.exit_code == -9
    assert asyncio.current_task().cancelling() == before
    assert registry.count_active("owner") == 0
    assert registry.count_unresolved("owner") == 0


@pytest.mark.asyncio
async def test_accepted_registration_transfers_to_actual_execution_owner(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registered = []
    communicating = asyncio.Event()
    release = asyncio.Event()
    original = registry.register

    async def register(*args, **kwargs):
        entry = await original(*args, **kwargs)
        registered.append(entry)
        return entry

    class BufferedProcess(Process):
        async def communicate(self, input=None):
            communicating.set()
            await release.wait()
            return await super().communicate(input)

    monkeypatch.setattr(registry, "register", register)
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        lambda *a, **k: asyncio.sleep(0, result=BufferedProcess()),
    )
    monkeypatch.setattr(
        backend, "_remove_containers_uninterruptible", lambda *a, **k: asyncio.sleep(0)
    )
    task = asyncio.create_task(
        backend.execute(
            IsolatedExecutionRequest(
                action_id="accepted", organization_id="owner", action_type="noop", arguments={}
            )
        )
    )
    try:
        await asyncio.wait_for(communicating.wait(), 3)
        assert len(registered) == 1
        assert registered[0].task is task
        release.set()
        assert (await asyncio.wait_for(task, 3)).is_success
        assert registry.count_active("owner") == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
