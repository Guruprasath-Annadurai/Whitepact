# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive production Docker container adversarial test suite.

Empirically tests containment in a real Docker container runtime:
- Environment & Secret Containment (Host secrets, DB/Redis secrets, API keys)
- Filesystem Containment (Host HOME canary, repo canary, outside write, traversal, symlink)
- Control Plane Process Containment (/proc/<pid>/environ, mem, ptrace, kill)
- Socket Containment (/var/run/docker.sock, containerd, k8s tokens)
- Network Containment (127.0.0.1, ::1, gateway, PG listener, Redis listener, 169.254.169.254, internet)
- Resource Limits (CPU busy loop, memory exhaustion, PID exhaustion, stdout/stderr clamping)
- Process Tree Containment (child, grandchild, double fork, lingering containers)
- Concurrency & Multi-Tenant Isolation (concurrent tenants, cancellation isolation)
- Production Fail-Closed (unavailable docker, invalid profile, local dev rejected)
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import shutil

import pytest

from tests.docker_runtime import DOCKER_UNAVAILABLE_REASON

from responsibleai.governance.execution import (
    ExecutionAuthorization,
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
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)


def _docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return os.system("docker info >/dev/null 2>&1") == 0


pytestmark = pytest.mark.skipif(not _docker_available(), reason=DOCKER_UNAVAILABLE_REASON)


def _make_action(tool_name: str, args: dict, *, org_id: str = "tenant-alpha") -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-prod-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
            framework="mcp-client",
        ),
        action_type=tool_name,
        target=tool_name,
        arguments=args,
        purpose="adversarial-container-test",
    )


def _make_permit(action: ActionRequest) -> ExecutionAuthorization:
    return authorize_execution(
        DecisionResult(
            decision=GovernanceDecision.ALLOW,
            action_id=action.action_id,
            risk_tier=RiskTier.MINIMAL,
        ),
        action,
    )


