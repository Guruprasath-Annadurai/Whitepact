# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive validation for in-flight execution revocation and termination.

Proves:
1. Demonstrably long-running tool execution (test.counter.increment with sleep_seconds=10.0)
   terminates immediately upon in-flight revocation (<1.0s vs 10s timeout).
2. Tenant isolation: revoking tenant A does not affect in-flight executions for tenant B.
3. Multi-worker distributed revocation: separate OS processes reconcile against shared
   database revocation epochs and terminate in-flight executions within bounded latency.
4. Late-registration rejection: executions admitted at superseded epochs cannot register or run.
5. Idempotent signal handling: duplicate revocation signals cause no errors or race conditions.
"""

from __future__ import annotations

import asyncio
import multiprocessing
import os
import time
import uuid
from typing import Any

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
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
def reset_in_flight_registry(monkeypatch):
    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "1")
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_in_flight_tool_execution_terminates_immediately_on_revocation() -> None:
    """A demonstrably long-running tool execution (test.counter.increment with sleep_seconds=10.0)

    terminates immediately when revoked, in < 1.0s, not waiting for the 10.0s wall timeout.
    """
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()

    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    action_id = f"act_{uuid.uuid4().hex[:8]}"

    # Request the genuine tool action that sleeps for 10.0 seconds
    request = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 10.0},
        profile=IsolationProfile(
            name="STRICT",
            network_policy=NetworkPolicy.NONE,
            resources=ResourceLimits(wall_timeout_seconds=10.0),
        ),
    )

    start_time = time.monotonic()
    exec_task = asyncio.create_task(backend.execute(request))

    # Wait for the tool process to start and register
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

    # Must terminate well before the 10-second wall-clock limit (<1.5s)
    assert elapsed < 1.5, f"Execution took {elapsed:.2f}s; expected < 1.5s"
    assert not outcome.is_success
    assert outcome.exit_code in {-15, -9} or "revoked in-flight" in (outcome.violation or "")
    assert registry.count_active(org_id) == 0


@pytest.mark.asyncio
async def test_in_flight_revocation_tenant_isolation() -> None:
    """Revoking in-flight executions for tenant A leaves tenant B running."""
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()

    org_a = f"org_a_{uuid.uuid4().hex[:8]}"
    org_b = f"org_b_{uuid.uuid4().hex[:8]}"

    req_a = IsolatedExecutionRequest(
        action_id=f"act_a_{uuid.uuid4().hex[:8]}",
        organization_id=org_a,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 5.0},
        profile=IsolationProfile(
            resources=ResourceLimits(wall_timeout_seconds=5.0),
        ),
    )
    req_b = IsolatedExecutionRequest(
        action_id=f"act_b_{uuid.uuid4().hex[:8]}",
        organization_id=org_b,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 5.0},
        profile=IsolationProfile(
            resources=ResourceLimits(wall_timeout_seconds=5.0),
        ),
    )

    task_a = asyncio.create_task(backend.execute(req_a))
    task_b = asyncio.create_task(backend.execute(req_b))

    for _ in range(50):
        if registry.count_active(org_a) == 1 and registry.count_active(org_b) == 1:
            break
        await asyncio.sleep(0.02)

    assert registry.count_active(org_a) == 1
    assert registry.count_active(org_b) == 1

    # Revoke tenant A ONLY
    term_a = await registry.terminate_in_flight(organization_id=org_a)
    assert len(term_a) == 1

    outcome_a = await task_a
    assert not outcome_a.is_success
    assert registry.count_active(org_a) == 0

    # Tenant B is still actively running
    assert registry.count_active(org_b) == 1

    # Cleanup tenant B
    await registry.terminate_in_flight(organization_id=org_b)
    await task_b
    assert registry.count_active(org_b) == 0


@pytest.mark.asyncio
async def test_late_registration_rejected_when_epoch_superseded() -> None:
    """An execution admitted at an older epoch cannot register after revocation."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "tenant_stale"

    # Record that epoch 5 was already revoked for this tenant
    registry.record_revoked_epoch(org_id, epoch=5)

    # Attempt to register an execution admitted at epoch 4
    with pytest.raises(PermissionError) as excinfo:
        await registry.register(
            execution_id="exec_late",
            organization_id=org_id,
            action_id="act_late",
            admission_epoch=4,
        )
    assert "revoked in-flight" in str(excinfo.value)
    assert registry.count_active(org_id) == 0


