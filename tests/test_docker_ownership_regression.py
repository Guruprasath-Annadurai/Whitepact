# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression test for WP-DKR-REV-01: Execution-ownership-safe Docker lifecycle.

Proves that concurrent executions with identical organization_id and action_id
do not interfere, do not collide with exit 125, and do not cross-delete each other.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid

import pytest

from tests.docker_runtime import DOCKER_UNAVAILABLE_REASON, docker_available

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)

pytestmark = pytest.mark.skipif(not docker_available(), reason=DOCKER_UNAVAILABLE_REASON)

SLOW_SUCCESS_SCRIPT = """
import sys, json, time
time.sleep(1.0)
sys.stdout.write(json.dumps({"status": "success", "result": "ok"}))
"""

SHORT_TIMEOUT_SCRIPT = """
import time
time.sleep(10.0)
"""

INTENTIONAL_FAILURE_SCRIPT = """
import sys, time
time.sleep(0.2)
sys.stderr.write("intentional failure in execution A\\n")
sys.exit(42)
"""

@pytest.mark.asyncio
async def test_concurrent_same_action_id_no_collision() -> None:
    """Two concurrent executions with identical organization_id and action_id
    must both succeed without name collision (exit 125).
    """
    backend = DockerContainerBackend()
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    action_id = "deterministic-action"

    req_a = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_a",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": SLOW_SUCCESS_SCRIPT},
    )
    req_b = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_b",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": SLOW_SUCCESS_SCRIPT},
    )

    outcome_a, outcome_b = await asyncio.gather(
        backend.execute(req_a),
        backend.execute(req_b),
    )

    assert outcome_a.is_success, f"Outcome A failed: exit={outcome_a.exit_code}, stderr={outcome_a.stderr}"
    assert outcome_b.is_success, f"Outcome B failed: exit={outcome_b.exit_code}, stderr={outcome_b.stderr}"

@pytest.mark.asyncio
async def test_cross_execution_cleanup_isolation() -> None:
    """Execution A timing out and cleaning up must NOT kill concurrent Execution B
    with the same organization_id and action_id.
    """
    backend = DockerContainerBackend()
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    action_id = "shared-action"

    req_short = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_timeout",
        arguments={},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.3)),
        workspace_files={"runner.py": SHORT_TIMEOUT_SCRIPT},
    )
    req_normal = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_normal",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": SLOW_SUCCESS_SCRIPT},
    )

    outcome_short, outcome_normal = await asyncio.gather(
        backend.execute(req_short),
        backend.execute(req_normal),
    )

    assert outcome_short.timed_out, "Short execution should have timed out"
    assert outcome_normal.is_success, (
        f"Normal execution failed due to cross-execution interference: "
        f"exit={outcome_normal.exit_code}, stderr={outcome_normal.stderr}"
    )


@pytest.mark.asyncio
async def test_twenty_concurrent_same_action_id_executions() -> None:
    """20 concurrent executions with identical organization_id and action_id
    must all execute in complete isolation without name collisions or cross-deletions.
    """
    backend = DockerContainerBackend()
    org_id = f"org-twenty-{uuid.uuid4().hex[:6]}"
    action_id = "same-logical-action"

    tasks = [
        backend.execute(
            IsolatedExecutionRequest(
                action_id=action_id,
                organization_id=org_id,
                action_type=f"task_{i}",
                arguments={"index": i},
                profile=DEFAULT_STRICT_PROFILE,
                workspace_files={"runner.py": SLOW_SUCCESS_SCRIPT},
            )
        )
        for i in range(20)
    ]

    outcomes = await asyncio.gather(*tasks)
    assert len(outcomes) == 20
    for i, outcome in enumerate(outcomes):
        assert outcome.is_success, (
            f"Execution {i} failed: exit={outcome.exit_code}, stderr={outcome.stderr}"
        )

    # Verify zero lingering containers for this test
    res = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=wp_iso_{org_id}_{action_id}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.stdout.strip() == "", f"Found lingering containers: {res.stdout}"


@pytest.mark.asyncio
async def test_repeated_sequential_timeout_soak() -> None:
    """WP-DKR-REV-02 (Soak): 25 sequential executions that all intentionally
    exceed execution timeout. Proves container creation, timeout observation,
    owned container termination, zero exit 125 name collisions, and zero stale
    containers across all iterations.
    """
    backend = DockerContainerBackend()
    org_id = f"org-soak-{uuid.uuid4().hex[:6]}"
    action_id = "soak-timeout-action"

    timeout_soak_iterations = 25
    exit_125_collisions = 0
    stale_containers_detected = 0

    for i in range(timeout_soak_iterations):
        req = IsolatedExecutionRequest(
            action_id=action_id,
            organization_id=org_id,
            action_type=f"soak_iter_{i}",
            arguments={"iteration": i},
            profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.25)),
            workspace_files={"runner.py": SHORT_TIMEOUT_SCRIPT},
        )
        outcome = await backend.execute(req)

        assert outcome.timed_out, f"Iteration {i} did not report timeout"
        if outcome.exit_code == 125:
            exit_125_collisions += 1

        # Check for lingering container from this iteration or previously
        check = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"name=wp_iso_{org_id}_{action_id}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lingering = check.stdout.strip()
        if lingering:
            stale_containers_detected += len(lingering.split())

    assert exit_125_collisions == 0, f"Detected exit-125 name collisions: {exit_125_collisions}"
    assert stale_containers_detected == 0, (
        f"Detected {stale_containers_detected} stale containers during soak"
    )

    # Final verification of zero lingering containers for this soak scope
    final_check = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=wp_iso_{org_id}_{action_id}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert final_check.stdout.strip() == "", (
        f"Found lingering containers after soak: {final_check.stdout}"
    )


@pytest.mark.asyncio
async def test_identical_org_action_failure_vs_running_sibling() -> None:
    """WP-DKR-REV-02 (Sibling Isolation): Two concurrent executions with IDENTICAL
    organization_id and action_id. Execution A fails intentionally while Execution B
    remains active. Verifies A's cleanup does NOT interrupt, kill, or corrupt B,
    and B finishes with full success.
    """
    backend = DockerContainerBackend()
    org_id = f"org-sibling-{uuid.uuid4().hex[:6]}"
    action_id = "identical-sibling-action"

    req_fail = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_failing_sibling",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": INTENTIONAL_FAILURE_SCRIPT},
    )
    req_running = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test_running_sibling",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": SLOW_SUCCESS_SCRIPT},
    )

    outcome_fail, outcome_running = await asyncio.gather(
        backend.execute(req_fail),
        backend.execute(req_running),
    )

    # Execution A must have failed with exit code 42
    assert not outcome_fail.is_success, "Execution A was expected to fail"
    assert outcome_fail.exit_code == 42, (
        f"Execution A expected exit 42, got {outcome_fail.exit_code}"
    )
    assert "intentional failure in execution A" in outcome_fail.stderr

    # Execution B must have remained completely unperturbed and succeeded
    assert outcome_running.is_success, (
        f"Execution B was interrupted or failed: exit={outcome_running.exit_code}, "
        f"stderr={outcome_running.stderr}"
    )
    assert outcome_running.exit_code == 0
    assert outcome_running.result_payload == "ok"

    # Neither execution must have experienced exit 125 name collision
    assert outcome_fail.exit_code != 125
    assert outcome_running.exit_code != 125

    # Zero lingering containers
    res = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=wp_iso_{org_id}_{action_id}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.stdout.strip() == "", f"Found lingering containers: {res.stdout}"
