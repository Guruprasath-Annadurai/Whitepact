# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real Docker lifecycle with controlled workloads; no customer authority is asserted."""

import asyncio
import shutil
import subprocess
import sys
import uuid

import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)
from tests.docker_runtime import enable_containment_probe, require_container_isolation_host


@pytest.fixture(autouse=True)
def native_host(tmp_path, monkeypatch):
    require_container_isolation_host()
    enable_containment_probe(monkeypatch)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    tracking.InFlightExecutionRegistry.reset_instance()
    yield
    tracking.InFlightExecutionRegistry.reset_instance()


def docker(*args):
    result = subprocess.run(
        [shutil.which("docker"), *args], capture_output=True, text=True, timeout=15, check=True
    )
    return result.stdout.strip()


async def running_container(org):
    deadline = asyncio.get_running_loop().time() + 20
    while asyncio.get_running_loop().time() < deadline:
        ids = await asyncio.to_thread(docker, "ps", "-q", "--filter", f"name=wp_iso_{org}_")
        if ids:
            return ids.splitlines()[0]
        await asyncio.sleep(0.05)
    pytest.fail("Actual controlled Docker workload never became running")


@pytest.mark.asyncio
@pytest.mark.parametrize("cleanup_failure", [False, True])
async def test_actual_execute_preserves_cancellation_and_containment(tmp_path, cleanup_failure):
    org = f"abs-{uuid.uuid4().hex}"
    backend = DockerContainerBackend()
    if cleanup_failure:
        # Inject CLI failures only; daemon/container are real and remain independently
        # inspectable/removable through the actual Docker binary for test cleanup.
        wrapper = tmp_path / "controlled-docker"
        wrapper.write_text(
            f"#!{sys.executable}\n"
            "import os, shutil, sys\n"
            "if sys.argv[1] in {'rm','inspect'}:\n"
            " sys.stderr.write('authorization plugin not found')\n"
            " sys.exit(1)\n"
            "real=shutil.which('docker')\n"
            "os.execv(real,[real,*sys.argv[1:]])\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        backend = DockerContainerBackend(docker_cmd=str(wrapper))
    request = IsolatedExecutionRequest(
        action_id="native-cancel", organization_id=org, action_type="test.harmless",
        arguments={}, profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=30)),
        workspace_files={"runner.py": "import time\ntime.sleep(60)\n"},
    )
    registry = tracking.InFlightExecutionRegistry.get_instance()
    task = asyncio.create_task(backend.execute(request))
    try:
        container = await running_container(org)
        assert registry.count_active(org) == 1
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), timeout=25)
        assert task.cancelling() == 2
        if cleanup_failure:
            assert registry.has_unresolved(org)
            assert docker("inspect", "-f", "{{.State.Running}}", container) == "true"
        else:
            assert registry.count_active(org) == 0
            assert not registry.has_unresolved(org)
            assert docker("ps", "-aq", "--filter", f"name=wp_iso_{org}_") == ""
    finally:
        try:
            if not task.done():
                task.cancel()
                await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=25)
        finally:
            # Only remove containers owned by this unique, disposable test tenant.
            ids = docker("ps", "-aq", "--filter", f"name=wp_iso_{org}_").splitlines()
            if ids:
                docker("rm", "-f", *ids)
