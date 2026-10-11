# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolation is the default: forgetting an environment variable must not disable it.

Regression for a fail-open default. Previously ``InternalToolExecutor`` built an
``IsolationBroker`` only when ``ENVIRONMENT=production`` or ``WHITEPACT_ISOLATION_BACKEND``
was set; otherwise it called ``dispatch_tool`` in-process with the host's full network and
filesystem. A deployment that omitted both variables silently bypassed Phase 2 isolation
and controlled egress for every governed tool. Now uncontained execution needs an explicit
non-production ``WHITEPACT_ALLOW_UNISOLATED_EXECUTION=1``.

The test suite itself sets that opt-in (tests/conftest.py); these tests remove it.
"""

from __future__ import annotations

from typing import Any

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
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    InvalidBackendModeError,
    IsolationBackendUnavailableError,
    IsolationError,
)
from responsibleai.isolation.mode import (
    UNISOLATED_EXECUTION_ENV,
    is_production,
    unisolated_execution_allowed,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


def _action() -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-1", kind="api_key", org_id="tenant-a"),
            organization_id="tenant-a",
        ),
        action_type="rai_scan",
        target="rai_scan",
        arguments={"text": "hello"},
    )


def _authorization(action: ActionRequest) -> ExecutionAuthorization:
    decision = DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action.action_id, reason_codes=["TEST"]
    )
    return authorize_execution(decision, action, ttl_seconds=60)


@pytest.fixture
def default_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """What an operator gets by configuring nothing."""
    for name in ("ENVIRONMENT", "WHITEPACT_ISOLATION_BACKEND", UNISOLATED_EXECUTION_ENV):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def tool_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record any attempt to run a tool in this process."""
    calls: list[str] = []

    async def spy(name: str, args: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append(name)
        return {"ran": True}

    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", spy)
    return calls


class TestPolicyModule:
    def test_default_environment_does_not_allow_unisolated(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        assert unisolated_execution_allowed() is False

    @pytest.mark.parametrize("value", ["", "0", "true", "yes", "TRUE", "on", " 1"])
    def test_only_the_exact_literal_opt_in_counts(
        self, default_environment: pytest.MonkeyPatch, value: str
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, value)
        assert unisolated_execution_allowed() is False

    def test_explicit_opt_in_is_honoured_outside_production(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        assert unisolated_execution_allowed() is True

    @pytest.mark.parametrize("env", ["production", "PRODUCTION", "Production", " production "])
    def test_production_overrides_the_opt_in(
        self, default_environment: pytest.MonkeyPatch, env: str
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        default_environment.setenv("ENVIRONMENT", env)
        assert is_production() is True
        assert unisolated_execution_allowed() is False


class TestExecutorDefaultsClosed:
    def test_default_executor_builds_an_isolation_broker(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        """No env at all: the executor must have a broker (or refuse), never None."""
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: True)
        assert InternalToolExecutor()._broker is not None

    def test_default_executor_with_no_docker_refuses_to_start(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: False)
        with pytest.raises(IsolationBackendUnavailableError):
            InternalToolExecutor()

    @pytest.mark.asyncio
    async def test_unset_environment_never_runs_the_tool_in_process(
        self, default_environment: pytest.MonkeyPatch, tool_spy: list[str]
    ) -> None:
        """Even with the broker removed, the executor must refuse, not run in-process."""
        executor = InternalToolExecutor(broker=object())
        executor._broker = None
        action = _action()
        with pytest.raises(IsolationError, match="IsolationBroker is mandatory"):
            await executor.execute(_authorization(action), action)
        assert tool_spy == []

    @pytest.mark.asyncio
    async def test_explicit_local_dev_opt_in_still_works(
        self, default_environment: pytest.MonkeyPatch, tool_spy: list[str]
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        executor = InternalToolExecutor()
        assert executor._broker is None
        action = _action()
        await executor.execute(_authorization(action), action)
        assert tool_spy == ["rai_scan"]

    @pytest.mark.asyncio
    async def test_production_ignores_the_opt_in(
        self, default_environment: pytest.MonkeyPatch, tool_spy: list[str]
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        default_environment.setenv("ENVIRONMENT", "production")
        executor = InternalToolExecutor(broker=object())
        executor._broker = None
        action = _action()
        with pytest.raises(IsolationError, match="strictly forbidden in production"):
            await executor.execute(_authorization(action), action)
        assert tool_spy == []


class TestBrokerNeverDegradesSilently:
    def test_missing_docker_without_opt_in_fails_closed(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: False)
        with pytest.raises(IsolationBackendUnavailableError, match="Failing closed"):
            IsolationBroker()

    def test_missing_docker_with_opt_in_degrades_only_when_explicitly_allowed(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: False)
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        assert isinstance(IsolationBroker().backend, LocalSubprocessBackend)

    def test_explicitly_requested_docker_never_degrades_even_with_opt_in(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: False)
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        default_environment.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")
        with pytest.raises(IsolationBackendUnavailableError):
            IsolationBroker()

    def test_local_dev_backend_requires_the_opt_in(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(InvalidBackendModeError, match=UNISOLATED_EXECUTION_ENV):
            IsolationBroker(mode="local_dev")

    def test_local_dev_backend_forbidden_in_production_even_with_opt_in(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        default_environment.setenv("ENVIRONMENT", "production")
        with pytest.raises(InvalidBackendModeError, match="forbidden in production"):
            IsolationBroker(mode="local_dev")

    def test_available_docker_is_used_without_any_env(
        self, default_environment: pytest.MonkeyPatch
    ) -> None:
        default_environment.setattr(DockerContainerBackend, "is_available", lambda self: True)
        assert isinstance(IsolationBroker().backend, DockerContainerBackend)
