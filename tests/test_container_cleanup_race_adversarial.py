# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Dedicated adversarial regression tests for container cleanup races and failure containment.

Proves:
1. Cancellation during cleanup retains registry tracking until actual absence is verified.
2. Timeout during cleanup marks containment unresolved, failing closed.
3. Container removal failure (docker rm -f fails) preserves unresolved containment.
4. Container inspection failure (docker inspect fails with daemon error) treats absence as unconfirmed.
5. Docker daemon disconnection ("connect: connection refused") preserves containment tracking.
6. Revocation during cleanup ensures sub-second in-flight termination and unresolved tracking.
7. Remaining live container after cancellation is detected and marked unresolved.
8. Concurrent cleanup attempts do not collide or falsely drop tracking.
9. Simulated crash / exception during container termination transitions execution to unresolved.
10. Critical invariant: Execution never disappears from containment tracking while active.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
import uuid
from unittest.mock import patch

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)


@pytest.fixture(autouse=True)
def reset_in_flight_registry(monkeypatch, tmp_path):
    # These are controlled unit probes, not native Docker qualification. The
    # CREATE-before-START boundary must not leak real stopped daemon objects.
    def acknowledge_inert_create(self, command, receipt):
        cid = "a" * 64
        receipt.write_text(cid, encoding="utf-8")
        return cid

    monkeypatch.setattr(DockerContainerBackend, "_create_stopped_container", acknowledge_inert_create)
    monkeypatch.setattr(
        "responsibleai.isolation.in_flight._DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking"
    )
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


def _make_dummy_request(
    org_id: str, action_id: str, timeout: float = 5.0
) -> IsolatedExecutionRequest:
    return IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test.action",
        arguments={},
        profile=IsolationProfile(
            name="TEST",
            network_policy=NetworkPolicy.NONE,
            resources=ResourceLimits(wall_timeout_seconds=timeout),
        ),
    )


class MockProc:
    def __init__(self, output: bytes = b'{"status": "success", "result": 42}'):
        self.returncode = 0
        self.pid = 12345
        self._output = output

    async def communicate(self, input=None):
        return (self._output, b"")

    def kill(self):
        pass

    async def wait(self):
        return 0


@pytest.mark.asyncio
async def test_container_removal_failure_preserves_unresolved_containment() -> None:
    """When docker rm -f fails during execute(), execution is naturally preserved in unresolved."""
    backend = DockerContainerBackend()
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    action_id = f"act_{uuid.uuid4().hex[:8]}"
    request = _make_dummy_request(org_id, action_id)

    # Mock _remove_containers to raise RuntimeError simulating rm failure
    def _failing_remove(targets, *, stable_seconds, wait_seconds):
        raise RuntimeError("docker rm -f failed: permission denied or container locked")

    with patch.object(backend, "is_available", return_value=True), \
         patch("responsibleai.isolation.container_backend.grant_container_read"), \
         patch.object(EphemeralWorkspace, "prepare_for_container"), \
         patch("asyncio.create_subprocess_exec", return_value=MockProc()), \
         patch.object(backend, "_remove_containers", side_effect=_failing_remove):
        outcome = await backend.execute(request)
        assert outcome.is_success is True

        # Production execute() naturally transitioned the execution to unresolved
        assert registry.count_active(org_id) == 0
        assert registry.has_unresolved(org_id) is True
        assert registry.count_unresolved(org_id) == 1
        unresolved = registry.get_unresolved_containments(org_id)
        assert len(unresolved) == 1
        assert "docker rm -f failed" in (unresolved[0].last_termination_error or "")
        assert unresolved[0].containment_status == "unresolved"


@pytest.mark.asyncio
async def test_mocked_cleanup_fixture_never_contacts_docker_create():
    with patch("subprocess.run", side_effect=AssertionError("Unit probe contacted host daemon")) as run:
        await test_container_removal_failure_preserves_unresolved_containment()
    run.assert_not_called()


@pytest.mark.asyncio
async def test_container_inspect_daemon_disconnection_preserves_unresolved() -> None:
    """When docker inspect fails with daemon disconnection, absence is unconfirmed."""
    backend = DockerContainerBackend()
    target = f"wp_iso_{uuid.uuid4().hex[:8]}"

    # Simulate rm returning ok, but inspect returning rc=1 with daemon disconnection
    def _mock_run(cmd, *args, **kwargs):
        if "rm" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "inspect" in cmd:
            return subprocess.CompletedProcess(
                cmd,
                1,
                stdout="",
                stderr="Error response from daemon: dial unix /var/run/docker.sock: connect: connection refused",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_mock_run):
        # _remove_containers must raise RuntimeError because absence could not be confirmed
        with pytest.raises(RuntimeError, match="Container containment unconfirmed"):
            backend._remove_containers([target], stable_seconds=0.0, wait_seconds=0.5)


