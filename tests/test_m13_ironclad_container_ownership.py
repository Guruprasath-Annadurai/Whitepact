# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic ownership/cleanup regressions, not native Docker qualification."""

import asyncio
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import IsolatedExecutionRequest


class Process:
    returncode = 0
    pid = 12345

    async def communicate(self, input=None):
        return b'{"status":"success","result":42}', b""

    async def wait(self):
        return 0

    def kill(self):
        self.returncode = -9


@pytest.fixture
def backend(monkeypatch, tmp_path):
    InFlightExecutionRegistry.reset_instance()
    monkeypatch.setattr(
        "responsibleai.isolation.in_flight._DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking"
    )
    monkeypatch.setattr(EphemeralWorkspace, "prepare_for_container", lambda *a, **k: None)
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.grant_container_read", lambda *a: None
    )
    instance = DockerContainerBackend()
    monkeypatch.setattr(instance, "is_available", lambda: True)
    yield instance
    InFlightExecutionRegistry.reset_instance()


def request(org="owner"):
    return IsolatedExecutionRequest(
        action_id="ownership", organization_id=org, action_type="noop", arguments={}
    )


@pytest.mark.asyncio
async def test_workspace_forged_cid_cannot_target_another_container(backend, monkeypatch):
    foreign = "f" * 64
    targets = []

    async def spawn(*command, **kwargs):
        mount = next(
            value for value in command if value.startswith("-v=") and ":/workspace:" in value
        )
        workspace = Path(mount[3:].split(":/workspace:", 1)[0])
        (workspace / ".container.cid").write_text(foreign)
        return Process()

    async def cleanup(selected, **kwargs):
        targets.extend(selected)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", cleanup)
    outcome = await backend.execute(request())
    assert outcome.result_payload == 42
    assert foreign not in targets


@pytest.mark.parametrize("contents", [b"", b"a" * 63, b"a" * 65, b"g" * 64, b"\xff" * 64])
def test_incomplete_or_invalid_receipt_is_not_creation_proof(tmp_path, contents):
    receipt = tmp_path / "cid"
    receipt.write_bytes(contents)
    assert DockerContainerBackend._trusted_container_id(receipt) is None


@pytest.mark.parametrize("kind", ["missing", "symlink", "fifo", "hardlink", "directory"])
def test_nonprivate_file_shapes_are_not_creation_proof(tmp_path, kind):
    receipt = tmp_path / "cid"
    original = tmp_path / "original"
    original.write_text("a" * 64)
    if kind == "symlink":
        receipt.symlink_to(original)
    elif kind == "fifo":
        os.mkfifo(receipt)
    elif kind == "hardlink":
        os.link(original, receipt)
    elif kind == "directory":
        receipt.mkdir()
    assert DockerContainerBackend._trusted_container_id(receipt) is None


def test_unreadable_receipt_is_not_creation_proof(tmp_path, monkeypatch):
    receipt = tmp_path / "cid"
    receipt.write_text("a" * 64)

    def denied(*args, **kwargs):
        raise PermissionError("unreadable")

    monkeypatch.setattr(os, "open", denied)
    assert DockerContainerBackend._trusted_container_id(receipt) is None


def test_receipt_owned_by_another_user_is_not_creation_proof(tmp_path, monkeypatch):
    receipt = tmp_path / "cid"
    receipt.write_text("a" * 64)
    info = receipt.stat()
    monkeypatch.setattr(
        os,
        "fstat",
        lambda fd: SimpleNamespace(
            st_mode=info.st_mode, st_uid=os.getuid() + 1, st_nlink=1, st_size=64
        ),
    )
    assert DockerContainerBackend._trusted_container_id(receipt) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("trusted", [True, False])
async def test_timeout_cleanup_uses_only_private_creation_receipt(backend, monkeypatch, trusted):
    owned = "a" * 64
    calls = []
    receipt_paths = []

    class TimeoutProcess(Process):
        returncode = None

        async def communicate(self, input=None):
            raise TimeoutError

    async def spawn(*command, **kwargs):
        receipt = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("--cidfile="))
        )
        mounts = [value[3:].split(":", 1)[0] for value in command if value.startswith("-v=")]
        assert all(not receipt.is_relative_to(Path(mount)) for mount in mounts)
        assert receipt.parent.stat().st_mode & 0o777 == 0o700
        assert not receipt.exists()
        receipt.write_text(owned if trusted else "partial")
        receipt_paths.append(receipt)
        return TimeoutProcess()

    async def cleanup(targets, **kwargs):
        assert receipt_paths[0].exists()
        calls.append((targets, kwargs))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", cleanup)
    outcome = await backend.execute(request())
    assert outcome.timed_out
    assert calls[0][1] == {"stable_seconds": 0.0 if trusted else 3.0, "wait_seconds": 12.0}
    assert (owned in calls[0][0]) is trusted
    assert not receipt_paths[0].parent.exists()


