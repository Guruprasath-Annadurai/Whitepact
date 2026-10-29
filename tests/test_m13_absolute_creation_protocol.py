# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Protocol-order unit evidence. Mocked Docker is NOT native containment proof."""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from responsibleai.isolation import container_backend as module
from responsibleai.isolation import in_flight
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import IsolationBackendUnavailableError
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)


@pytest.fixture
def protocol(monkeypatch, tmp_path):
    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    in_flight.InFlightExecutionRegistry.reset_instance()
    monkeypatch.setattr(EphemeralWorkspace, "prepare_for_container", lambda *a, **k: None)
    monkeypatch.setattr(module, "grant_container_read", lambda *a, **k: None)
    image_id = "sha256:" + "a" * 64
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({image_id: image_id}))
    backend = DockerContainerBackend(image_name=image_id)
    monkeypatch.setattr(backend, "is_available", lambda: True)
    cleanup = AsyncMock()
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", cleanup)
    events = []
    state = {"mode": "success", "receipts": []}
    cid = "c" * 64

    def create(command, **kwargs):
        if command[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                command, 0, stdout=json.dumps([{"Id": image_id, "Os": "linux"}])
            )
        if command[1:3] == ["container", "inspect"]:
            return subprocess.CompletedProcess(command, 0, stdout=image_id)
        assert command[1] == "create", "The daemon must not receive RUN"
        assert "--pull=never" in command and image_id in command
        assert kwargs["check"]
        events.append("create")
        receipt = Path(next(x.split("=", 1)[1] for x in command if x.startswith("--cidfile=")))
        state["receipts"].append(receipt)
        if state["mode"] == "delayed":
            time.sleep(0.02)
        if state["mode"] == "failure":
            raise subprocess.CalledProcessError(1, command)
        receipt.write_text("c" * (31 if state["mode"] == "partial" else 64))
        acknowledgement = "d" * 64 if state["mode"] == "mismatch" else cid
        return subprocess.CompletedProcess(command, 0, stdout=acknowledgement, stderr="")

    class Process:
        returncode = None

        async def communicate(self, input=None):
            if state["mode"] == "timeout" and self.returncode is None:
                await asyncio.sleep(60)
            if self.returncode is None:
                self.returncode = 0
            return b'{"status":"success","result":42}', b""

        def kill(self):
            self.returncode = -9

    async def start(*command, **kwargs):
        assert command[1:] == ("start", "--attach", "--interactive", cid)
        events.append("start")
        assert events[0] == "create"
        # Ownership registration must precede the first START request.
        active = in_flight.InFlightExecutionRegistry.get_instance()._active
        assert len(active) == 1
        assert next(iter(active.values())).container_id == cid
        return Process()

    monkeypatch.setattr(module.subprocess, "run", create)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", start)
    try:
        yield backend, events, state, cleanup, cid
    finally:
        # All receipts here are synthetic, private paths created by THIS test.
        for receipt in state["receipts"]:
            if receipt.exists():
                receipt.unlink()
            if receipt.parent.exists():
                receipt.parent.rmdir()
        in_flight.InFlightExecutionRegistry.reset_instance()


def request(timeout=1.0):
    return IsolatedExecutionRequest(
        action_id="unit",
        organization_id="unit-tenant",
        action_type="unit",
        arguments={},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=timeout)),
    )


@pytest.mark.asyncio
async def test_create_receipt_and_registration_precede_start(protocol):
    backend, events, _, cleanup, cid = protocol
    outcome = await backend.execute(request())
    assert outcome.is_success and outcome.result_payload == 42
    assert events == ["create", "start"]
    assert cleanup.await_args.args[0] == [cid], "Never remove a potentially reused name"


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["failure", "partial"])
async def test_unacknowledged_create_cannot_start_workload(protocol, mode):
    backend, events, state, _, _ = protocol
    state["mode"] = mode
    with pytest.raises((subprocess.CalledProcessError, IsolationBackendUnavailableError)):
        await backend.execute(request())
    assert events == ["create"]


@pytest.mark.asyncio
async def test_mismatched_create_acknowledgement_never_starts(protocol):
    backend, events, state, _, _ = protocol
    state["mode"] = "mismatch"
    with pytest.raises(IsolationBackendUnavailableError, match="acknowledgement is incomplete"):
        await backend.execute(request())
    assert events == ["create"]


@pytest.mark.asyncio
async def test_timeout_after_ack_has_exact_cid_and_is_not_revocation(protocol):
    backend, events, state, cleanup, cid = protocol
    state["mode"] = "timeout"
    for _ in range(3):
        outcome = await backend.execute(request(timeout=0.25))
        assert outcome.timed_out
        assert "wall timeout" in outcome.violation
        assert "revoked" not in outcome.violation
        assert not in_flight.InFlightExecutionRegistry.get_instance().has_unresolved("unit-tenant")
    assert events == ["create", "start"] * 3
    assert all(call.args[0] == [cid] for call in cleanup.await_args_list)


@pytest.mark.asyncio
async def test_create_time_is_not_exempt_from_wall_budget(protocol):
    backend, events, state, cleanup, cid = protocol
    state["mode"] = "delayed"
    outcome = await backend.execute(request(timeout=0.001))
    assert outcome.timed_out and not outcome.is_success
    assert events == ["create"]
    assert cleanup.await_args.args[0] == [cid]
