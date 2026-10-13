# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Privileged cloud operations — disabled unless grant verification succeeds."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from responsibleai.whitepact_cloud.grant_service import AdminGrantService, GrantExecutionError

T = TypeVar("T")

# Production wiring must explicitly enable after executor is bound to AdminGrantService.
PRIVILEGED_EXECUTOR_ENABLED = False


class PrivilegedOperationExecutor:
    """All provider/infrastructure actions must pass through grant verification."""

    def __init__(
        self,
        grant_service: AdminGrantService,
        *,
        enabled: bool = PRIVILEGED_EXECUTOR_ENABLED,
    ) -> None:
        self._grants = grant_service
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def execute(
        self,
        *,
        grant_id: str,
        signature: str,
        expected_operation: str,
        expected_provider: str,
        expected_resource: str,
        required_permission: str,
        operation: Callable[[dict[str, Any]], Awaitable[T]],
    ) -> T:
        if not self._enabled:
            raise GrantExecutionError("privileged_executor_disabled")

        verification = await self._grants.verify_for_execution(
            grant_id,
            signature,
            expected_operation=expected_operation,
            expected_provider=expected_provider,
            expected_resource=expected_resource,
            required_permission=required_permission,
        )
        if not verification.get("ok"):
            raise GrantExecutionError(verification.get("reason", "denied"))
        return await operation(verification)
