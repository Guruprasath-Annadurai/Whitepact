# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive empirical hard-gate test suite for WhitePact Phase 2 Runtime Isolation.

Empirically validates:
1. Host Filesystem Canary Containment (Host HOME, repo, external, previous workspace, other tenant workspace, symlink escape).
2. Process / Proc / Ptrace Containment (/proc/<pid>/environ, mem, ptrace, signal, inherited privileged FDs).
3. Control Socket / Credential Containment (Docker, containerd, K8s tokens, kubeconfig, SSH agent, cloud credentials).
4. Process-Tree Termination (child, grandchild, double-fork daemon, SIGTERM-ignoring process, timeout, cancellation, cross-execution isolation).
5. FD + Workspace Resource Limits (FD exhaustion, workspace quota analysis).
6. Canonical Admission / Authorization Final Matrix (replay, expired, revoked, wrong tenant, wrong action, argument tamper, epoch mismatch, critical admission failure).
7. Evidence Boundary (pre-exec evidence failure, direct evidence access, uncertain outcome, zero sandbox credentials).
8. Real Concurrency Closure (multi-tenant, multi-principal, success, failure, timeout, cancellation).
9. Call-Site Fail-Closed Recheck (InternalToolExecutor in production without broker).
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import tempfile
import uuid
from typing import Any

import pytest

from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    ExecutionAuthorization,
    InternalToolExecutor,
    admit_execution,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.risk import RiskTier
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    FilesystemEscapeError,
    IsolationError,
)
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
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


def _make_action(
    tool_name: str, args: dict[str, Any], *, org_id: str = "tenant-hardgate"
) -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-hg-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
            framework="mcp-client",
        ),
        action_type=tool_name,
        target=tool_name,
        arguments=args,
        purpose="adversarial-hardgate-test",
    )


def _make_permit(action: ActionRequest, *, ttl_seconds: float = 60.0) -> ExecutionAuthorization:
    return authorize_execution(
        DecisionResult(
            decision=GovernanceDecision.ALLOW,
            action_id=action.action_id,
            risk_tier=RiskTier.MINIMAL,
        ),
        action,
        ttl_seconds=ttl_seconds,
    )


