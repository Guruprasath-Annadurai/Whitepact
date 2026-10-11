# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolation broker coordinating profile resolution, backend selection,
and execution plane isolation."""

from __future__ import annotations

import os
from typing import Any

from responsibleai.governance.execution import ExecutionAuthorization
from responsibleai.governance.models import ActionRequest
from responsibleai.isolation.backend import IsolationBackend
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
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    BackendMode,
    ExecutionOutcome,
    IsolatedExecutionRequest,
    IsolationProfile,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


class IsolationBroker:
    """Brokers execution requests to the appropriate containment backend."""

    def __init__(
        self,
        *,
        mode: BackendMode | str | None = None,
        backend: IsolationBackend | None = None,
        default_profile: IsolationProfile | None = None,
    ) -> None:
        self.default_profile = default_profile or DEFAULT_STRICT_PROFILE
        env_mode = os.environ.get("WHITEPACT_ISOLATION_BACKEND")

        try:
            if mode is None:
                if env_mode:
                    self.mode = BackendMode(env_mode)
                else:
                    self.mode = BackendMode.DOCKER
            elif isinstance(mode, str):
                self.mode = BackendMode(mode)
            else:
                self.mode = mode
        except ValueError as exc:
            raise InvalidBackendModeError(f"Unknown backend mode: {mode or env_mode}") from exc

        if backend is not None:
            self.backend = backend
        else:
            self.backend = self._init_backend()

    def _init_backend(self) -> IsolationBackend:
        if self.mode == BackendMode.LOCAL_DEV:
            if is_production():
                raise InvalidBackendModeError(
                    "LOCAL_DEV isolation backend mode is strictly forbidden in production. "
                    "Fail-closed invariant triggered."
                )
            if not unisolated_execution_allowed():
                raise InvalidBackendModeError(
                    "LOCAL_DEV provides no network or filesystem containment and requires "
                    f"{UNISOLATED_EXECUTION_ENV}=1 as an explicit local-development opt-in."
                )
            return LocalSubprocessBackend()

        if self.mode == BackendMode.DOCKER:
            docker_be = DockerContainerBackend()
            if docker_be.is_available():
                return docker_be
            # Never degrade to an uncontained backend silently. Only an explicit,
            # non-production opt-in may run without Docker, and not when Docker was
            # explicitly requested.
            explicit_docker = os.environ.get("WHITEPACT_ISOLATION_BACKEND") == "docker"
            if explicit_docker or not unisolated_execution_allowed():
                raise IsolationBackendUnavailableError(
                    "Docker container isolation backend is required but unavailable. "
                    "Failing closed. To run without isolation for local development only, "
                    f"set {UNISOLATED_EXECUTION_ENV}=1 outside production."
                )
            return LocalSubprocessBackend()

        raise InvalidBackendModeError(f"Unknown backend mode: {self.mode}")

    async def execute(
        self,
        authorization: ExecutionAuthorization,
        action: ActionRequest,
        *,
        profile: IsolationProfile | None = None,
    ) -> Any:
        """Admit and execute an authorized action inside the isolated execution plane."""
        active_profile = profile or self.default_profile

        request = IsolatedExecutionRequest(
            action_id=action.action_id,
            organization_id=action.agent.organization_id or "default",
            action_type=action.action_type,
            arguments=action.arguments,
            profile=active_profile,
        )

        outcome: ExecutionOutcome = await self.backend.execute(request)

        if not outcome.is_success:
            raise IsolationError(
                f"Isolated execution failed (exit_code={outcome.exit_code}): "
                f"{outcome.violation or outcome.stderr}"
            )

        return outcome.result_payload
