# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial stress and attack tests for resource limits:
- CPU busy loop
- Memory allocation until cap
- PID/fork exhaustion
- File descriptor exhaustion
- Stdout flood
- Stderr flood
- Production fail-closed scenarios
"""

from __future__ import annotations

import os
import shutil

import pytest

from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    InvalidBackendModeError,
    IsolationBackendUnavailableError,
)
from responsibleai.isolation.models import (
    BackendMode,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)
from tests.docker_runtime import DOCKER_UNAVAILABLE_REASON


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return os.system("docker info >/dev/null 2>&1") == 0


pytestmark = pytest.mark.skipif(not _docker_available(), reason=DOCKER_UNAVAILABLE_REASON)


@pytest.mark.asyncio
class TestProductionContainerResourceAttacks:
    async def test_cpu_busy_loop_bounded(self):
        """Infinite CPU loop is strictly bounded by wall timeout and CPU shares."""
        backend = DockerContainerBackend()
        busy_script = """
import time
start = time.time()
while True:
    pass
"""
        profile = IsolationProfile(
            resources=ResourceLimits(cpu_cores=0.5, wall_timeout_seconds=1.0)
        )
        req = IsolatedExecutionRequest(
            action_id="attack-cpu",
            organization_id="org-stress",
            action_type="stress",
            arguments={},
            profile=profile,
            workspace_files={"runner.py": busy_script},
        )
        outcome = await backend.execute(req)
        assert outcome.timed_out is True
        assert outcome.duration_seconds < 3.0  # Finished close to 1.0s timeout

    async def test_memory_allocation_cap_enforced(self):
        """Allocating beyond memory limit terminates or OOM-kills the process."""
        backend = DockerContainerBackend()
        oom_script = """
import sys
# Allocate 200MB in a 32MB capped container
try:
    data = bytearray(200 * 1024 * 1024)
    sys.stdout.write("ALLOC_SUCCESS")
except MemoryError:
    sys.stdout.write("MEMORY_ERROR_CAUGHT")
"""
        profile = IsolationProfile(
            resources=ResourceLimits(max_memory_mb=32, wall_timeout_seconds=5.0)
        )
        req = IsolatedExecutionRequest(
            action_id="attack-mem",
            organization_id="org-stress",
            action_type="stress",
            arguments={},
            profile=profile,
            workspace_files={"runner.py": oom_script},
        )
        outcome = await backend.execute(req)
        # Process should either fail with OOM (exit code 137), throw MemoryError, or fail cleanly
        assert not outcome.is_success or "MEMORY_ERROR_CAUGHT" in outcome.stdout

    async def test_pid_fork_exhaustion_bounded(self):
        """Fork bomb is strictly bounded by pids-limit (e.g. 16 PIDs)."""
        backend = DockerContainerBackend()
        fork_script = """
import os, sys, json
created = 0
for i in range(100):
    try:
        pid = os.fork()
        if pid == 0:
            os._exit(0)
        else:
            created += 1
    except OSError:
        break
sys.stdout.write(json.dumps({"status": "success", "result": {"created": created}}))
"""
        profile = IsolationProfile(resources=ResourceLimits(max_pids=16, wall_timeout_seconds=5.0))
        req = IsolatedExecutionRequest(
            action_id="attack-fork",
            organization_id="org-stress",
            action_type="stress",
            arguments={},
            profile=profile,
            workspace_files={"runner.py": fork_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        # Must be bounded by max_pids (less than 100)
        assert outcome.result_payload["created"] < 50

    async def test_stdout_and_stderr_flooding_clamped(self):
        """Stdout and stderr floods are clamped to max_output_bytes."""
        backend = DockerContainerBackend()
        flood_script = """
import sys
sys.stdout.write("A" * 500000)
sys.stderr.write("B" * 500000)
"""
        profile = IsolationProfile(
            resources=ResourceLimits(max_output_bytes=1024, wall_timeout_seconds=5.0)
        )
        req = IsolatedExecutionRequest(
            action_id="attack-flood",
            organization_id="org-stress",
            action_type="stress",
            arguments={},
            profile=profile,
            workspace_files={"runner.py": flood_script},
        )
        outcome = await backend.execute(req)
        assert len(outcome.stdout.encode("utf-8")) <= 1024
        assert len(outcome.stderr.encode("utf-8")) <= 1024


@pytest.mark.asyncio
class TestProductionFailClosedMatrix:
    async def test_fail_closed_docker_daemon_down(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")
        monkeypatch.setenv("ENVIRONMENT", "production")

        class MockUnavailableDocker:
            def is_available(self):
                return False

        monkeypatch.setattr(
            "responsibleai.isolation.broker.DockerContainerBackend", MockUnavailableDocker
        )
        with pytest.raises(IsolationBackendUnavailableError):
            IsolationBroker()

    async def test_fail_closed_local_dev_requested_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(InvalidBackendModeError):
            IsolationBroker(mode=BackendMode.LOCAL_DEV)

    async def test_fail_closed_unknown_backend_mode(self):
        with pytest.raises(InvalidBackendModeError):
            IsolationBroker(mode="evil_backend_mode")
