# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A real governed tool must run inside a real container, and failures must say why.

Background (PR #180 CI, customer journey): with isolation required by default, the journey
failed with "Container exited with code 1: Unable to find image ... Pulling ...". The pull
was a red herring. The trusted runner imports ``responsibleai`` inside the container, the
stock ``python`` image does not contain it, so every isolated execution failed, and the
runner's own error went to stdout while only Docker's pull output was reported.

Two layers:

* Portable unit tests (any host): image selection, runner-error surfacing, and the narrow
  host-side routing of the single test-only database fixture.
* Real-container tests (Linux, Docker, an image built from ``Dockerfile.isolation``):
  a real tool executes in a container and returns the same result it does in-process.
"""

from __future__ import annotations

import json
import os
import subprocess
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
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import (
    DEFAULT_ISOLATION_IMAGE,
    ISOLATION_IMAGE_ENV,
    DockerContainerBackend,
    _runner_error,
)
from responsibleai.isolation.errors import IsolationError
from responsibleai.isolation.mode import (
    SYNTHETIC_HOST_TOOL_ENV,
    UNISOLATED_EXECUTION_ENV,
    synthetic_host_tool_allowed,
)

PII_TEXT = "Customer SSN is 123-45-6789, email: alice@company.com"


def _action(tool: str = "rai_scan", arguments: dict[str, Any] | None = None) -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-1", kind="api_key", org_id="tenant-a"),
            organization_id="tenant-a",
        ),
        action_type=tool,
        target=tool,
        arguments=arguments if arguments is not None else {"text": PII_TEXT},
    )


def _authorization(action: ActionRequest) -> ExecutionAuthorization:
    decision = DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action.action_id, reason_codes=["TEST"]
    )
    return authorize_execution(decision, action, ttl_seconds=60)


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    for name in (
        "ENVIRONMENT",
        "WHITEPACT_ENV",
        "RAI_ENVIRONMENT",
        "WHITEPACT_ISOLATION_BACKEND",
        UNISOLATED_EXECUTION_ENV,
        SYNTHETIC_HOST_TOOL_ENV,
        ISOLATION_IMAGE_ENV,
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


class _RecordingBroker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        self.calls.append(action.action_type)
        return {"via": "broker"}


@pytest.fixture
def host_tool_spy(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def spy(name: str, args: dict[str, Any], **_: Any) -> dict[str, Any]:
        calls.append(name)
        return {"via": "host"}

    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", spy)
    return calls


class TestImageSelection:
    def test_default_image_is_the_stock_python_image(self, clean_environment: Any) -> None:
        assert DockerContainerBackend().image_name == DEFAULT_ISOLATION_IMAGE

    def test_environment_selects_the_runtime_image(self, clean_environment: Any) -> None:
        clean_environment.setenv(
            ISOLATION_IMAGE_ENV, "registry.example/whitepact-runtime@sha256:ab"
        )
        assert DockerContainerBackend().image_name == "registry.example/whitepact-runtime@sha256:ab"

    def test_explicit_argument_wins_over_the_environment(self, clean_environment: Any) -> None:
        clean_environment.setenv(ISOLATION_IMAGE_ENV, "from-env")
        assert DockerContainerBackend(image_name="explicit").image_name == "explicit"

    def test_a_request_cannot_choose_the_image(self) -> None:
        """The image is deployment configuration, never request input."""
        import inspect

        from responsibleai.isolation.models import IsolatedExecutionRequest

        assert "image" not in {
            name.lower() for name in inspect.signature(IsolatedExecutionRequest).parameters
        }


class TestRunnerErrorSurfacing:
    def test_runner_error_json_is_extracted(self) -> None:
        out = json.dumps({"status": "error", "error": "isolated runtime unavailable: no module"})
        assert _runner_error(out) == "isolated runtime unavailable: no module"

    @pytest.mark.parametrize(
        "stdout", ["", "not json", "[]", '{"status": "success"}', '{"status": "error"}']
    )
    def test_anything_else_yields_none(self, stdout: str) -> None:
        assert _runner_error(stdout) is None

    def test_a_hostile_runner_message_is_bounded(self) -> None:
        out = json.dumps({"status": "error", "error": "x" * 10_000})
        assert len(_runner_error(out) or "") == 500


class TestSyntheticFixtureIsTheOnlyHostSideTool:
    def test_requires_its_own_explicit_switch(self, clean_environment: Any) -> None:
        assert synthetic_host_tool_allowed() is False
        clean_environment.setenv(UNISOLATED_EXECUTION_ENV, "1")
        assert synthetic_host_tool_allowed() is False, "the general opt-in must not imply it"

    @pytest.mark.parametrize("name", ["ENVIRONMENT", "WHITEPACT_ENV", "RAI_ENVIRONMENT"])
    @pytest.mark.parametrize("value", ["production", "PROD", " Production "])
    def test_any_production_marker_disables_it(
        self, clean_environment: Any, name: str, value: str
    ) -> None:
        clean_environment.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        clean_environment.setenv(name, value)
        assert synthetic_host_tool_allowed() is False

    @pytest.mark.asyncio
    async def test_real_tools_still_go_through_the_broker(
        self, clean_environment: Any, host_tool_spy: list[str]
    ) -> None:
        clean_environment.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        broker = _RecordingBroker()
        action = _action("rai_scan")
        result = await InternalToolExecutor(broker=broker).execute(_authorization(action), action)
        assert result == {"via": "broker"}
        assert broker.calls == ["rai_scan"] and host_tool_spy == []

    @pytest.mark.asyncio
    async def test_the_fixture_runs_host_side_only_with_its_switch(
        self, clean_environment: Any, host_tool_spy: list[str]
    ) -> None:
        clean_environment.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        broker = _RecordingBroker()
        action = _action(SYNTHETIC_COUNTER_TOOL, {})
        result = await InternalToolExecutor(broker=broker).execute(_authorization(action), action)
        assert result == {"via": "host"}
        assert broker.calls == [] and host_tool_spy == [SYNTHETIC_COUNTER_TOOL]

    @pytest.mark.asyncio
    async def test_without_the_switch_the_fixture_is_isolated_like_any_tool(
        self, clean_environment: Any, host_tool_spy: list[str]
    ) -> None:
        broker = _RecordingBroker()
        action = _action(SYNTHETIC_COUNTER_TOOL, {})
        await InternalToolExecutor(broker=broker).execute(_authorization(action), action)
        assert broker.calls == [SYNTHETIC_COUNTER_TOOL] and host_tool_spy == []

    @pytest.mark.asyncio
    async def test_production_never_runs_it_host_side(
        self, clean_environment: Any, host_tool_spy: list[str]
    ) -> None:
        clean_environment.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        clean_environment.setenv("ENVIRONMENT", "production")
        broker = _RecordingBroker()
        action = _action(SYNTHETIC_COUNTER_TOOL, {})
        await InternalToolExecutor(broker=broker).execute(_authorization(action), action)
        assert host_tool_spy == [], "production must not execute any tool in this process"

    @pytest.mark.asyncio
    async def test_no_broker_and_no_opt_in_refuses_a_real_tool_even_with_the_switch(
        self, clean_environment: Any, host_tool_spy: list[str]
    ) -> None:
        clean_environment.setenv(SYNTHETIC_HOST_TOOL_ENV, "1")
        executor = InternalToolExecutor(broker=object())
        executor._broker = None
        action = _action("rai_scan")
        with pytest.raises(IsolationError, match="IsolationBroker is mandatory"):
            await executor.execute(_authorization(action), action)
        assert host_tool_spy == []


# --- Real containers ---------------------------------------------------------------------


def _require_runtime_image() -> str:
    image = os.environ.get(ISOLATION_IMAGE_ENV)
    if not image:
        message = (
            f"{ISOLATION_IMAGE_ENV} is not set. Build one with "
            "`docker build -f Dockerfile.isolation -t whitepact-isolated-runtime:local .`"
        )
        if os.environ.get("WHITEPACT_REQUIRE_DOCKER_ISOLATION") == "1":
            pytest.fail(message)
        pytest.skip(f"RUNTIME_IMAGE_NOT_PROVISIONED {message}. A skip is not a pass.")
    probe = subprocess.run(  # noqa: S603, S607
        ["docker", "image", "inspect", image], capture_output=True, check=False
    )
    if probe.returncode != 0:
        pytest.fail(f"{ISOLATION_IMAGE_ENV}={image} is not present in the local Docker daemon")
    return image


@pytest.mark.usefixtures("real_container_host")
class TestRealContainerExecution:
    @pytest.mark.asyncio
    async def test_a_real_tool_executes_in_a_container_and_matches_in_process(
        self, clean_environment: Any
    ) -> None:
        image = _require_runtime_image()
        clean_environment.setenv(ISOLATION_IMAGE_ENV, image)
        clean_environment.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")

        from responsibleai.mcp.tools import dispatch_tool

        action = _action("rai_scan")
        executor = InternalToolExecutor(broker=IsolationBroker())
        isolated = await executor.execute(_authorization(action), action)
        in_process = await dispatch_tool("rai_scan", dict(action.arguments))

        assert isolated["is_blocked"] is True and isolated["has_pii"] is True
        assert {k: isolated[k] for k in ("is_blocked", "has_pii")} == {
            k: in_process[k] for k in ("is_blocked", "has_pii")
        }

    @pytest.mark.asyncio
    async def test_an_image_without_whitepact_fails_with_the_runner_s_real_reason(
        self, clean_environment: Any
    ) -> None:
        """Regression for the misleading 'Unable to find image ... Pulling' message."""
        clean_environment.setenv(ISOLATION_IMAGE_ENV, DEFAULT_ISOLATION_IMAGE)
        clean_environment.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")
        action = _action("rai_scan")
        executor = InternalToolExecutor(broker=IsolationBroker())
        with pytest.raises(IsolationError) as excinfo:
            await executor.execute(_authorization(action), action)
        message = str(excinfo.value)
        assert "isolated runtime unavailable" in message, message
        assert "Pulling" not in message.split("isolated runtime unavailable")[0][-200:]