@pytest.mark.asyncio
async def test_rejected_admission_waits_out_late_creation_before_return(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    state = {"clock": 0.0, "inspect": 0, "present": False, "removed": False}
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time",
        SimpleNamespace(
            monotonic=lambda: state["clock"],
            sleep=lambda seconds: state.update(clock=state["clock"] + seconds),
        ),
    )

    def docker(command, **kwargs):
        if command[1] == "rm":
            if state["present"]:
                state.update(present=False, removed=True)
            return subprocess.CompletedProcess(command, 0)
        state["inspect"] += 1
        # An early absent observation is insufficient: creation arrives later.
        if state["inspect"] == 2:
            state["present"] = True
        return subprocess.CompletedProcess(
            command,
            0 if state["present"] else 1,
            stderr="" if state["present"] else f"Error: No such container: {command[-1]}",
        )

    monkeypatch.setattr(subprocess, "run", docker)
    pending = Process()
    pending.returncode = None
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=pending)
    )
    outcome = await backend.execute(request())
    assert outcome.exit_code == -9
    assert state["removed"] and not state["present"]
    assert state["clock"] >= 3.2
    assert registry.count_unresolved("owner") == 1
    assert (
        "creation completion unconfirmed"
        in registry.get_unresolved_containments("owner")[0].last_termination_error
    )


@pytest.mark.asyncio
async def test_rejected_admission_inspect_uncertainty_preserves_unresolved(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1

    def failed(*args, **kwargs):
        raise RuntimeError("daemon unavailable")

    monkeypatch.setattr(backend, "_remove_containers", failed)
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=Process())
    )
    await backend.execute(request())
    assert registry.count_unresolved("owner") == 1
    assert (
        "daemon unavailable"
        in registry.get_unresolved_containments("owner")[0].last_termination_error
    )


@pytest.mark.asyncio
async def test_repeated_cancellation_cannot_interrupt_rejected_cleanup(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    entered = threading.Event()
    release = threading.Event()
    completed = threading.Event()

    def remove(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        completed.set()

    monkeypatch.setattr(backend, "_remove_containers", remove)
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=Process())
    )
    task = asyncio.create_task(backend.execute(request()))
    assert await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert completed.is_set()
    assert task.cancelling() == 2


@pytest.mark.asyncio
async def test_trusted_delayed_start_cannot_recreate_or_cross_tenant_cleanup(backend, monkeypatch):
    identities = {}
    cleanups = []
    both_created = asyncio.Event()

    class DelayedStart(Process):
        returncode = None

        async def communicate(self, input=None):
            await both_created.wait()
            raise TimeoutError

    async def spawn(*command, **kwargs):
        name = next(value.split("=", 1)[1] for value in command if value.startswith("--name="))
        receipt = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("--cidfile="))
        )
        cid = f"{len(identities) + 1:064x}"
        identities[cid] = {"name": name, "exists": True}
        receipt.write_text(cid)
        if len(identities) == 2:
            both_created.set()
        return DelayedStart()

    async def cleanup(targets, **kwargs):
        cid, name = targets
        assert identities[cid]["name"] == name
        assert kwargs["stable_seconds"] == 0
        identities[cid]["exists"] = False
        # A delayed start uses its acknowledged ID; it cannot call create.
        delayed_start_succeeds = identities[cid]["exists"]
        assert not delayed_start_succeeds
        cleanups.append((cid, name))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", cleanup)
    outcomes = await asyncio.gather(
        backend.execute(request("tenant-a")), backend.execute(request("tenant-b"))
    )
    assert all(outcome.timed_out for outcome in outcomes)
    assert len(cleanups) == len(set(cleanups)) == 2
    assert not any(row["exists"] for row in identities.values())


