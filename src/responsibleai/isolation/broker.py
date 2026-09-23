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
        is_prod = os.environ.get("ENVIRONMENT", "").lower() == "production"

        if self.mode == BackendMode.LOCAL_DEV:
            if is_prod:
                raise InvalidBackendModeError(
                    "LOCAL_DEV isolation backend mode is strictly forbidden in production. "
                    "Fail-closed invariant triggered."
                )
            return LocalSubprocessBackend()

        if self.mode == BackendMode.DOCKER:
            docker_be = DockerContainerBackend()
            if not docker_be.is_available():
                # Fail closed if production or explicitly configured
                if is_prod or os.environ.get("WHITEPACT_ISOLATION_BACKEND") == "docker":
                    raise IsolationBackendUnavailableError(
                        "Docker container isolation backend is required but unavailable. "
                        "Failing closed."
                    )
                # In non-production tests/local dev where docker isn't running, fallback only if allowed
                return LocalSubprocessBackend()
            return docker_be

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
