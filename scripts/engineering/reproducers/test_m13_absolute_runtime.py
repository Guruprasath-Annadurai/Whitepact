# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent runtime contracts; controlled process/Docker errors, not native proof."""

import asyncio
import subprocess
import threading
import uuid
from unittest.mock import patch

import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import (
    ExecutionOutcome,
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    from responsibleai.isolation.durable_intent import required_journal

    # Resolve the existing explicit development-mode configuration before the
    # test's bounded scheduling probe, not during its first event-loop turn.
    # This module is a controlled process double, not hosted journal evidence.
    assert required_journal() is None
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    tracking.InFlightExecutionRegistry.reset_instance()
    yield tracking.InFlightExecutionRegistry.get_instance()
    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_rejected_admission_does_not_manufacture_caller_cancellation(registry):
    org = f"absolute-{uuid.uuid4().hex}"
    registry.record_revoked_epoch(org, 1)

    async def caller():
        with pytest.raises(PermissionError):
            await registry.register(
                "denied", org, "action", admission_epoch=0,
                task=asyncio.current_task(), terminate_callback=lambda: True,
            )
        await asyncio.sleep(0)
        return "DENIED"

    task = asyncio.create_task(caller())
    try:
        result = await task
    except asyncio.CancelledError:
        pytest.fail("Registry must raise admission denial without cancelling its own caller")
    assert result == "DENIED"
    assert task.cancelling() == 0


@pytest.mark.asyncio
async def test_failed_rejected_execution_termination_remains_tracked(registry):
    org = f"absolute-{uuid.uuid4().hex}"
    registry.record_revoked_epoch(org, 1)

    def failed_termination():
        raise RuntimeError("daemon cannot confirm containment")

    async def caller():
        with pytest.raises(PermissionError):
            await registry.register(
                "unknown", org, "action", admission_epoch=0,
                task=asyncio.current_task(), terminate_callback=failed_termination,
            )

    task = asyncio.create_task(caller())
    await asyncio.gather(task, return_exceptions=True)
    assert registry.has_unresolved(org), "Unconfirmed rejected execution cannot disappear"
    assert any(e.execution_id == "unknown" for e in registry.get_unresolved_containments(org))


@pytest.mark.asyncio
async def test_execute_termination_callback_rejects_plugin_absence_error(registry):
    backend = DockerContainerBackend()
    running, release = asyncio.Event(), asyncio.Event()
    inspected = []

    class Process:
        returncode = 0
        pid = 12345

        async def communicate(self, input=None):
            running.set()
            await release.wait()
            return b'{"status":"success","result":42}', b""

        def kill(self):
            pass

        async def wait(self):
            return 0

    def docker(command, **kwargs):
        if "inspect" in command:
            inspected.append(command[-1])
            return subprocess.CompletedProcess(
                command, 1, stdout="", stderr="authorization plugin not found"
            )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def acknowledge_inert_create(command, receipt):
        cid = "d" * 64
        receipt.write_text(cid, encoding="utf-8")
        return cid

    request = IsolatedExecutionRequest(
        action_id=f"action-{uuid.uuid4().hex}", organization_id=f"org-{uuid.uuid4().hex}",
        action_type="test.action", arguments={},
        profile=IsolationProfile(name="TEST", network_policy=NetworkPolicy.NONE,
                                 resources=ResourceLimits(wall_timeout_seconds=5)),
    )
    with (
        patch.object(backend, "is_available", return_value=True),
        patch("responsibleai.isolation.container_backend.grant_container_read"),
        patch.object(EphemeralWorkspace, "prepare_for_container"),
        patch("asyncio.create_subprocess_exec", return_value=Process()),
        patch.object(backend, "_create_stopped_container", side_effect=acknowledge_inert_create),
        patch("subprocess.run", side_effect=docker),
    ):
        task = asyncio.create_task(backend.execute(request))
        try:
            await asyncio.wait_for(running.wait(), 3)
            entry = next(iter(registry._active.values()))
            assert entry.terminate_callback is not None
            with pytest.raises(RuntimeError, match="containment unconfirmed"):
                await entry.terminate_callback()
        finally:
            release.set()
            results = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(results[0], ExecutionOutcome)
        assert not results[0].is_success and results[0].result_payload is None
        assert inspected and all(target == "d" * 64 for target in inspected)
        assert registry.has_unresolved(request.organization_id)
        assert any(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
        with pytest.raises(PermissionError, match="revoked in-flight"):
            await registry.register("subsequent", request.organization_id, "action")


@pytest.mark.asyncio
@pytest.mark.parametrize("inspection_error", [
    "authorization plugin not found",
    "Error: No such container: owned; authorization plugin not found",
    "daemon unavailable",
])
async def test_actual_cleanup_inspection_uncertainty_retains_denial(registry, inspection_error):
    backend = DockerContainerBackend()
    org, execution = f"uncertain-{uuid.uuid4().hex}", uuid.uuid4().hex

    def docker(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 1 if "inspect" in command else 0, stdout="", stderr=inspection_error
        )

    async def terminate():
        await backend._remove_containers_uninterruptible(
            ["e" * 64], stable_seconds=0, wait_seconds=0.03
        )
        return True

    with patch("subprocess.run", side_effect=docker):
        await registry.register(execution, org, "action", terminate_callback=terminate)
        assert await registry.terminate_in_flight(organization_id=org) == []
        assert registry.has_unresolved(org)
        assert any(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
        with pytest.raises(PermissionError, match="revoked in-flight"):
            await registry.register("subsequent", org, "action", admission_epoch=100)


@pytest.mark.asyncio
async def test_cancellation_waits_for_contended_registry_transition(registry):
    backend = DockerContainerBackend()
    started, release = threading.Event(), threading.Event()
    waiting = asyncio.Event()

    class Lock(asyncio.Lock):
        async def acquire(self):
            if self.locked():
                waiting.set()
            return await super().acquire()

    registry._lock = Lock()

    class Process:
        returncode = 0
        pid = 12345

        async def communicate(self, input=None):
            return b'{"status":"success","result":42}', b""

        def kill(self):
            pass

        async def wait(self):
            return 0

    def cleanup(*args, **kwargs):
        started.set()
        assert release.wait(5)
        raise RuntimeError("unconfirmed under contention")

    def acknowledge_inert_create(command, receipt):
        # Supply only the earlier inert-CREATE transport boundary. The original
        # contended registry transition and cancellation assertions stay real.
        cid = "c" * 64
        receipt.write_text(cid, encoding="utf-8")
        return cid

    org = f"org-{uuid.uuid4().hex}"
    request = IsolatedExecutionRequest(
        action_id=f"action-{uuid.uuid4().hex}", organization_id=org,
        action_type="test.action", arguments={},
        profile=IsolationProfile(name="TEST", network_policy=NetworkPolicy.NONE,
                                 resources=ResourceLimits(wall_timeout_seconds=5)),
    )
    holding = False
    with (
        patch.object(backend, "is_available", return_value=True),
        patch("responsibleai.isolation.container_backend.grant_container_read"),
        patch.object(EphemeralWorkspace, "prepare_for_container"),
        patch("asyncio.create_subprocess_exec", return_value=Process()),
        patch.object(backend, "_create_stopped_container", side_effect=acknowledge_inert_create),
        patch.object(backend, "_remove_containers", side_effect=cleanup),
    ):
        task = asyncio.create_task(backend.execute(request))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            await registry._lock.acquire()
            holding = True
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(waiting.wait(), 3)
            await asyncio.sleep(0)
            assert not task.done(), "Cancellation cannot abandon its pending registry transition"
            registry._lock.release()
            holding = False
            with pytest.raises(asyncio.CancelledError):
                await task
            assert registry.has_unresolved(org)
            assert task.cancelling() == 2
        finally:
            release.set()
            if holding:
                registry._lock.release()
            await asyncio.gather(task, return_exceptions=True)