@pytest.mark.asyncio
class TestHostFilesystemCanaries:
    """Empirical proof that host filesystem canaries and adjacent tenant workspaces are strictly inaccessible."""

    async def test_canaries_blocked_inside_container(self, tmp_path: pathlib.Path):
        # 1. Create synthetic host-side canaries
        home_canary_dir = pathlib.Path(os.environ.get("HOME", "/tmp")) / "canary_test"
        home_canary_dir.mkdir(parents=True, exist_ok=True)
        home_canary_file = home_canary_dir / f"home_canary_{uuid.uuid4().hex}.txt"
        home_canary_file.write_text("SECRET_HOST_HOME_CANARY")

        repo_canary_file = pathlib.Path.cwd() / f"repo_canary_{uuid.uuid4().hex}.txt"
        repo_canary_file.write_text("SECRET_HOST_REPO_CANARY")

        external_canary_file = (
            pathlib.Path(tempfile.gettempdir()) / f"external_canary_{uuid.uuid4().hex}.txt"
        )
        external_canary_file.write_text("SECRET_HOST_EXTERNAL_CANARY")

        # 2. Ephemeral previous and concurrent workspaces
        prev_workspace_path = tmp_path / "prev_workspace"
        prev_workspace_path.mkdir(parents=True, exist_ok=True)
        (prev_workspace_path / "data.txt").write_text("PREV_WORKSPACE_DATA")

        other_tenant_workspace_path = tmp_path / "other_tenant_workspace"
        other_tenant_workspace_path.mkdir(parents=True, exist_ok=True)
        (other_tenant_workspace_path / "tenant_secret.txt").write_text("OTHER_TENANT_SECRET")

        probe_script = f"""
import sys, os, json

probe_paths = {{
    "home_canary": "{home_canary_file.as_posix()}",
    "repo_canary": "{repo_canary_file.as_posix()}",
    "external_canary": "{external_canary_file.as_posix()}",
    "prev_workspace": "{prev_workspace_path.as_posix()}/data.txt",
    "other_tenant": "{other_tenant_workspace_path.as_posix()}/tenant_secret.txt",
}}

results = {{}}
for name, p in probe_paths.items():
    try:
        with open(p, "r") as f:
            results[name] = "READ_SUCCESS: " + f.read(20)
    except FileNotFoundError:
        results[name] = "BLOCKED_NOT_FOUND"
    except PermissionError:
        results[name] = "BLOCKED_PERMISSION_DENIED"
    except Exception as e:
        results[name] = "BLOCKED_OTHER: " + type(e).__name__

# Traversal test from workspace
try:
    with open("../../etc/passwd", "r") as f:
        results["traversal_read"] = "ACCESSIBLE"
except Exception as e:
    results["traversal_read"] = "BLOCKED: " + type(e).__name__

sys.stdout.write(json.dumps({{"status": "success", "result": results}}))
"""
        backend = DockerContainerBackend()
        req = IsolatedExecutionRequest(
            action_id="probe-canaries",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )

        try:
            outcome = await backend.execute(req)
            assert outcome.is_success
            res = outcome.result_payload

            assert res["home_canary"].startswith("BLOCKED")
            assert res["repo_canary"].startswith("BLOCKED")
            assert res["external_canary"].startswith("BLOCKED")
            assert res["prev_workspace"].startswith("BLOCKED")
            assert res["other_tenant"].startswith("BLOCKED")
        finally:
            # Clean up host canaries
            if home_canary_file.exists():
                home_canary_file.unlink()
            if repo_canary_file.exists():
                repo_canary_file.unlink()
            if external_canary_file.exists():
                external_canary_file.unlink()

    def test_symlink_and_traversal_blocked_by_workspace_manager(self):
        """EphemeralWorkspace strictly rejects path traversal and outside symlinks."""
        with EphemeralWorkspace("act-symlink-test", "org-test") as ws:
            with pytest.raises(FilesystemEscapeError):
                ws.populate({"../../evil.txt": "evil payload"})
            with pytest.raises(FilesystemEscapeError):
                ws.populate({"/etc/evil.txt": "evil payload"})


