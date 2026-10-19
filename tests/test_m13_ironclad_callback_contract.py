# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real callback/shared-cleanup denial contract; Docker responses are controlled."""

import asyncio
import subprocess
from types import SimpleNamespace

import pytest

from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import IsolatedExecutionRequest
from tests.test_m13_ironclad_container_ownership import Process
from tests.test_m13_ironclad_container_ownership import backend as backend


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error", ["authorization plugin not found", "No such object: x; plugin failed"]
)
async def test_actual_callback_never_accepts_plugin_error_as_absence(backend, monkeypatch, error):
    started, release = asyncio.Event(), asyncio.Event()
    clock = [0.0]

    class BufferedProcess(Process):
        async def communicate(self, input=None):
            started.set()
            await release.wait()
            return await super().communicate(input)

    def docker(command, **kwargs):
        if command[1] == "inspect":
            return subprocess.CompletedProcess(command, 1, stdout="", stderr=error)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time",
        SimpleNamespace(
            monotonic=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s)
        ),
    )
    monkeypatch.setattr(subprocess, "run", docker)
    monkeypatch.setattr(
        asyncio,
        "create_subprocess_exec",
        lambda *a, **k: asyncio.sleep(0, result=BufferedProcess()),
    )
    task = asyncio.create_task(
        backend.execute(
            IsolatedExecutionRequest(
                action_id="callback", organization_id="owner", action_type="noop", arguments={}
            )
        )
    )
    registry = InFlightExecutionRegistry.get_instance()
    try:
        await asyncio.wait_for(started.wait(), 3)
        entry = next(iter(registry._active.values()))
        # Do not replace _remove_containers: the callback must use the actual
        # production inspection/absence parser and bounded cleanup path.
        with pytest.raises(RuntimeError, match="containment unconfirmed"):
            await entry.terminate_callback()
        assert registry.count_active("owner") == 1
        release.set()
        await asyncio.wait_for(task, 3)
        assert registry.count_unresolved("owner") == 1
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
