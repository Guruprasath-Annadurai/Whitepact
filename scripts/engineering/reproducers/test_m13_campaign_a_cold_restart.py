# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Campaign A: Lost-metadata cold restart adversarial evaluation.

Executes a real Docker container, kills the parent worker abruptly with SIGKILL,
proves the container survives detached, and verifies fail-closed containment
under real multi-process cold restart with corrupted, dead-worker, and missing metadata.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    get_restore_readiness_gate,
    reset_restore_readiness_gate,
)


def _docker(*args: str) -> str:
    res = subprocess.run(
        [shutil.which("docker") or "docker", *args],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    return res.stdout.strip()


@pytest.mark.asyncio
async def test_campaign_a_real_docker_worker_kill_cold_restart_corrupted_metadata(tmp_path: Path):
    """Scenario 1: Worker killed with SIGKILL, container survives, tracking metadata corrupted.
    
    A freshly restarted application process must detect corrupted tracking and fail closed.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker not available")

    org = f"camp-a-corrupt-{uuid.uuid4().hex[:8]}"
    exec_id = f"exec-{uuid.uuid4().hex[:8]}"
    container_name = f"wp_iso_{org}_{exec_id}"
    tracking_dir = tmp_path / "tracking_corrupt"
    tracking_dir.mkdir(parents=True, exist_ok=True)

    # 1. Start worker child that launches container and records tracking
    worker_code = f"""
import json, os, subprocess, sys, time
cid = subprocess.check_output([
    sys.argv[1], 'run', '-d', '--name', sys.argv[2],
    '--entrypoint', 'python', 'python:3.12-slim',
    '-c', 'import time; time.sleep(120)'
], text=True).strip()
record = {{
    "execution_id": "{exec_id}",
    "organization_id": "{org}",
    "pid": os.getpid(),
    "container_name": sys.argv[2],
    "container_id": cid,
    "created_at": time.time(),
    "containment_status": "active"
}}
with open(sys.argv[3], "w") as f:
    json.dump(record, f)
print(json.dumps({{"pid": os.getpid(), "cid": cid}}), flush=True)
time.sleep(60)
"""
    record_path = tracking_dir / f"{org}_{exec_id}.json"
    worker = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        worker_code,
        docker_bin,
        container_name,
        str(record_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    cid = None
    try:
        # Read worker output to get PID and CID
        line = await asyncio.wait_for(worker.stdout.readline(), timeout=30)
        worker_info = json.loads(line.decode().strip())
        worker_pid = worker_info["pid"]
        cid = worker_info["cid"]

        # Verify container is actively running
        assert _docker("inspect", "-f", "{{.State.Running}}", cid) == "true"

        # 2. Abruptly kill the worker process with SIGKILL (crash simulation)
        os.kill(worker_pid, signal.SIGKILL)
        await worker.wait()
        assert worker.returncode != 0

        # Verify container survived worker crash
        assert _docker("inspect", "-f", "{{.State.Running}}", cid) == "true"

        # 3. Corrupt the tracking metadata on disk (simulating incomplete write or disk corruption)
        record_path.write_bytes(b"{\"incomplete_json_corrupt_data")

        # 4. Cold restart: run a completely separate Python subprocess as the new application
        restart_checker_code = f"""
import asyncio, sys
import responsibleai.isolation.in_flight as tracking
from pathlib import Path

tracking._DISTRIBUTED_REGISTRY_DIR = Path("{tracking_dir}")
tracking.InFlightExecutionRegistry.reset_instance()
registry = tracking.InFlightExecutionRegistry.get_instance()

# Must detect unresolved containment
has_unres = registry.has_unresolved("{org}")
if not has_unres:
    sys.exit(10)

# Must fail closed on consequential registration
async def try_register():
    try:
        await registry.register("new-exec", "{org}", "consequential-action")
        sys.exit(20)  # Should NOT reach here
    except PermissionError:
        sys.exit(0)  # Correctly failed closed!

asyncio.run(try_register())
"""
        restart_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            restart_checker_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": "src:."},
        )
        stdout, stderr = await asyncio.wait_for(restart_proc.communicate(), timeout=15)
        assert restart_proc.returncode == 0, f"Cold restart failed closed check: rc={restart_proc.returncode}, stderr={stderr.decode()}"

        # Container is still running safely isolated without foreign destruction
        assert _docker("inspect", "-f", "{{.State.Running}}", cid) == "true"

    finally:
        # Test cleanup: only remove this test's unique container
        if cid:
            try:
                _docker("rm", "-f", cid)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_campaign_a_real_docker_dead_worker_unconfirmed_containment(tmp_path: Path):
    """Scenario 2: Worker process died, container survives, tracking metadata intact with dead PID.
    
    A freshly restarted application process must detect dead-worker unconfirmed containment
    and fail closed against new registrations.
    """
    docker_bin = shutil.which("docker")
    if not docker_bin:
        pytest.skip("Docker not available")

    org = f"camp-a-dead-{uuid.uuid4().hex[:8]}"
    exec_id = f"exec-{uuid.uuid4().hex[:8]}"
    container_name = f"wp_iso_{org}_{exec_id}"
    tracking_dir = tmp_path / "tracking_dead"
    tracking_dir.mkdir(parents=True, exist_ok=True)

    worker_code = f"""
import json, os, subprocess, sys, time
cid = subprocess.check_output([
    sys.argv[1], 'run', '-d', '--name', sys.argv[2],
    '--entrypoint', 'python', 'python:3.12-slim',
    '-c', 'import time; time.sleep(120)'
], text=True).strip()
record = {{
    "execution_id": "{exec_id}",
    "organization_id": "{org}",
    "pid": os.getpid(),
    "created_at": time.time(),
    "containment_status": "active"
}}
with open(sys.argv[3], "w") as f:
    json.dump(record, f)
print(json.dumps({{"pid": os.getpid(), "cid": cid}}), flush=True)
time.sleep(60)
"""
    record_path = tracking_dir / f"{org}_{exec_id}.json"
    worker = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        worker_code,
        docker_bin,
        container_name,
        str(record_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    cid = None
    try:
        line = await asyncio.wait_for(worker.stdout.readline(), timeout=30)
        worker_info = json.loads(line.decode().strip())
        worker_pid = worker_info["pid"]
        cid = worker_info["cid"]

        assert _docker("inspect", "-f", "{{.State.Running}}", cid) == "true"

        # Abruptly kill worker
        os.kill(worker_pid, signal.SIGKILL)
        await worker.wait()

        # Cold restart in separate process
        restart_checker_code = f"""
import asyncio, sys
import responsibleai.isolation.in_flight as tracking
from pathlib import Path

tracking._DISTRIBUTED_REGISTRY_DIR = Path("{tracking_dir}")
tracking.InFlightExecutionRegistry.reset_instance()
registry = tracking.InFlightExecutionRegistry.get_instance()

# Dead worker cannot confirm containment; record must be reported as unresolved
active_remote = tracking._check_remote_worker_active("{org}")
if len(active_remote) != 1:
    sys.exit(11)
if "Worker exited; containment unconfirmed" not in active_remote[0].get("error", ""):
    sys.exit(12)

# File must NOT have been unlinked!
if not Path("{record_path}").exists():
    sys.exit(13)

# New execution attempt must fail closed
async def try_register():
    try:
        await registry.register("new-exec", "{org}", "consequential-action")
        sys.exit(20)
    except PermissionError:
        sys.exit(0)

asyncio.run(try_register())
"""
        restart_proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            restart_checker_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": "src:."},
        )
        stdout, stderr = await asyncio.wait_for(restart_proc.communicate(), timeout=15)
        assert restart_proc.returncode == 0, f"Cold restart dead-worker check failed: rc={restart_proc.returncode}, stderr={stderr.decode()}"

    finally:
        if cid:
            try:
                _docker("rm", "-f", cid)
            except Exception:
                pass


@pytest.mark.asyncio
async def test_campaign_a_total_metadata_loss_recovery_fail_closed(tmp_path: Path):
    """Scenario 3: Total metadata loss across crash.
    
    When tracking metadata is wiped, recovery startup authority in RESTORE_PENDING
    or missing Store B strictly prevents consequential admission.
    """
    empty_tracking_dir = tmp_path / "tracking_empty"
    empty_tracking_dir.mkdir(parents=True, exist_ok=True)

    cold_restart_code = f"""
import os, sys
from pathlib import Path
import responsibleai.isolation.in_flight as tracking
from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    get_restore_readiness_gate,
)

# Simulate recovery startup with RESTORE_PENDING
os.environ["WHITEPACT_RESTORE_MODE"] = "1"
os.environ.pop("WHITEPACT_STORE_B_PATH", None)

gate = get_restore_readiness_gate()
if gate.state != RestoreReadinessState.FAILED and gate.state != RestoreReadinessState.RESTORE_PENDING:
    sys.exit(31)

# Consequential traffic assertion must strictly raise RestoreQuarantineError
try:
    gate.assert_traffic_admitted()
    sys.exit(32)
except RestoreQuarantineError:
    sys.exit(0)
"""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        cold_restart_code,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env={**os.environ, "PYTHONPATH": "src:."},
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
    assert proc.returncode == 0, f"Total metadata loss fail-closed check failed: rc={proc.returncode}, stderr={stderr.decode()}"