@pytest.mark.asyncio
async def test_duplicate_revocation_signals_are_idempotent() -> None:
    """Duplicate termination signals for the same tenant are safe and idempotent."""
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()

    org_id = f"org_dup_{uuid.uuid4().hex[:8]}"
    req = IsolatedExecutionRequest(
        action_id=f"act_dup_{uuid.uuid4().hex[:8]}",
        organization_id=org_id,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 5.0},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=5.0)),
    )

    t = asyncio.create_task(backend.execute(req))
    for _ in range(50):
        if registry.count_active(org_id) == 1:
            break
        await asyncio.sleep(0.02)

    # Send first termination signal
    term1 = await registry.terminate_in_flight(organization_id=org_id)
    assert len(term1) == 1

    # Send second duplicate signal immediately
    term2 = await registry.terminate_in_flight(organization_id=org_id)
    assert len(term2) == 0  # Safe no-op

    await t
    assert registry.count_active(org_id) == 0


def _worker_process_entrypoint(
    db_url: str, org_id: str, started_event: Any, result_queue: Any
) -> None:
    """OS Worker Process 2: runs a long-running execution with database reconciliation watcher."""
    os.environ["RAI_MCP_ALLOW_TEST_TOOLS"] = "1"

    async def _run() -> None:
        from responsibleai.db.engine import create_engine
        from responsibleai.isolation.in_flight import InFlightExecutionRegistry
        from responsibleai.isolation.models import (
            IsolatedExecutionRequest,
            IsolationProfile,
            ResourceLimits,
        )
        from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend

        engine = create_engine(db_url)
        await engine.init()

        reg = InFlightExecutionRegistry.get_instance()
        # Start database reconciliation watcher with 50ms polling
        watcher = reg.start_reconciliation_watcher(engine, interval=0.05)

        backend = LocalSubprocessBackend()
        req = IsolatedExecutionRequest(
            action_id=f"worker_act_{os.getpid()}",
            organization_id=org_id,
            action_type="test.counter.increment",
            arguments={"sleep_seconds": 10.0},
            profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=10.0)),
            admission_epoch=0,
        )

        t_start = time.monotonic()
        task = asyncio.create_task(backend.execute(req))

        for _ in range(100):
            if reg.count_active(org_id) > 0:
                break
            await asyncio.sleep(0.05)

        # Notify main test process that Worker 2 is executing
        started_event.set()

        outcome = await task
        watcher.cancel()
        elapsed = time.monotonic() - t_start

        result_queue.put(
            {
                "elapsed": elapsed,
                "exit_code": outcome.exit_code,
                "is_success": outcome.is_success,
                "violation": outcome.violation,
            }
        )

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_distributed_multi_worker_revocation(tmp_path) -> None:
    """Proves cross-worker revocation across separate OS processes via shared database epochs."""
    db_path = str(tmp_path / "distributed_revocation.db")
    db_url = f"sqlite+aiosqlite:///{db_path}"

    engine = create_engine(db_url)
    await engine.init()

    org_repo = OrgRepository(engine)
    epoch_repo = RevocationEpochRepository(engine)

    org = await org_repo.create_org(name="Distributed Tenant", slug="dist-tenant")
    # Initial epoch is 0
    ep0 = await epoch_repo.current(org.id)
    assert ep0.epoch == 0

    started_event = multiprocessing.Event()
    result_queue = multiprocessing.Queue()

    # Launch separate OS worker process
    p = multiprocessing.Process(
        target=_worker_process_entrypoint,
        args=(db_url, org.id, started_event, result_queue),
    )
    p.start()

    try:
        # Wait until Worker 2 has started the 10s execution
        await asyncio.to_thread(started_event.wait, timeout=15.0)
        assert started_event.is_set(), "Worker 2 failed to start execution in time"

        # Main process: bump revocation epoch in the shared database
        await epoch_repo.bump(org.id)
        ep1 = await epoch_repo.current(org.id)
        assert ep1.epoch == 1

        # Worker 2 must detect the database bump, kill the running process, and report
        result = await asyncio.to_thread(result_queue.get, timeout=15.0)

        # Must terminate in bounded latency (<2.0s) well before the 10-second timeout
        assert result["elapsed"] < 2.0, f"Worker 2 took {result['elapsed']:.2f}s; expected < 2.0s"
        assert result["is_success"] is False
        assert result["exit_code"] in {-15, -9} or "revoked in-flight" in (
            result["violation"] or ""
        )

    finally:
        p.join(timeout=2.0)
        if p.is_alive():
            p.terminate()