@pytest.mark.asyncio
async def test_rejected_admission_drains_client_before_confirming_cleanup(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    order = []

    class DrainProcess(Process):
        returncode = None

        def kill(self):
            super().kill()
            order.append("kill")

        async def communicate(self, input=None):
            order.append("drain-and-reap")
            return b"", b""

    def remove(*args, **kwargs):
        order.append("containment")

    monkeypatch.setattr(backend, "_remove_containers", remove)

    async def spawn(*command, **kwargs):
        receipt = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("--cidfile="))
        )
        receipt.write_text("a" * 64)
        return DrainProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    await backend.execute(request())
    assert order == ["kill", "drain-and-reap", "containment"]
    assert registry.count_unresolved("owner") == 0


@pytest.mark.asyncio
async def test_client_drain_failure_still_cleans_and_retains_uncertainty(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    cleaned = []

    class FailedDrain(Process):
        async def communicate(self, input=None):
            raise RuntimeError("cannot drain")

    monkeypatch.setattr(backend, "_remove_containers", lambda *a, **k: cleaned.append(True))
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=FailedDrain())
    )
    await backend.execute(request())
    assert cleaned == [True]
    assert registry.count_unresolved("owner") == 1
    assert (
        "drainage/reaping"
        in registry.get_unresolved_containments("owner")[0].last_termination_error
    )


@pytest.mark.asyncio
async def test_creation_after_absence_window_cannot_erase_tracking(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    clock = [0.0]
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time",
        SimpleNamespace(
            monotonic=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        ),
    )
    observations = []

    def absent(command, **kwargs):
        observations.append(command[1])
        return subprocess.CompletedProcess(
            command, 1, stderr=f"Error: No such container: {command[-1]}"
        )

    pending = Process()
    pending.returncode = None
    monkeypatch.setattr(subprocess, "run", absent)
    monkeypatch.setattr(
        asyncio, "create_subprocess_exec", lambda *a, **k: asyncio.sleep(0, result=pending)
    )
    await backend.execute(request())
    assert clock[0] >= 3
    assert observations.count("inspect") > 1
    # Even arbitrarily late creation remains covered by unresolved ownership;
    # repeated early absence cannot prove creation completion.
    assert registry.count_unresolved("owner") == 1
    assert registry.is_revoked("owner", admission_epoch=100)


@pytest.mark.asyncio
async def test_denied_callback_reaps_real_pipe_flooding_client(backend, monkeypatch):
    """Real host subprocess PIPE lifecycle; this does not qualify Docker."""
    registry = InFlightExecutionRegistry.get_instance()
    registry._latest_revoked_epoch["owner"] = 1
    original_spawn = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*command, **kwargs):
        receipt = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("--cidfile="))
        )
        receipt.write_text("a" * 64)
        process = await original_spawn(
            sys.executable,
            "-c",
            "import os,time; os.write(2,b'READY\\n'); os.write(1,b'x'*2097152); time.sleep(30)",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        processes.append(process)
        assert await asyncio.wait_for(process.stderr.readline(), timeout=3) == b"READY\n"
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers", lambda *a, **k: None)
    await backend.execute(request())
    assert processes[0].returncode is not None
    assert processes[0].stdout.at_eof()
    assert processes[0].stderr.at_eof()
    assert registry.count_unresolved("owner") == 0


@pytest.mark.asyncio
async def test_same_worker_retry_retains_verified_creation_acknowledgement(backend, monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    receipts = []
    calls = []

    class TimeoutProcess(Process):
        returncode = None

        async def communicate(self, input=None):
            raise TimeoutError

    async def spawn(*command, **kwargs):
        receipt = Path(
            next(value.split("=", 1)[1] for value in command if value.startswith("--cidfile="))
        )
        receipt.write_text("a" * 64)
        receipts.append(receipt)
        return TimeoutProcess()

    def remove(targets, **kwargs):
        calls.append(targets)
        if len(calls) == 1:
            raise RuntimeError("daemon unavailable")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(backend, "_remove_containers", remove)
    await backend.execute(request())
    assert registry.count_unresolved("owner") == 1
    assert not receipts[0].exists()
    resolved = await registry.retry_unresolved("owner")
    assert len(resolved) == 1
    assert calls[0] == calls[1]
    assert "a" * 64 in calls[1]
    assert registry.count_unresolved("owner") == 0
