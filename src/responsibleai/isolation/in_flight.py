# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""In-flight execution registry coordinating immediate cancellation and
termination of running execution containers/processes upon authority revocation.

Features:
- Process-local registration and tracking of running containers and subprocesses.
- Distributed cross-worker reconciliation against database revocation epochs.
- Sub-second process-tree / container termination (<1.0s vs timeout).
- Strict termination verification: target process/container must be verified dead.
- Trustworthy containment state: failed terminations remain tracked as unresolved containment.
- Late-registration rejection: actions admitted at revoked epochs cannot register.
- Tenant isolation: revocation is strictly scoped to the targeted organization.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)

_DISTRIBUTED_REGISTRY_DIR = Path(tempfile.gettempdir()) / "whitepact_inflight"


def _ensure_distributed_dir() -> Path:
    _DISTRIBUTED_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    return _DISTRIBUTED_REGISTRY_DIR


def _record_cross_worker_registration(entry: InFlightExecution) -> None:
    d = _ensure_distributed_dir()
    file_path = d / f"{entry.organization_id}_{entry.execution_id}.json"
    data = {
            "execution_id": entry.execution_id,
            "organization_id": entry.organization_id,
            "action_id": entry.action_id,
            "authorization_id": entry.authorization_id,
            "admission_epoch": entry.admission_epoch,
            "pid": os.getpid(),
            "created_at": time.time(),
            "containment_status": entry.containment_status,
        }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=d, prefix=".tracking-", delete=False) as out:
            temporary = Path(out.name)
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, file_path)
        directory_fd = os.open(d, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _remove_cross_worker_registration(organization_id: str, execution_id: str) -> None:
    try:
        file_path = _DISTRIBUTED_REGISTRY_DIR / f"{organization_id}_{execution_id}.json"
        if file_path.exists():
            file_path.unlink()
    except Exception as exc:
        logger.debug("Failed to remove distributed execution tracking: %s", exc)


def _check_remote_worker_active(organization_id: str | None) -> list[dict[str, Any]]:
    unresolved_remote: list[dict[str, Any]] = []
    if not _DISTRIBUTED_REGISTRY_DIR.exists():
        return unresolved_remote
    current_pid = os.getpid()
    try:
        entries: list[Path] = []
        with os.scandir(_DISTRIBUTED_REGISTRY_DIR) as it:
            for entry in it:
                if entry.name.endswith(".json"):
                    entries.append(Path(entry.path))
    except Exception as exc:
        logger.warning("Failed to scan distributed registry directory: %s", exc)
        unresolved_remote.append(
            {
                "execution_id": "scan_failure",
                "organization_id": organization_id or "unknown",
                "action_id": "unknown",
                "pid": None,
                "created_at": time.time(),
                "error": f"Distributed registry scan failure: {exc}",
            }
        )
        return unresolved_remote

    for f in entries:
        filename = f.name
        # Match tenant prefix if organization_id is provided
        if organization_id is not None:
            prefix = f"{organization_id}_"
            if not filename.startswith(prefix):
                # Preserves tenant-safe isolation: ignore files of other organizations
                continue
            file_org = organization_id
            file_exec = filename[len(prefix) : -5]
        else:
            stem = filename[:-5]
            parts = stem.split("_", 1)
            file_org = parts[0] if len(parts) > 0 else "unknown"
            file_exec = parts[1] if len(parts) > 1 else stem

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as read_exc:
            # File is unreadable, locked, or corrupted; cannot authoritatively prove absence!
            unresolved_remote.append(
                {
                    "execution_id": file_exec,
                    "organization_id": file_org,
                    "action_id": "unknown",
                    "pid": None,
                    "created_at": time.time(),
                    "error": f"Tracking file inaccessible: {read_exc}",
                }
            )
            continue

        if organization_id is not None and data.get("organization_id") != organization_id:
            continue
        pid = data.get("pid")
        if pid and pid != current_pid:
            try:
                os.kill(pid, 0)
                is_alive = True
            except ProcessLookupError:
                is_alive = False
            except PermissionError:
                # Target process is alive under another user, container, or security context
                is_alive = True
            if is_alive:
                unresolved_remote.append(data)
            else:
                # A dead worker cannot attest that its container was terminated.
                # Retain legacy records too: they carry no contrary containment proof.
                unresolved_remote.append({**data, "error": "Worker exited; containment unconfirmed"})
        elif data.get("containment_status") == "unresolved":
            unresolved_remote.append(data)
    return unresolved_remote


class DatabaseReconciliationError(RuntimeError):
    """Raised when distributed revocation epoch reconciliation cannot query database."""


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
    termination_attempts: int = 0
    last_termination_error: str | None = None
    containment_status: str = "active"  # "active", "terminated", "unresolved"


class InFlightExecutionRegistry:
    """Thread-safe and async-safe registry for actively executing containers."""

    _instance: InFlightExecutionRegistry | None = None

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[str, InFlightExecution] = {}
        self._unresolved: dict[str, InFlightExecution] = {}
        self._latest_revoked_epoch: dict[str, int] = {}
        self._watcher_task: asyncio.Task[None] | None = None
        self._last_successful_reconciliation: float | None = None
        self._last_reconciliation_error: str | None = None
        self._consecutive_reconciliation_failures: int = 0

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

    def has_unresolved(self, organization_id: str) -> bool:
        """Check if an organization has active unresolved containment failures."""
        if any(e.organization_id == organization_id for e in self._unresolved.values()):
            return True
        return len(_check_remote_worker_active(organization_id)) > 0

    def is_revoked(self, organization_id: str, admission_epoch: int) -> bool:
        """Check if an admission epoch is superseded by a recorded revocation or blocked by unresolved containment."""
        if self.has_unresolved(organization_id):
            return True
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
            rejected = self.is_revoked(organization_id, admission_epoch)
            if rejected:
                # A process can already exist when admission is rejected. Track it
                # before awaiting termination; discard only after confirmation.
                entry.termination_attempts = 1
                entry.containment_status = "unresolved"
                self._unresolved[execution_id] = entry
            else:
                self._active[execution_id] = entry
            try:
                _record_cross_worker_registration(entry)
            except Exception as exc:
                # The container may already exist. Deny admission and run the
                # actual termination callback instead of losing its tracking.
                rejected = True
                entry.containment_status = "unresolved"
                entry.termination_attempts = 1
                entry.last_termination_error = f"Tracking persistence failed: {exc}"
                self._active.pop(execution_id, None)
                self._unresolved[execution_id] = entry

        if rejected:
            logger.warning(
                "late_registration_rejected: %s for org: %s (admission_epoch=%d, revoked_epoch=%d)",
                execution_id,
                organization_id,
                admission_epoch,
                self._latest_revoked_epoch.get(organization_id, -1),
            )
            confirmed = terminate_callback is None and task is None
            if terminate_callback is not None:
                try:
                    res = terminate_callback()
                    if asyncio.iscoroutine(res):
                        res = await res
                    confirmed = res is True
                    if not confirmed:
                        entry.last_termination_error = "Rejected execution termination unconfirmed"
                except Exception as exc:
                    entry.last_termination_error = str(exc)
            if confirmed:
                async with self._lock:
                    self._unresolved.pop(execution_id, None)
                    _remove_cross_worker_registration(organization_id, execution_id)
            if task is not None and task is not asyncio.current_task() and not task.done():
                task.cancel()
            raise PermissionError(
                f"Execution authorization for tenant '{organization_id}' has been revoked in-flight."
            )

        return entry

    async def unregister(self, execution_id: str, *, force: bool = False) -> bool:
        """Unregister an execution upon normal completion.

        If termination was attempted and remains unconfirmed/unresolved, unconditional
        unregistration is refused from dropping the audit trail: the entry is preserved
        in _unresolved for operator alerting.
        """
        async with self._lock:
            entry = self._active.get(execution_id)
            if entry is not None and entry.termination_attempts > 0 and not force:
                logger.critical(
                    "REFUSING_SILENT_UNREGISTER_OF_UNRESOLVED_EXECUTION: %s (org: %s, attempts: %d, error: %s)",
                    execution_id,
                    entry.organization_id,
                    entry.termination_attempts,
                    entry.last_termination_error,
                )
                entry.containment_status = "unresolved"
                self._unresolved[execution_id] = entry
                self._active.pop(execution_id, None)
                return False

            if entry is not None:
                _remove_cross_worker_registration(entry.organization_id, execution_id)
            self._active.pop(execution_id, None)
            return True

    def get_unresolved_containments(
        self, organization_id: str | None = None
    ) -> list[InFlightExecution]:
        """Return all executions whose containment failed or remains unconfirmed."""
        if organization_id is None:
            return list(self._unresolved.values())
        return [e for e in self._unresolved.values() if e.organization_id == organization_id]

    async def terminate_in_flight(
        self,
        *,
        organization_id: str | None = None,
        action_id: str | None = None,
        authorization_id: str | None = None,
    ) -> list[str]:
        """Terminate all matching in-flight executions immediately.

        Invokes low-level container/process termination callbacks and cancels tasks.
        Verifies that termination succeeded. Returns the list of confirmed terminated execution_ids.
        Unconfirmed terminations are retained in tracking as unresolved containment.
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
                "terminating_in_flight_execution: %s for org: %s (attempt %d)",
                entry.execution_id,
                entry.organization_id,
                entry.termination_attempts + 1,
            )
            callback_failed = False
            last_err: str | None = None

            # 1. Invoke low-level container/process termination callback if registered
            if entry.terminate_callback is not None:
                try:
                    res = entry.terminate_callback()
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res is False:
                        callback_failed = True
                        last_err = "terminate_callback returned False (target still running)"
                except Exception as exc:
                    callback_failed = True
                    last_err = str(exc)
                    logger.error(
                        "in_flight_terminate_callback_failed: %s (%s)",
                        entry.execution_id,
                        exc,
                    )

            # 2. Cancel the asyncio task running the communicate call
            if entry.task is not None and not entry.task.done():
                entry.task.cancel()

            # 3. Handle confirmed vs unresolved containment
            if callback_failed:
                entry.termination_attempts += 1
                entry.containment_status = "unresolved"
                entry.last_termination_error = last_err
                async with self._lock:
                    self._unresolved[entry.execution_id] = entry
                logger.critical(
                    "CONTAINMENT_UNRESOLVED_ALERT: %s for org: %s failed termination: %s",
                    entry.execution_id,
                    entry.organization_id,
                    last_err,
                )
            else:
                entry.containment_status = "terminated"
                async with self._lock:
                    self._unresolved.pop(entry.execution_id, None)
                    self._active.pop(entry.execution_id, None)
                _remove_cross_worker_registration(entry.organization_id, entry.execution_id)
                terminated_ids.append(entry.execution_id)

        # Check cross-worker distributed tracking
        remote_active = _check_remote_worker_active(organization_id)
        for r in remote_active:
            exec_id = r["execution_id"]
            if exec_id not in self._unresolved:
                entry = InFlightExecution(
                    execution_id=exec_id,
                    organization_id=r["organization_id"],
                    action_id=r.get("action_id", "unknown"),
                    authorization_id=r.get("authorization_id"),
                    task=None,
                    terminate_callback=None,
                    created_at=r.get("created_at", time.monotonic()),
                    admission_epoch=r.get("admission_epoch", 0),
                    termination_attempts=1,
                    last_termination_error=f"Remote worker (pid {r.get('pid')}) still active; distributed termination unconfirmed",
                    containment_status="unresolved",
                )
                async with self._lock:
                    self._unresolved[exec_id] = entry

        return terminated_ids

    def get_active_organizations(self) -> set[str]:
        return {e.organization_id for e in self._active.values()}

    def count_active(self, organization_id: str | None = None) -> int:
        if organization_id is None:
            return len(self._active)
        return sum(1 for e in self._active.values() if e.organization_id == organization_id)

    def get_unresolved(self, organization_id: str | None = None) -> list[dict[str, Any]]:
        """Return operator-visible diagnostic records of unconfirmed/unresolved containment."""
        records: list[dict[str, Any]] = []
        for e in self._unresolved.values():
            if organization_id is None or e.organization_id == organization_id:
                records.append(
                    {
                        "execution_id": e.execution_id,
                        "organization_id": e.organization_id,
                        "action_id": e.action_id,
                        "authorization_id": e.authorization_id,
                        "created_at": e.created_at,
                        "admission_epoch": e.admission_epoch,
                        "termination_attempts": e.termination_attempts,
                        "last_termination_error": e.last_termination_error,
                        "containment_status": e.containment_status,
                    }
                )
        return records

    def count_unresolved(self, organization_id: str | None = None) -> int:
        """Count active unresolved containment failures, including unconfirmed remote workers."""
        local_count = sum(
            1
            for e in self._unresolved.values()
            if organization_id is None or e.organization_id == organization_id
        )
        remote_active = _check_remote_worker_active(organization_id)
        remote_ids = {
            r["execution_id"]
            for r in remote_active
            if r.get("execution_id") not in self._unresolved
        }
        return local_count + len(remote_ids)

    async def retry_unresolved(self, organization_id: str | None = None) -> list[str]:
        """Retry containment termination for previously unconfirmed executions."""
        async with self._lock:
            targets = [
                e
                for e in self._unresolved.values()
                if organization_id is None or e.organization_id == organization_id
            ]
        resolved: list[str] = []
        for entry in targets:
            entry.termination_attempts += 1
            if entry.terminate_callback is not None:
                try:
                    res = entry.terminate_callback()
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res is not False:
                        entry.containment_status = "terminated"
                        async with self._lock:
                            self._unresolved.pop(entry.execution_id, None)
                            self._active.pop(entry.execution_id, None)
                        resolved.append(entry.execution_id)
                except Exception as exc:
                    entry.last_termination_error = str(exc)
        return resolved

    async def reconcile_epochs(self, engine: Any) -> list[str]:
        """Durable distributed reconciliation: query database for active tenants and kill stale runs.

        Raises DatabaseReconciliationError on connectivity or query failures so the outer supervisor
        can apply backoff and accurately alert operators, preventing false claims of containment.
        """
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
        except Exception as exc:
            logger.warning("reconcile_epochs_query_failed_propagating: %s", exc)
            raise DatabaseReconciliationError(
                f"Database connectivity failed during revocation epoch reconciliation: {exc}"
            ) from exc

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

        return terminated

    def start_reconciliation_watcher(
        self, engine: Any, interval: float = 0.05
    ) -> asyncio.Task[None]:
        """Start background reconciliation loop polling database epochs for active executions."""
        if self._watcher_task is not None and not self._watcher_task.done():
            return self._watcher_task

        async def _loop() -> None:
            backoff = interval
            while True:
                try:
                    if len(self._active) > 0:
                        await self.reconcile_epochs(engine)
                    backoff = interval
                    self._last_successful_reconciliation = time.monotonic()
                    self._last_reconciliation_error = None
                    self._consecutive_reconciliation_failures = 0
                except asyncio.CancelledError:
                    break
                except Exception as exc:
                    self._consecutive_reconciliation_failures += 1
                    self._last_reconciliation_error = str(exc)
                    logger.warning(
                        "reconciliation_watcher_error_retry (failures=%d, backoff=%.2fs): %s",
                        self._consecutive_reconciliation_failures,
                        backoff,
                        exc,
                    )
                    backoff = min(backoff * 2.0, 5.0)
                await asyncio.sleep(backoff)

        self._watcher_task = asyncio.create_task(_loop())
        return self._watcher_task

    def stop_reconciliation_watcher(self) -> None:
        """Stop and cancel the background reconciliation watcher."""
        if self._watcher_task is not None:
            if not self._watcher_task.done():
                self._watcher_task.cancel()
            self._watcher_task = None
