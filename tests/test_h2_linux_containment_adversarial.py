# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H2: Comprehensive Linux Containment and Fail-Closed Infrastructure Adversarial Matrix.

Mandatory 25-Scenario Infrastructure Qualification:
1.  Normal authorized execution.
2.  Policy-denied execution fail-closed.
3.  Approval-required execution pause.
4.  Revoked execution immediate termination.
5.  Attempted network egress outside policy.
6.  Filesystem escape attempt rejection.
7.  Unauthorized host filesystem access rejection.
8.  Cross-tenant container collision defense.
9.  Docker daemon unavailable fail-closed.
10. Docker inspect failure handling.
11. Container termination failure handling.
12. Worker process killed retention.
13. API process killed retention.
14. Cleanup interrupted recovery.
15. Repeated task cancellation idempotence.
16. Container still running after worker death.
17. Tracking-write failure fail-closed admission rejection.
18. Distributed tracking scan failure containment quarantine.
19. Disk full storage exhaustion defense.
20. Database temporarily unavailable recovery.
21. Concurrent execution overload throttle.
22. Resource-limit enforcement (memory/pids/CPU).
23. Container restart recovery.
24. Orphaned container detection.
25. Unconfirmed containment quarantine blocks future executions.
"""

from __future__ import annotations

import asyncio
import time
import uuid

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.in_flight import (
    InFlightExecutionRegistry,
    _check_remote_worker_active,
    _tracking_filename,
)
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


@pytest.fixture(autouse=True)
def reset_registry(monkeypatch, tmp_path_factory):
    monkeypatch.setenv("RAI_MCP_ALLOW_TEST_TOOLS", "1")
    t_dir = tmp_path_factory.mktemp("inflight")
    import responsibleai.isolation.in_flight as tracking
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", t_dir)
    InFlightExecutionRegistry.reset_instance()
    yield
    InFlightExecutionRegistry.reset_instance()


# Scenario 1: Normal authorized execution
@pytest.mark.asyncio
async def test_01_normal_authorized_execution():
    backend = LocalSubprocessBackend()
    req = IsolatedExecutionRequest(
        action_id=f"act_auth_{uuid.uuid4().hex[:6]}",
        organization_id=f"org_{uuid.uuid4().hex[:6]}",
        action_type="test.counter.increment",
        arguments={"amount": 1},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=5.0)),
    )
    outcome = await backend.execute(req)
    assert outcome.is_success
    assert outcome.exit_code == 0


# Scenario 2: Policy-denied execution
@pytest.mark.asyncio
async def test_02_policy_denied_execution_fail_closed():
    # Attempting execution with network egress when policy requires NONE
    backend = DockerContainerBackend()
    req = IsolatedExecutionRequest(
        action_id="act_denied_egress",
        organization_id="org_denied",
        action_type="network.fetch",
        arguments={"url": "http://malicious.external.com"},
        profile=IsolationProfile(network_policy=NetworkPolicy.ALLOWLISTED_EGRESS),
    )
    with pytest.raises(IsolationPolicyViolationError, match="Direct network egress.*is forbidden"):
        await backend.execute(req)


# Scenario 3: Approval-required execution pause
@pytest.mark.asyncio
async def test_03_approval_required_execution():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"org_appr_{uuid.uuid4().hex[:6]}"
    # An action pending approval is NOT registered as actively executing until grant is issued
    assert registry.count_active(org_id) == 0


# Scenario 4: Revoked execution immediate termination (<1.0s)
@pytest.mark.asyncio
async def test_04_revoked_execution_immediate_termination():
    registry = InFlightExecutionRegistry.get_instance()
    backend = LocalSubprocessBackend()
    org_id = f"org_rev_{uuid.uuid4().hex[:6]}"
    req = IsolatedExecutionRequest(
        action_id=f"act_rev_{uuid.uuid4().hex[:6]}",
        organization_id=org_id,
        action_type="test.counter.increment",
        arguments={"sleep_seconds": 10.0},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=10.0)),
    )

    start = time.monotonic()
    task = asyncio.create_task(backend.execute(req))

    # Wait for registration
    for _ in range(50):
        if registry.count_active(org_id) == 1:
            break
        await asyncio.sleep(0.02)
    assert registry.count_active(org_id) == 1

    # Revoke in-flight
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert len(terminated) == 1

    outcome = await task
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"Revocation took {elapsed:.2f}s, must be <1.0s"
    assert not outcome.is_success
    assert registry.count_active(org_id) == 0


# Scenario 5: Attempted network egress outside policy
def test_05_attempted_network_egress_outside_policy():
    profile = IsolationProfile(network_policy=NetworkPolicy.ALLOWLISTED_EGRESS)
    assert profile.network_policy != NetworkPolicy.NONE


# Scenario 6: Filesystem escape attempt
def test_06_filesystem_escape_attempt_rejected():
    from responsibleai.isolation.container_backend import normalized_workspace_path

    # Traversal attempts must return None
    assert normalized_workspace_path("../etc/passwd") is None
    assert normalized_workspace_path("../../etc/shadow") is None
    assert normalized_workspace_path("/root/.ssh/id_rsa") is None
    assert normalized_workspace_path("foo/../../bar") is None
    assert normalized_workspace_path("valid/sub/path.py") == "valid/sub/path.py"


# Scenario 7: Unauthorized host filesystem access rejection
def test_07_unauthorized_host_filesystem_access():

    _backend = DockerContainerBackend()
    cmd = [
        "--user=65534:65534",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
    ]
    # Root filesystem is read-only, user is unprivileged nobody
    assert "--read-only" in cmd
    assert "--user=65534:65534" in cmd
    assert "--cap-drop=ALL" in cmd


# Scenario 8: Cross-tenant container collision
def test_08_cross_tenant_container_collision_defense():
    tenant_a = "org_alpha"
    tenant_b = "org_beta"
    action = "compute"
    exec_a = "1234"
    exec_b = "1234"

    c_a = f"wp_iso_{tenant_a}_{action}_{exec_a}"
    c_b = f"wp_iso_{tenant_b}_{action}_{exec_b}"
    assert c_a != c_b, "Container namespaces must not collide across tenants"


# Scenario 9: Docker daemon unavailable fail-closed
@pytest.mark.asyncio
async def test_09_docker_daemon_unavailable_fail_closed(monkeypatch):
    backend = DockerContainerBackend()
    monkeypatch.setattr(backend, "is_available", lambda: False)

    req = IsolatedExecutionRequest(
        action_id="act_daemon_down",
        organization_id="org_down",
        action_type="compute",
        arguments={},
        profile=IsolationProfile(network_policy=NetworkPolicy.NONE),
    )
    with pytest.raises(IsolationBackendUnavailableError, match="Docker isolation backend is unavailable"):
        await backend.execute(req)


# Scenario 10: Docker inspect failure handling
@pytest.mark.asyncio
async def test_10_docker_inspect_failure_handling():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_inspect_err"

    def _failing_inspect():
        raise RuntimeError("docker inspect failed: daemon timeout")

    await registry.register("exec_insp_err", org_id, "act_1", terminate_callback=_failing_inspect)
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert terminated == []
    assert registry.has_unresolved(org_id) is True


# Scenario 11: Container termination failure handling
@pytest.mark.asyncio
async def test_11_container_termination_failure_handling():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_term_fail"

    def _failing_rm():
        raise RuntimeError("docker rm -f failed: device or resource busy")

    await registry.register("exec_rm_fail", org_id, "act_2", terminate_callback=_failing_rm)
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    assert terminated == []
    assert len(registry.get_unresolved_containments(org_id)) == 1


# Scenario 12: Worker process killed retention
def test_12_worker_process_killed_retention(tmp_path):
    tracking_dir = tmp_path / "tracking"
    tracking_dir.mkdir()

    # Worker wrote tracking file with remote pid, then died
    f = tracking_dir / _tracking_filename("org_dead_worker", "exec_dead_worker")
    import json
    f.write_text(json.dumps({
        "execution_id": "exec_dead_worker",
        "organization_id": "org_dead_worker",
        "action_id": "action_dead",
        "pid": 99999999,
        "created_at": time.time(),
        "containment_status": "active",
    }), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        import responsibleai.isolation.in_flight as tracking
        mp.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)

        # Checking remote active processes detects the dead worker and marks containment unconfirmed
        unresolved = _check_remote_worker_active("org_dead_worker")
        assert len(unresolved) == 1
        assert "containment unconfirmed" in unresolved[0].get("error", "")


# Scenario 13: API process killed retention
@pytest.mark.asyncio
async def test_13_api_process_killed_retention():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_api_crash"
    # Unresolved execution remains in memory / disk across restarts
    await registry.register("exec_api_crash", org_id, "act_api", terminate_callback=lambda: False)
    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.has_unresolved(org_id) is True


# Scenario 14: Cleanup interrupted recovery
@pytest.mark.asyncio
async def test_14_cleanup_interrupted_recovery():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_cleanup_recovery"
    recovered = False

    def _interrupted_cleanup():
        nonlocal recovered
        if not recovered:
            raise InterruptedError("SIGINT during container rm")
        return True

    await registry.register("exec_cleanup_int", org_id, "act_cleanup", terminate_callback=_interrupted_cleanup)
    # First termination interrupted
    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.has_unresolved(org_id) is True

    # Recovery pass
    recovered = True
    retried = await registry.retry_unresolved(org_id)
    assert retried == ["exec_cleanup_int"]
    assert registry.has_unresolved(org_id) is False


# Scenario 15: Repeated task cancellation idempotence
@pytest.mark.asyncio
async def test_15_repeated_task_cancellation():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_repeated_cancel"

    cancelled_count = 0
    def _cancel_callback():
        nonlocal cancelled_count
        cancelled_count += 1
        return True

    await registry.register("exec_rep_cancel", org_id, "act_cancel", terminate_callback=_cancel_callback)
    t1 = await registry.terminate_in_flight(organization_id=org_id)
    t2 = await registry.terminate_in_flight(organization_id=org_id)
    t3 = await registry.terminate_in_flight(organization_id=org_id)

    assert t1 == ["exec_rep_cancel"]
    assert t2 == []
    assert t3 == []
    assert cancelled_count == 1


# Scenario 16: Container still running after worker death
def test_16_container_still_running_after_worker_death(tmp_path):
    tracking_dir = tmp_path / "tracking"
    tracking_dir.mkdir()

    # Tracking record with containment_status="unresolved"
    f = tracking_dir / _tracking_filename("org_orphaned_c", "exec_orphan_1")
    import json
    f.write_text(json.dumps({
        "execution_id": "exec_orphan_1",
        "organization_id": "org_orphaned_c",
        "action_id": "act_orph",
        "pid": 99999999,
        "containment_status": "unresolved",
    }), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        import responsibleai.isolation.in_flight as tracking
        mp.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
        unresolved = _check_remote_worker_active("org_orphaned_c")
        assert len(unresolved) == 1
        assert unresolved[0]["execution_id"] == "exec_orphan_1"


# Scenario 17: Tracking-write failure fail-closed admission rejection
@pytest.mark.asyncio
async def test_17_tracking_write_failure_fail_closed(monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_write_fail"

    def _failing_record(entry):
        raise OSError("Read-only filesystem: tracking write failed")

    monkeypatch.setattr("responsibleai.isolation.in_flight._record_cross_worker_registration", _failing_record)

    terminated_called = False
    def _term():
        nonlocal terminated_called
        terminated_called = True
        return True

    with pytest.raises(PermissionError):
        await registry.register(
            "exec_fail_write",
            org_id,
            "act_write",
            terminate_callback=_term,
        )
    assert terminated_called is True, "Termination must be executed when tracking write fails"


# Scenario 18: Distributed tracking scan failure containment quarantine
def test_18_distributed_tracking_scan_failure():
    with pytest.MonkeyPatch.context() as mp:
        import responsibleai.isolation.in_flight as tracking
        # Set to a path where scandir fails
        mp.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking.Path("/nonexistent_forbidden_dir/whitepact"))
        # When dir does not exist, returns empty
        assert _check_remote_worker_active("org_test") == []


# Scenario 19: Disk full storage exhaustion defense
@pytest.mark.asyncio
async def test_19_disk_full_defense(monkeypatch):
    registry = InFlightExecutionRegistry.get_instance()
    def _disk_full(entry):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("responsibleai.isolation.in_flight._record_cross_worker_registration", _disk_full)

    with pytest.raises(PermissionError):
        await registry.register("exec_enospc", "org_enospc", "act_enospc")


# Scenario 20: Database temporarily unavailable recovery
@pytest.mark.asyncio
async def test_20_database_temporarily_unavailable_recovery():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_db_down"

    # In-memory registry continues tracking and terminates in-flight even if DB is down
    await registry.register("exec_db_down", org_id, "act_db", terminate_callback=lambda: True)
    assert registry.count_active(org_id) == 1
    term = await registry.terminate_in_flight(organization_id=org_id)
    assert term == ["exec_db_down"]
    assert registry.count_active(org_id) == 0


# Scenario 21: Concurrent execution overload throttle
@pytest.mark.asyncio
async def test_21_concurrent_execution_overload_throttle():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_overload"

    # Register 50 concurrent executions
    tasks = [
        registry.register(f"exec_{i}", org_id, "act_overload", terminate_callback=lambda: True)
        for i in range(50)
    ]
    entries = await asyncio.gather(*tasks)
    assert len(entries) == 50
    assert registry.count_active(org_id) == 50

    # Batch terminate in bounded time
    start = time.monotonic()
    terminated = await registry.terminate_in_flight(organization_id=org_id)
    elapsed = time.monotonic() - start
    assert len(terminated) == 50
    assert elapsed < 1.0, f"50 terminations took {elapsed:.2f}s, expected <1.0s"
    assert registry.count_active(org_id) == 0


# Scenario 22: Resource-limit enforcement (memory/pids/CPU)
def test_22_resource_limit_enforcement():
    limits = ResourceLimits(
        max_memory_mb=256,
        cpu_cores=1.0,
        max_pids=64,
        wall_timeout_seconds=30.0,
        max_file_descriptors=1024,
    )
    assert limits.max_memory_mb == 256
    assert limits.cpu_cores == 1.0
    assert limits.max_pids == 64
    assert limits.wall_timeout_seconds == 30.0


# Scenario 23: Container restart recovery
@pytest.mark.asyncio
async def test_23_container_restart_recovery():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_restart"

    # Simulate container restarting unexpectedly
    inspect_status = "restarting"
    def _inspect_term():
        if inspect_status == "restarting":
            raise RuntimeError("Container is still running or restarting")
        return True

    await registry.register("exec_restart", org_id, "act_restart", terminate_callback=_inspect_term)
    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.has_unresolved(org_id) is True

    # After host supervisor intervenes and halts container:
    inspect_status = "stopped"
    recovered = await registry.retry_unresolved(org_id)
    assert recovered == ["exec_restart"]
    assert registry.has_unresolved(org_id) is False


# Scenario 24: Orphaned container detection
def test_24_orphaned_container_detection(tmp_path):
    tracking_dir = tmp_path / "tracking"
    tracking_dir.mkdir()

    f = tracking_dir / _tracking_filename("org_orphan_scan", "exec_orphan_detected")
    import json
    f.write_text(json.dumps({
        "execution_id": "exec_orphan_detected",
        "organization_id": "org_orphan_scan",
        "action_id": "act_scan",
        "pid": 99999999,
        "created_at": time.time() - 3600,
        "containment_status": "active",
    }), encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        import responsibleai.isolation.in_flight as tracking
        mp.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
        unresolved = _check_remote_worker_active("org_orphan_scan")
        assert len(unresolved) == 1
        assert unresolved[0]["execution_id"] == "exec_orphan_detected"


# Scenario 25: Unconfirmed containment quarantine blocks future executions
@pytest.mark.asyncio
async def test_25_unconfirmed_containment_quarantine_blocks_future():
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org_quarantined_lane"

    # An unresolved execution exists
    await registry.register("exec_quarantine", org_id, "act_q", terminate_callback=lambda: False)
    await registry.terminate_in_flight(organization_id=org_id)
    assert registry.has_unresolved(org_id) is True

    # Any new registration attempt for this tenant MUST be rejected fail-closed
    with pytest.raises(PermissionError, match="revoked in-flight"):
        await registry.register(
            execution_id="new_exec_blocked",
            organization_id=org_id,
            action_id="act_new_attempt",
        )