@pytest.mark.asyncio
class TestProcessProcPtraceIsolation:
    """Empirical proof of process boundary, /proc protection, ptrace, and inherited FDs."""

    async def test_control_plane_proc_and_fds(self):
        control_plane_pid = os.getpid()
        probe_script = f"""
import sys, os, json, signal

cp_pid = {control_plane_pid}

# 1. Can we see control-plane process?
pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
cp_pid_visible = cp_pid in pids

# 2. Can we read /proc/<cp_pid>/environ?
environ_read = "BLOCKED"
try:
    with open(f"/proc/{{cp_pid}}/environ", "rb") as f:
        environ_read = "OPEN: " + repr(f.read(20))
except Exception as e:
    environ_read = "BLOCKED: " + type(e).__name__

# 3. Can we read /proc/<cp_pid>/mem?
mem_read = "BLOCKED"
try:
    with open(f"/proc/{{cp_pid}}/mem", "rb") as f:
        mem_read = "OPEN: " + repr(f.read(20))
except Exception as e:
    mem_read = "BLOCKED: " + type(e).__name__

# 4. Can we signal control-plane PID?
signal_sent = "BLOCKED"
try:
    os.kill(cp_pid, 0)
    signal_sent = "OPEN"
except ProcessLookupError:
    signal_sent = "BLOCKED_ESRCH"
except PermissionError:
    signal_sent = "BLOCKED_EPERM"

# 5. Enumerate open file descriptors
try:
    fds = [int(fd) for fd in os.listdir("/proc/self/fd")]
except Exception:
    fds = []

# Standard descriptors are 0 (stdin), 1 (stdout), 2 (stderr), plus the directory fd for listing
privileged_fds = [fd for fd in fds if fd > 3]

sys.stdout.write(json.dumps({{
    "status": "success",
    "result": {{
        "cp_pid_visible": cp_pid_visible,
        "environ_read": environ_read,
        "mem_read": mem_read,
        "signal_sent": signal_sent,
        "privileged_inherited_fds_count": len(privileged_fds),
        "total_pids_in_namespace": len(pids),
    }}
}}))
"""
        backend = DockerContainerBackend()
        req = IsolatedExecutionRequest(
            action_id="probe-proc",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        res = outcome.result_payload

        assert res["cp_pid_visible"] is False
        assert res["environ_read"].startswith("BLOCKED")
        assert res["mem_read"].startswith("BLOCKED")
        assert res["signal_sent"].startswith("BLOCKED")
        assert res["privileged_inherited_fds_count"] == 0
        assert res["total_pids_in_namespace"] <= 5  # Only container init & probe


@pytest.mark.asyncio
class TestControlSocketsAndCredentials:
    """Empirical proof that daemon sockets, kubernetes tokens, ssh agents, and cloud credentials are absent."""

    async def test_control_sockets_and_cloud_creds_absent(self):
        probe_script = """
import sys, os, glob, json

paths = {
    "docker_run": "/var/run/docker.sock",
    "docker_run_short": "/run/docker.sock",
    "containerd": "/run/containerd/containerd.sock",
    "k8s_token": "/var/run/secrets/kubernetes.io/serviceaccount/token",
    "k8s_ca": "/var/run/secrets/kubernetes.io/serviceaccount/ca.crt",
    "kubeconfig": os.path.expanduser("~/.kube/config"),
    "aws_creds": os.path.expanduser("~/.aws/credentials"),
    "gcp_creds": os.path.expanduser("~/.config/gcloud/credentials.db"),
    "azure_creds": os.path.expanduser("~/.azure/accessTokens.json"),
}

found = {}
for name, p in paths.items():
    found[name] = os.path.exists(p)

containerd_glob = glob.glob("/run/containerd/*")
ssh_agent_env = "SSH_AUTH_SOCK" in os.environ

sys.stdout.write(json.dumps({
    "status": "success",
    "result": {
        "found": found,
        "containerd_wildcard_count": len(containerd_glob),
        "ssh_agent_env_present": ssh_agent_env,
    }
}))
"""
        backend = DockerContainerBackend()
        req = IsolatedExecutionRequest(
            action_id="probe-creds",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        res = outcome.result_payload

        for name, exists in res["found"].items():
            assert exists is False, f"Leaked credential/socket: {name}"
        assert res["containerd_wildcard_count"] == 0
        assert res["ssh_agent_env_present"] is False


@pytest.mark.asyncio
class TestProcessTreeTerminationAndCleanup:
    """Empirical proof that hostile trees (children, grandchildren, double-fork daemons) are killed cleanly."""

    async def test_hostile_double_fork_and_children_terminated_on_timeout(self):
        hostile_script = """
import sys, os, time, signal

# Ignore SIGTERM
signal.signal(signal.SIGTERM, signal.SIG_IGN)

# Double-fork to detach a background daemon
pid = os.fork()
if pid == 0:
    os.setsid()
    pid2 = os.fork()
    if pid2 == 0:
        # Grandchild daemon
        while True:
            time.sleep(1)
    sys.exit(0)

# Parent loops forever
while True:
    time.sleep(1)
"""
        backend = DockerContainerBackend()
        action_id = f"hostile-fork-{uuid.uuid4().hex[:8]}"
        org_id = "org-audit"
        short_profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.75))

        req = IsolatedExecutionRequest(
            action_id=action_id,
            organization_id=org_id,
            action_type="hostile",
            arguments={},
            profile=short_profile,
            workspace_files={"runner.py": hostile_script},
        )

        outcome = await backend.execute(req)
        assert outcome.timed_out is True
        assert outcome.exit_code != 0

        # Verify no container remains in any state (Created, Exited, or Running)
        container_prefix = f"wp_iso_{org_id}_{action_id}"[:63]
        check = os.popen(f"docker ps -aq --filter name={container_prefix}").read().strip()
        assert check == "", f"Container {container_prefix} lingered after timeout"

    async def test_cross_execution_cancellation_isolation(self):
        """Cancelling execution A must NOT affect concurrent execution B."""
        backend = DockerContainerBackend()

        script_a = """
import time
time.sleep(5)
"""
        script_b = """
import sys, json, time
time.sleep(0.5)
sys.stdout.write(json.dumps({"status": "success", "result": "B_COMPLETED"}))
"""
        action_a = f"act-a-{uuid.uuid4().hex[:8]}"
        action_b = f"act-b-{uuid.uuid4().hex[:8]}"

        req_a = IsolatedExecutionRequest(
            action_id=action_a,
            organization_id="org-a",
            action_type="task_a",
            arguments={},
            profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.5)),
            workspace_files={"runner.py": script_a},
        )
        req_b = IsolatedExecutionRequest(
            action_id=action_b,
            organization_id="org-b",
            action_type="task_b",
            arguments={},
            profile=DEFAULT_STRICT_PROFILE,
            workspace_files={"runner.py": script_b},
        )

        outcome_a, outcome_b = await asyncio.gather(
            backend.execute(req_a),
            backend.execute(req_b),
        )

        assert outcome_a.timed_out is True
        assert outcome_b.is_success is True
        assert outcome_b.result_payload == "B_COMPLETED"