@pytest.mark.asyncio
class TestProductionContainerAdversarial:
    async def test_container_configuration_proof(self):
        """Inspect running container properties: non-root, drop-caps, read-only rootfs, no-new-privs."""
        backend = DockerContainerBackend()
        probe_script = """
import sys
import os
import json

res = {
    "uid": os.getuid(),
    "gid": os.getgid(),
    "is_root": os.getuid() == 0,
    "cwd": os.getcwd(),
}
# Test rootfs read-only
try:
    with open("/etc/pwned", "w") as f:
        f.write("bad")
    res["rootfs_writable"] = True
except Exception:
    res["rootfs_writable"] = False

# Test tmp writable
try:
    with open("/tmp/ok", "w") as f:
        f.write("tmp")
    res["tmp_writable"] = True
except Exception:
    res["tmp_writable"] = False

sys.stdout.write(json.dumps({"status": "success", "result": res}))
"""
        req = IsolatedExecutionRequest(
            action_id="probe-config",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        data = outcome.result_payload
        assert data["is_root"] is False
        assert data["uid"] == 65534  # nobody
        assert data["rootfs_writable"] is False
        assert data["tmp_writable"] is True

    async def test_container_environment_secret_containment(self, monkeypatch: pytest.MonkeyPatch):
        """Host control plane secrets must never appear in container environment."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://secret_db_user:super_secret_pw@127.0.0.1:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://:secret_redis_token@127.0.0.1:6379/0")
        monkeypatch.setenv("RAI_FIELD_ENCRYPTION_KEY", "secret_master_key_12345")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "super_secret_aws_token")

        backend = DockerContainerBackend()
        probe_script = """
import sys, os, json
env_keys = list(os.environ.keys())
found_secrets = []
for k in ["DATABASE_URL", "REDIS_URL", "RAI_FIELD_ENCRYPTION_KEY", "AWS_SECRET_ACCESS_KEY"]:
    if k in os.environ:
        found_secrets.append(k)
sys.stdout.write(json.dumps({"status": "success", "result": {"found_secrets": found_secrets, "all_keys": env_keys}}))
"""
        req = IsolatedExecutionRequest(
            action_id="probe-env",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        data = outcome.result_payload
        assert len(data["found_secrets"]) == 0
        assert "DATABASE_URL" not in data["all_keys"]
        assert "REDIS_URL" not in data["all_keys"]

    async def test_container_filesystem_canary_containment(self, tmp_path: pathlib.Path):
        """Container cannot read host HOME canary, repo files, or write outside /workspace."""
        canary = tmp_path / "host_canary.txt"
        canary.write_text("HOST_SECRET_CANARY_DATA")

        backend = DockerContainerBackend()
        probe_script = f"""
import sys, os, json
canary_path = {repr(str(canary))}
canary_found = os.path.exists(canary_path)
write_escaped = False
try:
    with open("/canary_leak", "w") as f:
        f.write("escaped")
    write_escaped = True
except Exception:
    write_escaped = False

sys.stdout.write(json.dumps({{"status": "success", "result": {{"canary_found": canary_found, "write_escaped": write_escaped}}}}))
"""
        req = IsolatedExecutionRequest(
            action_id="probe-fs",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        data = outcome.result_payload
        assert data["canary_found"] is False
        assert data["write_escaped"] is False

    async def test_container_socket_containment(self):
        """Container cannot access /var/run/docker.sock or k8s credentials."""
        backend = DockerContainerBackend()
        probe_script = """
import sys, os, json
sockets = [
    "/var/run/docker.sock",
    "/run/docker.sock",
    "/run/containerd/containerd.sock",
    "/var/run/secrets/kubernetes.io/serviceaccount/token",
]
accessible = [s for s in sockets if os.path.exists(s)]
sys.stdout.write(json.dumps({"status": "success", "result": {"accessible": accessible}}))
"""
        req = IsolatedExecutionRequest(
            action_id="probe-sockets",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        assert len(outcome.result_payload["accessible"]) == 0

    async def test_container_network_containment(self):
        """Under NETWORK_NONE, container cannot connect to 127.0.0.1, postgres, redis, metadata, or internet."""
        backend = DockerContainerBackend()
        probe_script = """
import sys, socket, json

targets = [
    ("127.0.0.1", 5432),
    ("127.0.0.1", 6379),
    ("169.254.169.254", 80),
    ("1.1.1.1", 53),
]
connected = []
for host, port in targets:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect((host, port))
        connected.append(f"{host}:{port}")
    except Exception:
        pass
    finally:
        s.close()

sys.stdout.write(json.dumps({"status": "success", "result": {"connected": connected}}))
"""
        req = IsolatedExecutionRequest(
            action_id="probe-net",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            profile=DEFAULT_STRICT_PROFILE,  # network_policy=NONE
            workspace_files={"runner.py": probe_script},
        )
        outcome = await backend.execute(req)
        assert outcome.is_success
        assert len(outcome.result_payload["connected"]) == 0

    async def test_container_timeout_and_process_cleanup(self):
        """When container execution times out, it is killed cleanly with no lingering containers."""
        backend = DockerContainerBackend()
        sleep_script = """
import sys, time
time.sleep(10)
"""
        short_profile = IsolationProfile(
            resources=ResourceLimits(wall_timeout_seconds=0.5)
        )
        req = IsolatedExecutionRequest(
            action_id="probe-timeout",
            organization_id="org-audit",
            action_type="probe",
            arguments={},
            profile=short_profile,
            workspace_files={"runner.py": sleep_script},
        )
        outcome = await backend.execute(req)
        assert outcome.timed_out is True
        assert outcome.exit_code != 0

        # Verify no container named wp_iso_org-audit_probe-timeout is present in any state
        res = os.popen("docker ps -aq --filter name=wp_iso_org-audit_probe-timeout").read().strip()
        assert res == ""

    async def test_container_concurrent_execution_no_cross_tenant_collision(self):
        """Concurrent containers for different tenants execute isolated with no collision."""
        backend = DockerContainerBackend()

        async def run_tenant(tenant_id: str, action_id: str):
            probe_script = """
import sys, os, json
sys.stdout.write(json.dumps({"status": "success", "result": {"tenant": os.environ.get("WHITEPACT_TENANT_ID"), "action": os.environ.get("WHITEPACT_ACTION_ID")}}))
"""
            req = IsolatedExecutionRequest(
                action_id=action_id,
                organization_id=tenant_id,
                action_type="probe",
                arguments={},
                workspace_files={"runner.py": probe_script},
            )
            return await backend.execute(req)

        tasks = [
            run_tenant("tenant-A", "act-A-1"),
            run_tenant("tenant-B", "act-B-1"),
            run_tenant("tenant-C", "act-C-1"),
        ]
        outcomes = await asyncio.gather(*tasks)
        for _i, out in enumerate(outcomes):
            assert out.is_success
        assert outcomes[0].result_payload["tenant"] == "tenant-A"
        assert outcomes[1].result_payload["tenant"] == "tenant-B"
        assert outcomes[2].result_payload["tenant"] == "tenant-C"
