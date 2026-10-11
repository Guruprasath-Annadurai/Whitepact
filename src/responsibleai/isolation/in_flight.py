# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""In-flight execution registry coordinating immediate cancellation and
termination of running execution containers/processes upon authority revocation.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InFlightExecution:
    execution_id: str
    organization_id: str
    action_id: str
    authorization_id: str | None
    task: asyncio.Task[Any] | None
    terminate_callback: Callable[[], Any] | None
    created_at: float


class InFlightExecutionRegistry:
    """Thread-safe and async-safe registry for actively executing containers."""

    _instance: InFlightExecutionRegistry | None = None

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[str, InFlightExecution] = {}

    @classmethod
    def get_instance(cls) -> InFlightExecutionRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Testing utility to reset registry state."""
        cls._instance = None

    async def register(
        self,
        execution_id: str,
        organization_id: str,
        action_id: str,
        authorization_id: str | None = None,
        task: asyncio.Task[Any] | None = None,
        terminate_callback: Callable[[], Any] | None = None,
    ) -> InFlightExecution:
        entry = InFlightExecution(
            execution_id=execution_id,
            organization_id=organization_id,
            action_id=action_id,
            authorization_id=authorization_id,
            task=task,
            terminate_callback=terminate_callback,
            created_at=time.monotonic(),
        )
        async with self._lock:
            self._active[execution_id] = entry
        return entry

    async def unregister(self, execution_id: str) -> None:
        async with self._lock:
            self._active.pop(execution_id, None)

    async def terminate_in_flight(
        self,
        *,
        organization_id: str | None = None,
        action_id: str | None = None,
        authorization_id: str | None = None,
    ) -> list[str]:
        """Terminate all matching in-flight executions immediately.

        Invokes low-level container/process termination callbacks and cancels tasks.
        Returns the list of terminated execution_ids.
        """
        async with self._lock:
            to_terminate = [
                entry
                for entry in self._active.values()
                if (organization_id is None or entry.organization_id == organization_id)
                and (action_id is None or entry.action_id == action_id)
                and (authorization_id is None or entry.authorization_id == authorization_id)
            ]

        terminated_ids: list[str] = []
        for entry in to_terminate:
            logger.warning(
                "terminating_in_flight_execution: %s for org: %s",
                entry.execution_id,
                entry.organization_id,
            )
            # 1. Invoke low-level container/process termination callback if registered
            if entry.terminate_callback is not None:
                try:
                    res = entry.terminate_callback()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as exc:
                    logger.error(
                        "in_flight_terminate_callback_failed: %s (%s)",
                        entry.execution_id,
                        exc,
                    )

            # 2. Cancel the asyncio task running the communicate call
            if entry.task is not None and not entry.task.done():
                entry.task.cancel()

            terminated_ids.append(entry.execution_id)

        return terminated_ids

    def count_active(self, organization_id: str | None = None) -> int:
        if organization_id is None:
            return len(self._active)
        return sum(1 for e in self._active.values() if e.organization_id == organization_id)
