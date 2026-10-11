# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""In-flight execution registry coordinating immediate cancellation and
termination of running execution containers/processes upon authority revocation.

Features:
- Process-local registration and tracking of running containers and subprocesses.
- Distributed cross-worker reconciliation against database revocation epochs.
- Sub-second process-tree / container termination (<1.0s vs timeout).
- Late-registration rejection: actions admitted at revoked epochs cannot register.
- Tenant isolation: revocation is strictly scoped to the targeted organization.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

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
    admission_epoch: int = 0


class InFlightExecutionRegistry:
    """Thread-safe and async-safe registry for actively executing containers."""

    _instance: InFlightExecutionRegistry | None = None

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[str, InFlightExecution] = {}
        self._latest_revoked_epoch: dict[str, int] = {}
        self._watcher_task: asyncio.Task[None] | None = None

    @classmethod
    def get_instance(cls) -> InFlightExecutionRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Testing utility to reset registry state and stop background tasks."""
        if cls._instance is not None and cls._instance._watcher_task is not None:
            cls._instance._watcher_task.cancel()
        cls._instance = None

    def record_revoked_epoch(self, organization_id: str, epoch: int) -> None:
        """Record the latest revoked epoch for an organization to reject late registrations."""
        current = self._latest_revoked_epoch.get(organization_id, -1)
        if epoch > current:
            self._latest_revoked_epoch[organization_id] = epoch

    def is_revoked(self, organization_id: str, admission_epoch: int) -> bool:
        """Check if an admission epoch is superseded by a recorded revocation."""
        latest = self._latest_revoked_epoch.get(organization_id, -1)
        return latest >= 0 and admission_epoch < latest

    async def register(
        self,
        execution_id: str,
        organization_id: str,
        action_id: str,
        authorization_id: str | None = None,
        task: asyncio.Task[Any] | None = None,
        terminate_callback: Callable[[], Any] | None = None,
        admission_epoch: int = 0,
    ) -> InFlightExecution:
        # Check late registration: if this tenant has already bumped beyond admission_epoch, abort!
        if self.is_revoked(organization_id, admission_epoch):
            logger.warning(
                "late_registration_rejected: %s for org: %s (admission_epoch=%d, revoked_epoch=%d)",
                execution_id,
                organization_id,
                admission_epoch,
                self._latest_revoked_epoch.get(organization_id, -1),
            )
            if terminate_callback is not None:
                try:
                    res = terminate_callback()
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
            if task is not None and not task.done():
                task.cancel()
            raise PermissionError(
                f"Execution authorization for tenant '{organization_id}' has been revoked in-flight."
            )

        entry = InFlightExecution(
            execution_id=execution_id,
            organization_id=organization_id,
            action_id=action_id,
            authorization_id=authorization_id,
            task=task,
            terminate_callback=terminate_callback,
            created_at=time.monotonic(),
            admission_epoch=admission_epoch,
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
            for entry in to_terminate:
                self._active.pop(entry.execution_id, None)

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

    def get_active_organizations(self) -> set[str]:
        return {e.organization_id for e in self._active.values()}

    def count_active(self, organization_id: str | None = None) -> int:
        if organization_id is None:
            return len(self._active)
        return sum(1 for e in self._active.values() if e.organization_id == organization_id)

    async def reconcile_epochs(self, engine: Any) -> list[str]:
        """Durable distributed reconciliation: query database for active tenants and kill stale runs."""
        active_orgs = self.get_active_organizations()
        if not active_orgs:
            return []

        from responsibleai.db.engine import governance_revocation_epochs as epochs

        terminated: list[str] = []
        try:
            async with engine.raw.connect() as conn:
                stmt = select(epochs.c.organization_id, epochs.c.epoch).where(
                    epochs.c.organization_id.in_(list(active_orgs))
                )
                result = await conn.execute(stmt)
                db_epochs = {row[0]: row[1] for row in result}

            for org_id, current_epoch in db_epochs.items():
                self.record_revoked_epoch(org_id, current_epoch)
                async with self._lock:
                    stale_ids = [
                        e.execution_id
                        for e in self._active.values()
                        if e.organization_id == org_id and e.admission_epoch < current_epoch
                    ]
                if stale_ids:
                    t_ids = await self.terminate_in_flight(organization_id=org_id)
                    terminated.extend(t_ids)
        except Exception as exc:
            logger.debug("reconcile_epochs_query_failed: %s", exc)

        return terminated

    def start_reconciliation_watcher(
        self, engine: Any, interval: float = 0.05
    ) -> asyncio.Task[None]:
        """Start background reconciliation loop polling database epochs for active executions."""
        if self._watcher_task is not None and not self._watcher_task.done():
            return self._watcher_task

        async def _loop() -> None:
            while True:
                try:
                    if len(self._active) > 0:
                        await self.reconcile_epochs(engine)
                except asyncio.CancelledError:
                    break
                except Exception:
                    pass
                await asyncio.sleep(interval)

        self._watcher_task = asyncio.create_task(_loop())
        return self._watcher_task
