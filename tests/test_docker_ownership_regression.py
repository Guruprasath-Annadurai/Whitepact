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

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)

SLOW_SUCCESS_SCRIPT = """
import sys, json, time
time.sleep(1.0)
sys.stdout.write(json.dumps({"status": "success", "result": "ok"}))
"""

SHORT_TIMEOUT_SCRIPT = """
import time
time.sleep(10.0)
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

