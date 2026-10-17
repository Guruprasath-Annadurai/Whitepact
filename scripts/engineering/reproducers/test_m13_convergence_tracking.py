# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Additional tracking counterexamples; original owner assertions stay unchanged."""

import json
import os
import sys
import time
from unittest.mock import patch

import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.isolation.container_backend import DockerContainerBackend


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    tracking.InFlightExecutionRegistry.reset_instance()
    yield
    tracking.InFlightExecutionRegistry.reset_instance()


def test_dead_worker_does_not_prove_container_absence(tmp_path):
    record = tmp_path / "tenant_execution.json"
    record.write_text(json.dumps({
        "organization_id": "tenant", "execution_id": "execution", "pid": 999998,
    }))
    with patch.object(tracking.os, "kill", side_effect=ProcessLookupError):
        assert tracking._check_remote_worker_active("tenant")
    assert record.exists()


@pytest.mark.asyncio
async def test_tracking_write_failure_denies_and_retains_unconfirmed_execution(monkeypatch):
    registry = tracking.InFlightExecutionRegistry.get_instance()
    terminated = []

    def terminate():
        terminated.append(True)
        return False

    def fail_write(entry):
        raise PermissionError("tracking directory is read-only")

    monkeypatch.setattr(tracking, "_record_cross_worker_registration", fail_write)
    with pytest.raises(PermissionError):
        await registry.register("execution", "tenant", "action", terminate_callback=terminate)
    assert terminated == [True]
    assert registry.count_active("tenant") == 0
    assert registry.has_unresolved("tenant")


def test_unresolved_record_survives_same_process_registry_restart(tmp_path):
    (tmp_path / "tenant_execution.json").write_text(json.dumps({
        "organization_id": "tenant", "execution_id": "execution", "pid": os.getpid(),
        "containment_status": "unresolved",
    }))
    registry = tracking.InFlightExecutionRegistry.get_instance()
    assert registry.has_unresolved("tenant")
    assert not registry.has_unresolved("other-tenant")


def test_unresponsive_cli_respects_cleanup_budget(tmp_path):
    executable = tmp_path / "unresponsive-docker"
    executable.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(1)\n")
    executable.chmod(0o700)
    backend = DockerContainerBackend(docker_cmd=str(executable))
    start = time.monotonic()
    with pytest.raises(RuntimeError, match="containment unconfirmed"):
        backend._remove_containers(["owned-container"], stable_seconds=0, wait_seconds=0.2)
    assert time.monotonic() - start < 0.8