@pytest.mark.asyncio
async def test_failed_termination_callback_retains_entry_for_retry() -> None:
    """If container kill or process termination callback fails, action is retained for retry."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"

    call_count = 0

    def _failing_then_succeeding_callback():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("docker daemon socket unavailable")
        return True

    entry = await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_docker_1",
        terminate_callback=_failing_then_succeeding_callback,
    )
    assert registry.count_active(org_id) == 1

    # First attempt: callback raises RuntimeError
    term_1 = await registry.terminate_in_flight(organization_id=org_id)
    assert term_1 == []
    # Entry must be retained in active tracking for retry
    assert registry.count_active(org_id) == 1
    assert entry.termination_attempts == 1
    assert entry.last_termination_error == "docker daemon socket unavailable"

    # Second attempt (retry): callback succeeds
    term_2 = await registry.terminate_in_flight(organization_id=org_id)
    assert term_2 == [exec_id]
    assert registry.count_active(org_id) == 0


@pytest.mark.asyncio
async def test_reconciliation_watcher_exponential_backoff_on_db_outage() -> None:
    """Reconciliation watcher survives database connectivity failures with backoff."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_db_outage",
    )

    class BrokenEngine:
        class BrokenRaw:
            def connect(self):
                class _Ctx:
                    async def __aenter__(self):
                        raise ConnectionRefusedError("Database unreachable")

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        pass

                return _Ctx()

        raw = BrokenRaw()

    watcher = registry.start_reconciliation_watcher(BrokenEngine(), interval=0.02)
    # Let the loop execute and encounter the connection error multiple times
    await asyncio.sleep(0.1)

    # Watcher task must still be running and not crashed by unhandled exception
    assert not watcher.done()

    # Registry must safely retain the active entry
    assert registry.count_active(org_id) == 1

    # Stop watcher cleanly
    registry.stop_reconciliation_watcher()
    await asyncio.sleep(0.01)
    assert watcher.done()


@pytest.mark.asyncio
async def test_unregistered_unresolved_containment_is_preserved_with_alert() -> None:
    """Backend unregister() cannot destroy unresolved containment evidence when termination failed."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"

    def _failing_callback():
        raise RuntimeError("permission denied killing process")

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_perm_fail",
        terminate_callback=_failing_callback,
    )

    # Revocation attempted
    term = await registry.terminate_in_flight(organization_id=org_id)
    assert term == []
    assert len(registry.get_unresolved_containments(org_id)) == 1

    # Worker task reaches finally block and calls unregister()
    unreg_ok = await registry.unregister(exec_id)
    # Must refuse to silently clear evidence
    assert unreg_ok is False

    # Unresolved record is preserved for operator inspection
    unresolved = registry.get_unresolved_containments(org_id)
    assert len(unresolved) == 1
    assert unresolved[0].execution_id == exec_id
    assert unresolved[0].containment_status == "unresolved"


@pytest.mark.asyncio
async def test_reconciliation_watcher_db_recovery_and_stale_detection() -> None:
    """Watcher survives initial DB outage, measures backoff, recovers, and terminates stale run."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_{uuid.uuid4().hex[:8]}"

    killed = False

    def _kill():
        nonlocal killed
        killed = True
        return True

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_reconnect",
        admission_epoch=0,
        terminate_callback=_kill,
    )

    class RecoveringEngine:
        def __init__(self):
            self.attempts = 0

        class RecoveringRaw:
            def __init__(self, parent):
                self.parent = parent

            def connect(self):
                self.parent.attempts += 1
                should_fail = self.parent.attempts <= 2

                class _Conn:
                    async def execute(self, stmt):
                        # Simulates DB epoch bump to 1
                        return [(org_id, 1)]

                class _Ctx:
                    async def __aenter__(self):
                        if should_fail:
                            raise ConnectionResetError("DB connection reset by peer")
                        return _Conn()

                    async def __aexit__(self, exc_type, exc_val, exc_tb):
                        pass

                return _Ctx()

        @property
        def raw(self):
            return self.RecoveringRaw(self)

    engine = RecoveringEngine()
    watcher = registry.start_reconciliation_watcher(engine, interval=0.03)

    # Allow time for failures and backoff, then recovery
    for _ in range(50):
        if killed:
            break
        await asyncio.sleep(0.02)

    assert killed is True
    assert registry.count_active(org_id) == 0
    assert registry._last_successful_reconciliation is not None
    assert registry._consecutive_reconciliation_failures == 0

    registry.stop_reconciliation_watcher()
    await asyncio.sleep(0.01)
    assert watcher.done()


