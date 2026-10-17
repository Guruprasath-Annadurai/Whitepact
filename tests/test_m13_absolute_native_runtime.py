# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real Docker lifecycle with controlled workloads; no customer authority is asserted."""

import asyncio
import json
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


@pytest.mark.asyncio
async def test_actual_worker_exit_does_not_clear_running_container(tmp_path):
    """A real exited child process leaves a real controlled container unresolved."""
    import os

    org = f"abs-crash-{uuid.uuid4().hex}"
    name = f"wp_iso_{org}_owned"
    image = os.environ["WHITEPACT_ISOLATION_IMAGE"]
    child = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import json,os,subprocess,sys; "
        "cid=subprocess.check_output([sys.argv[1],'run','-d','--name',sys.argv[2],"
        "'--entrypoint','python',sys.argv[3],'-c','import time;time.sleep(90)'],text=True); "
        "print(json.dumps({'pid':os.getpid(),'container':cid.strip()}))",
        shutil.which("docker"), name, image,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(child.communicate(), timeout=30)
        assert child.returncode == 0, stderr.decode()
        result = json.loads(stdout)
        assert docker("inspect", "-f", "{{.State.Running}}", result["container"]) == "true"
        tracking._ensure_distributed_dir()
        record = tracking._DISTRIBUTED_REGISTRY_DIR / f"{org}_execution.json"
        record.write_text(json.dumps({
            "organization_id": org, "execution_id": "execution", "pid": result["pid"],
        }))
        registry = tracking.InFlightExecutionRegistry.get_instance()
        assert registry.has_unresolved(org)
        assert record.exists()
        assert not registry.has_unresolved("other-tenant")
        with pytest.raises(PermissionError):
            await registry.register("denied", org, "controlled-action")
        assert docker("inspect", "-f", "{{.State.Running}}", result["container"]) == "true"
    finally:
        if child.returncode is None:
            child.kill()
            await child.wait()
        ids = docker("ps", "-aq", "--filter", f"name={name}").splitlines()
        if ids:
            docker("rm", "-f", *ids)