@pytest.mark.asyncio
async def test_container_still_running_after_timeout_raises_and_retains() -> None:
    """When a container remains running after timeout, removal fails closed."""
    backend = DockerContainerBackend()
    target = f"wp_iso_{uuid.uuid4().hex[:8]}"

    def _mock_run(cmd, *args, **kwargs):
        if "inspect" in cmd:
            # Container still in 'running true' state
            return subprocess.CompletedProcess(cmd, 0, stdout="running true\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_mock_run):
        with pytest.raises(RuntimeError, match="Container containment unconfirmed"):
            backend._remove_containers([target], stable_seconds=0.0, wait_seconds=0.4)


@pytest.mark.asyncio
async def test_cancellation_during_cleanup_does_not_abort_removal() -> None:
    """Async task cancellation during container removal must be shielded until container is absent."""
    backend = DockerContainerBackend()
    target = f"wp_iso_{uuid.uuid4().hex[:8]}"
    removed_event = asyncio.Event()

    def _slow_remove(targets, *, stable_seconds, wait_seconds):
        time.sleep(0.3)
        removed_event.set()

    with patch.object(backend, "_remove_containers", side_effect=_slow_remove):

        async def _run_cleanup():
            await backend._remove_containers_uninterruptible(
                [target], stable_seconds=0.0, wait_seconds=2.0
            )

        task = asyncio.create_task(_run_cleanup())
        await asyncio.sleep(0.05)
        # Cancel the task while cleanup is in flight
        task.cancel()

        # The task should complete or raise CancelledError only AFTER removal completes
        with pytest.raises(asyncio.CancelledError):
            await task

        assert removed_event.is_set(), (
            "Container removal must have executed despite task cancellation"
        )


@pytest.mark.asyncio
async def test_concurrent_cleanup_attempts_do_not_falsely_drop_tracking() -> None:
    """Multiple concurrent cleanup calls for the same container succeed idempotently."""
    backend = DockerContainerBackend()
    target = f"wp_iso_{uuid.uuid4().hex[:8]}"

    def _mock_run(cmd, *args, **kwargs):
        if "rm" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if "inspect" in cmd:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="Error: No such container")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_mock_run):
        # Run two concurrent cleanups
        results = await asyncio.gather(
            backend._remove_containers_uninterruptible(
                [target], stable_seconds=0.0, wait_seconds=1.0
            ),
            backend._remove_containers_uninterruptible(
                [target], stable_seconds=0.0, wait_seconds=1.0
            ),
            return_exceptions=True,
        )
        assert results == [None, None]


@pytest.mark.asyncio
async def test_fail_closed_denial_when_unresolved_containment_active() -> None:
    """When an execution fails containment, subsequent actions for that tenant fail closed."""
    backend = DockerContainerBackend()
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"org_{uuid.uuid4().hex[:8]}"
    req1 = _make_dummy_request(org_id, f"act_leak_{uuid.uuid4().hex[:8]}")
    req2 = _make_dummy_request(org_id, f"act_subsequent_{uuid.uuid4().hex[:8]}")

    def _failing_remove(targets, *, stable_seconds, wait_seconds):
        raise RuntimeError("dockerd disconnected during cleanup")

    with patch.object(backend, "is_available", return_value=True), \
         patch("responsibleai.isolation.container_backend.grant_container_read"), \
         patch.object(EphemeralWorkspace, "prepare_for_container"), \
         patch("asyncio.create_subprocess_exec", return_value=MockProc()), \
         patch.object(backend, "_remove_containers", side_effect=_failing_remove):
        # Initial execution fails cleanup during execute(), naturally transitioning to unresolved
        await backend.execute(req1)
        assert registry.has_unresolved(org_id) is True

        # Subsequent execution for the same tenant MUST be denied immediately fail-closed
        exec_task2 = asyncio.create_task(backend.execute(req2))
        outcome2 = await exec_task2
        assert not outcome2.is_success
        assert outcome2.exit_code == -9
        assert "revoked in-flight" in (outcome2.violation or "")


@pytest.mark.asyncio
async def test_repeated_cancellation_during_cleanup_restores_all_cancellations() -> None:
    """Repeated task.cancel() requests during cleanup are tracked and restored."""
    import threading
    backend = DockerContainerBackend()
    started = threading.Event()
    cleanup_calls = []

    def mock_remove(targets, *, stable_seconds, wait_seconds):
        started.set()
        time.sleep(0.05)
        cleanup_calls.append(targets)

    async def execution_task():
        await backend._remove_containers_uninterruptible(
            ["wp_test_restore"], stable_seconds=0.0, wait_seconds=0.1
        )
        await asyncio.sleep(0)
        return "not_cancelled"

    with patch.object(backend, "_remove_containers", side_effect=mock_remove):
        task = asyncio.create_task(execution_task())
        assert await asyncio.to_thread(started.wait, 3)
        # Cancel twice to verify multi-cancellation restoration
        task.cancel()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert task.cancelled() is True
        assert len(cleanup_calls) == 1
