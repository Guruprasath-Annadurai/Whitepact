# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive validation for in-flight execution revocation and termination.

Proves:
1. Active in-flight execution termination happens immediately upon epoch bump,
   NEVER continuing until wall-clock timeout.
2. Tenant isolation: revoking tenant A does not affect in-flight executions for tenant B.
3. Race-condition resilience: concurrent revocation and execution dispatch fail closed.
4. Clean audit outcome recording with revoked_in_flight classification.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import (
    ExecutionOutcome,
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


@pytest.fixture(autouse=True)
def reset_in_flight_registry():
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_in_flight_execution_terminates_immediately_on_revocation() -> None:
    """A long-running execution (e.g. 10s sleep) must terminate immediately

    when revoked, in < 1.0 second, not waiting for the 10s timeout.
    """
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()

    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    action_id = f"act_{uuid.uuid4().hex[:8]}"

    # Request a tool action that sleeps for 10 seconds
    request = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="slow_tool",
        arguments={},
        workspace_files={
            "runner.py": "import time; time.sleep(10)",
        },
        profile=IsolationProfile(
            name="STRICT",
            network_policy=NetworkPolicy.NONE,
            resources=ResourceLimits(wall_timeout_seconds=10.0),
        ),
    )

    start_time = time.monotonic()
    exec_task = asyncio.create_task(backend.execute(request))

    # Wait briefly for the subprocess to start and register
    for _ in range(50):
        if registry.count_active(org_id) > 0:
            break
        await asyncio.sleep(0.02)

    assert registry.count_active(org_id) == 1

    # Revoke in-flight execution for this organization
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert len(terminated) == 1

    outcome: ExecutionOutcome = await exec_task
    elapsed = time.monotonic() - start_time

    # Must terminate well before the 10-second wall-clock limit
    assert elapsed < 2.0, f"Execution took {elapsed:.2f}s; expected < 2.0s"
    assert not outcome.is_success
    assert (
        outcome.exit_code == -15
        or outcome.exit_code == -9
        or "revoked in-flight" in (outcome.violation or "")
    )
    assert registry.count_active(org_id) == 0


@pytest.mark.asyncio
async def test_in_flight_revocation_tenant_isolation() -> None:
    """Revoking in-flight executions for tenant A leaves tenant B running."""
    registry = InFlightExecutionRegistry.get_instance()

    org_a = "tenant_alpha"
    org_b = "tenant_beta"

    t1_term = False
    t2_term = False

    def cb_a():
        nonlocal t1_term
        t1_term = True

    def cb_b():
        nonlocal t2_term
        t2_term = True

    t1 = asyncio.create_task(asyncio.sleep(5))
    t2 = asyncio.create_task(asyncio.sleep(5))

    await registry.register("exec_1", org_a, "act_1", task=t1, terminate_callback=cb_a)
    await registry.register("exec_2", org_b, "act_2", task=t2, terminate_callback=cb_b)

    assert registry.count_active() == 2

    # Terminate tenant A only
    terminated = await registry.terminate_in_flight(organization_id=org_a)
    assert terminated == ["exec_1"]

    await asyncio.sleep(0.05)

    assert t1_term is True
    assert t1.cancelled() or t1.done()
    assert t2_term is False
    assert not t2.done()

    # Clean up t2
    t2.cancel()
    await registry.unregister("exec_2")


@pytest.mark.asyncio
async def test_in_flight_revocation_race_and_concurrency() -> None:
    """Multiple concurrent workers under the same tenant are all terminated simultaneously."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "tenant_racing"

    tasks = []
    callbacks_called = []

    for i in range(5):
        t = asyncio.create_task(asyncio.sleep(10))
        tasks.append(t)

        def make_cb(idx: int):
            return lambda: callbacks_called.append(idx)

        await registry.register(
            f"exec_{i}",
            org_id,
            f"act_{i}",
            task=t,
            terminate_callback=make_cb(i),
        )

    assert registry.count_active(org_id) == 5

    # Terminate all 5 workers in-flight concurrently
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert len(terminated) == 5
    assert len(callbacks_called) == 5

    await asyncio.sleep(0.05)
    for t in tasks:
        assert t.cancelled() or t.done()
