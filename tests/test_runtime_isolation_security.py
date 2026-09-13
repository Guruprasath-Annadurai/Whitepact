# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial security tests for WhitePact Independent Runtime Isolation."""

from __future__ import annotations

import pytest

from responsibleai.governance.execution import (
    ExecutionAuthorization,
    InternalToolExecutor,
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
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.environment import build_isolated_environment, is_sensitive_env_key
from responsibleai.isolation.errors import (
    FilesystemEscapeError,
    InvalidBackendModeError,
    IsolationBackendUnavailableError,
)
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    BackendMode,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


def _make_action(tool_name: str, args: dict, *, org_id: str = "tenant-alpha") -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
            framework="mcp-client",
        ),
        action_type=tool_name,
        target=tool_name,
        arguments=args,
        purpose="audit-runtime-isolation",
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


class TestEnvironmentSanitization:
    def test_sensitive_env_key_detection(self):
        assert is_sensitive_env_key("DATABASE_URL") is True
        assert is_sensitive_env_key("REDIS_PASSWORD") is True
        assert is_sensitive_env_key("RAI_FIELD_ENCRYPTION_KEY") is True
        assert is_sensitive_env_key("JWT_SECRET_TOKEN") is True
        assert is_sensitive_env_key("API_KEY") is True
        assert is_sensitive_env_key("NORMAL_PARAM") is False

    def test_build_isolated_environment_scrubs_secrets(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@127.0.0.1:5432/db")
        monkeypatch.setenv("REDIS_URL", "redis://:secret@127.0.0.1:6379/0")
        monkeypatch.setenv("MY_APP_SECRET", "super_secret")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")

        clean_env = build_isolated_environment(
            organization_id="tenant-test",
            action_id="action-123",
            extra_env={"EVIL_SECRET_KEY": "leak_me", "SAFE_VAR": "hello"},
        )

        assert "DATABASE_URL" not in clean_env
        assert "REDIS_URL" not in clean_env
        assert "MY_APP_SECRET" not in clean_env
        assert "EVIL_SECRET_KEY" not in clean_env
        assert clean_env["SAFE_VAR"] == "hello"
        assert clean_env["WHITEPACT_SANDBOX"] == "1"
        assert clean_env["WHITEPACT_TENANT_ID"] == "tenant-test"
        assert clean_env["WHITEPACT_ACTION_ID"] == "action-123"


class TestFilesystemContainment:
    def test_ephemeral_workspace_lifecycle(self):
        ws = EphemeralWorkspace("act-1", "org-1")
        with ws:
            path = ws.path
            assert path.exists()
            ws.populate({"file.txt": "content", "nested/sub.txt": b"bytes"})
            assert (path / "file.txt").read_text() == "content"
            assert (path / "nested" / "sub.txt").read_bytes() == b"bytes"
        assert not path.exists()

    def test_traversal_attack_blocked(self):
        ws = EphemeralWorkspace("act-2", "org-2")
        with ws:
            with pytest.raises(FilesystemEscapeError):
                ws.populate({"../../etc/shadow": "hacked"})


class TestBrokerAndFailClosed:
    def test_production_forbids_local_dev_mode(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        with pytest.raises(InvalidBackendModeError):
            IsolationBroker(mode=BackendMode.LOCAL_DEV)

    def test_docker_fail_closed_when_unavailable(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")
        class FakeDeadDocker:
            def is_available(self):
                return False
        monkeypatch.setattr(
            "responsibleai.isolation.broker.DockerContainerBackend",
            FakeDeadDocker,
        )
        with pytest.raises(IsolationBackendUnavailableError):
            IsolationBroker(mode=BackendMode.DOCKER)


@pytest.mark.asyncio
class TestSubprocessExecutionIsolation:
    async def test_subprocess_execution_success(self):
        backend = LocalSubprocessBackend()
        request = IsolatedExecutionRequest(
            action_id="act-test-1",
            organization_id="org-test",
            action_type="rai_trust_score",
            arguments={"agent_id": "test-agent"},
            profile=DEFAULT_STRICT_PROFILE,
        )
        outcome = await backend.execute(request)
        assert outcome.is_success
        assert outcome.result_payload is not None
        assert "score" in outcome.result_payload or "trust_score" in outcome.result_payload or isinstance(outcome.result_payload, dict)

    async def test_subprocess_timeout_enforced(self):
        backend = LocalSubprocessBackend()
        # Request with a tiny timeout of 0.1s against a tool or process that takes longer
        short_profile = IsolationProfile(
            resources=ResourceLimits(wall_timeout_seconds=0.1)
        )
        request = IsolatedExecutionRequest(
            action_id="act-timeout",
            organization_id="org-timeout",
            action_type="rai_trust_score",
            arguments={"agent_id": "test-agent"},
            profile=short_profile,
        )
        outcome = await backend.execute(request)
        # 0.1s is shorter than python subprocess startup + dispatch_tool import time (~0.5s)
        # so it is guaranteed to time out and be killed
        assert outcome.timed_out is True
        assert outcome.exit_code != 0
        assert "timeout" in (outcome.violation or "").lower()


@pytest.mark.asyncio
class TestExecutorIntegration:
    async def test_internal_tool_executor_with_isolation_broker(self):
        broker = IsolationBroker(mode=BackendMode.LOCAL_DEV)
        executor = InternalToolExecutor(broker=broker)

        action = _make_action("rai_trust_score", {"agent_id": "agent-xyz"})
        permit = _make_permit(action)

        result = await executor.execute(permit, action)
        assert isinstance(result, dict)
