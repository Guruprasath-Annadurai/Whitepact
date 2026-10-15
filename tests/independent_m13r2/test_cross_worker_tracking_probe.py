# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Two-process registry counterexample, NOT a governed external tool execution."""

import asyncio
import os
import sys

import pytest
from tests.independent_m13r2.test_m13r_verified_containment import verified_input
from tests.test_m12fs_root_hardening import _configure_test_env  # noqa: F401

from responsibleai.isolation.in_flight import InFlightExecutionRegistry

WORKER = """
import asyncio, sys
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
async def main():
    registry = InFlightExecutionRegistry()
    await registry.register('remote-tracking-fixture', sys.argv[1], 'fixture')
    print('READY', flush=True)
    for line in sys.stdin:
        if line.strip() == 'STATUS':
            print(registry.count_active(sys.argv[1]), flush=True)
        if line.strip() == 'STOP':
            break
asyncio.run(main())
"""


@pytest.mark.asyncio
async def test_empty_local_registry_is_not_cross_worker_confirmation(monkeypatch):
    actor, service, kwargs = await verified_input()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", InFlightExecutionRegistry())
    # Credentials are not inherited by the child. It has no tool/effect or DB task.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "PYTHONPATH") if k in os.environ}
    child = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-c",
        WORKER,
        kwargs["org_id"],
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert await asyncio.wait_for(child.stdout.readline(), 20) == b"READY\n"
        result = await service.execute_emergency_containment(actor, **kwargs)
        child.stdin.write(b"STATUS\n")
        await child.stdin.drain()
        assert await asyncio.wait_for(child.stdout.readline(), 5) == b"1\n"
        assert result["status"] != "CONTAINED", (
            "Another worker retains active tracking; local emptiness is not distributed termination proof"
        )
    finally:
        if child.returncode is None:
            child.stdin.write(b"STOP\n")
            await child.stdin.drain()
            try:
                await asyncio.wait_for(child.wait(), 5)
            except TimeoutError:
                child.kill()
                await child.wait()