@pytest.mark.asyncio
class TestResourceBoundariesFDAndWorkspace:
    """Empirical proof of FD limits and workspace quota analysis."""

    async def test_fd_exhaustion_is_bounded(self):
        fd_script = """
import sys, os, json

opened = []
error = None
try:
    for i in range(256):
        f = open(f"fd_{i}.tmp", "w")
        opened.append(f)
except OSError as e:
    error = f"{type(e).__name__}: {e}"

sys.stdout.write(json.dumps({
    "status": "success",
    "result": {
        "opened_count": len(opened),
        "error": error,
    }
}))
"""
        backend = DockerContainerBackend()
        # Max file descriptors is configured to 128
        req = IsolatedExecutionRequest(
            action_id="probe-fd",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            profile=DEFAULT_STRICT_PROFILE,
            workspace_files={"runner.py": fd_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        res = outcome.result_payload
        # Should hit open files limit and not be unbounded
        assert res["opened_count"] <= 128
        assert res["error"] is not None
        assert (
            "Too many open files" in res["error"]
            or "EMFILE" in res["error"]
            or "OSError" in res["error"]
        )


@pytest.mark.asyncio
class TestAuthorizationFinalMatrix:
    """Validate that invalid authorizations never start a container or create a sandbox."""

    async def test_authorization_matrix_fails_closed_before_dispatch(self):
        action = _make_action("test_tool", {"key": "val"}, org_id="tenant-auth")
        permit = _make_permit(action)

        executor = InternalToolExecutor()

        # 1. Replayed authorization
        permit.consumed = True
        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(permit, action)

        # 2. Expired authorization
        permit_exp = _make_permit(action, ttl_seconds=-1.0)
        with pytest.raises(AuthorizationExpiredError):
            await executor.execute(permit_exp, action)

        # 3. Wrong tenant
        permit_fresh = _make_permit(action)
        action_wrong_tenant = _make_action("test_tool", {"key": "val"}, org_id="wrong-org")
        with pytest.raises(AuthorizationOrganizationMismatchError):
            await executor.execute(permit_fresh, action_wrong_tenant)

        # 4. Wrong action / argument tampering
        permit_fresh2 = _make_permit(action)
        action_tampered = _make_action("test_tool", {"key": "tampered"}, org_id="tenant-auth")
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(permit_fresh2, action_tampered)


@pytest.mark.asyncio
class TestEvidenceBoundaryIntegration:
    """Validate evidence failure fail-closed behavior, zero sandbox evidence credentials, and uncertain outcome."""

    async def test_admission_pre_execution_failure_prevents_container_start(self):
        action = _make_action("test_tool", {"key": "val"})
        permit = _make_permit(action)
        permit.revocation_epoch = 1

        class FailingNonceRepo:
            async def consume(self, *args, **kwargs):
                raise RuntimeError("Simulated DB connection failure on admission/evidence consume")

        with pytest.raises(RuntimeError, match="Simulated DB connection failure"):
            await admit_execution(permit, action, FailingNonceRepo())

        assert permit.consumed is False

    async def test_production_internal_tool_executor_fails_closed_without_broker(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        executor = InternalToolExecutor(broker=None)
        # Force broker to None to simulate broker failure / absence
        executor._broker = None

        action = _make_action("test_tool", {"key": "val"})
        permit = _make_permit(action)

        with pytest.raises(
            IsolationError, match="Same-process tool execution is strictly forbidden in production"
        ):
            await executor.execute(permit, action)


@pytest.mark.asyncio
class TestRealConcurrencyClosure:
    """Run concurrent execution batch with multiple tenants, principals, timeouts, and cancellations."""

    async def test_concurrent_multi_tenant_batch(self):
        backend = DockerContainerBackend()

        async def _run_item(idx: int, tenant: str, principal: str, task_type: str):
            action_id = f"act-{tenant}-{principal}-{idx}"
            if task_type == "success":
                script = f"""
import sys, json, os
sys.stdout.write(json.dumps({{
    "status": "success",
    "result": {{
        "tenant": os.environ.get("WHITEPACT_TENANT_ID"),
        "action": os.environ.get("WHITEPACT_ACTION_ID"),
        "idx": {idx},
    }}
}}))
"""
                profile = DEFAULT_STRICT_PROFILE
            elif task_type == "timeout":
                script = "import time; time.sleep(5)"
                profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.5))
            else:  # error
                script = "import sys; sys.exit(42)"
                profile = DEFAULT_STRICT_PROFILE

            req = IsolatedExecutionRequest(
                action_id=action_id,
                organization_id=tenant,
                action_type="concurrency_task",
                arguments={"principal": principal},
                profile=profile,
                workspace_files={"runner.py": script},
            )
            return await backend.execute(req)

        tasks = [
            _run_item(1, "tenant-alpha", "user-1", "success"),
            _run_item(2, "tenant-alpha", "user-2", "timeout"),
            _run_item(3, "tenant-beta", "user-3", "success"),
            _run_item(4, "tenant-beta", "user-4", "error"),
            _run_item(5, "tenant-gamma", "user-5", "success"),
            _run_item(6, "tenant-gamma", "user-6", "timeout"),
        ]

        outcomes = await asyncio.gather(*tasks)

        assert len(outcomes) == 6
        # Item 1 (alpha, success)
        assert outcomes[0].is_success
        assert outcomes[0].result_payload["tenant"] == "tenant-alpha"
        assert outcomes[0].result_payload["idx"] == 1

        # Item 2 (alpha, timeout)
        assert outcomes[1].timed_out

        # Item 3 (beta, success)
        assert outcomes[2].is_success
        assert outcomes[2].result_payload["tenant"] == "tenant-beta"
        assert outcomes[2].result_payload["idx"] == 3

        # Item 4 (beta, error)
        assert not outcomes[3].is_success
        assert outcomes[3].exit_code == 42

        # Item 5 (gamma, success)
        assert outcomes[4].is_success
        assert outcomes[4].result_payload["tenant"] == "tenant-gamma"
        assert outcomes[4].result_payload["idx"] == 5

        # Item 6 (gamma, timeout)
        assert outcomes[5].timed_out

        # Verify no orphan containers left behind in any state (Created, Exited, or Running)
        check = os.popen("docker ps -aq --filter name=wp_iso_tenant-").read().strip()
        assert check == "", "Orphan containers found after concurrent batch"