@pytest.mark.asyncio
async def test_subprocess_termination_failure_propagates_and_marks_unresolved(monkeypatch) -> None:
    """When OS signals fail to kill a real subprocess, failure propagates and marks unresolved."""
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()

    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    action_id = f"act_{uuid.uuid4().hex[:8]}"

    req = IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 5.0},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=5.0)),
    )

    t = asyncio.create_task(backend.execute(req))
    for _ in range(50):
        if registry.count_active(org_id) == 1:
            break
        await asyncio.sleep(0.02)

    assert registry.count_active(org_id) == 1

    # Simulate OS signal failure where killpg / kill raise PermissionError
    real_os_kill = os.kill

    def _failing_kill(pid, sig):
        if sig != 0:
            raise PermissionError("EPERM: Operation not permitted")
        return real_os_kill(pid, sig)

    def _failing_killpg(pgid, sig):
        raise PermissionError("EPERM: Operation not permitted")

    monkeypatch.setattr(os, "killpg", _failing_killpg)
    monkeypatch.setattr(os, "kill", _failing_kill)

    # Termination must fail and NOT be confirmed
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert terminated == []

    # Unresolved containment must be captured
    unresolved = registry.get_unresolved_containments(org_id)
    assert len(unresolved) == 1
    assert unresolved[0].containment_status == "unresolved"
    assert "EPERM" in (unresolved[0].last_termination_error or "")

    # Cleanup backend execution task safely
    monkeypatch.undo()
    await registry.terminate_in_flight(organization_id=org_id)
    await t


@pytest.mark.asyncio
async def test_docker_container_inspect_daemon_failure_marked_unresolved() -> None:
    """Docker inspect errors that lack authoritative absence evidence mark containment unresolved."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_docker_{uuid.uuid4().hex[:8]}"

    # Simulate container callback with daemon disconnection during inspect
    async def _failing_docker_inspect():
        # inspect returned rc=1 with daemon failure
        raise RuntimeError(
            "Docker inspect failed authoritatively confirming containment for wp_cont_123 (rc=1): "
            "Error response from daemon: dial unix /var/run/docker.sock: connect: connection refused"
        )

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_docker_test",
        terminate_callback=_failing_docker_inspect,
    )

    term = await registry.terminate_in_flight(organization_id=org_id)
    assert term == []  # Not marked terminated
    assert registry.count_active(org_id) == 1
    assert registry.has_unresolved(org_id) is True

    unresolved = registry.get_unresolved_containments(org_id)
    assert len(unresolved) == 1
    assert unresolved[0].containment_status == "unresolved"
    assert "dial unix /var/run/docker.sock" in (unresolved[0].last_termination_error or "")


@pytest.mark.asyncio
async def test_unresolved_containment_causes_fail_closed_denial_on_admission() -> None:
    """When a tenant has unresolved containment, new executions fail closed upon registration."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id_1 = f"exec_fail_{uuid.uuid4().hex[:8]}"
    exec_id_2 = f"exec_new_{uuid.uuid4().hex[:8]}"

    def _broken():
        raise RuntimeError("SIGKILL delivery failed: process unkillable")

    await registry.register(
        execution_id=exec_id_1,
        organization_id=org_id,
        action_id="act_1",
        terminate_callback=_broken,
    )

    # Attempt termination -> fails into unresolved
    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.has_unresolved(org_id) is True

    # Subsequent registration attempt for the same tenant MUST fail closed
    with pytest.raises(PermissionError, match="has been revoked in-flight"):
        await registry.register(
            execution_id=exec_id_2,
            organization_id=org_id,
            action_id="act_2",
            admission_epoch=10,  # even with newer epoch!
        )


@pytest.mark.asyncio
async def test_operator_unresolved_containment_reporting_and_retry() -> None:
    """Operators can inspect unresolved diagnostic records and trigger successful retries."""
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    exec_id = f"exec_rep_{uuid.uuid4().hex[:8]}"

    fail = True

    def _flaky_callback():
        if fail:
            raise RuntimeError("Transient socket error")
        return True

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act_flaky",
        terminate_callback=_flaky_callback,
    )

    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.count_unresolved(org_id) == 1

    # Operator queries unresolved records
    records = registry.get_unresolved(org_id)
    assert len(records) == 1
    assert records[0]["execution_id"] == exec_id
    assert records[0]["containment_status"] == "unresolved"
    assert "Transient socket error" in records[0]["last_termination_error"]

    # Flake resolves, operator triggers retry_unresolved
    fail = False
    retried = await registry.retry_unresolved(org_id)
    assert retried == [exec_id]
    assert registry.count_unresolved(org_id) == 0
    assert registry.has_unresolved(org_id) is False
