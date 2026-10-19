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
import hashlib
import json
import logging
import os
import shutil
import stat
import struct
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)

_DISTRIBUTED_REGISTRY_DIR = Path(tempfile.gettempdir()) / "whitepact_inflight"
_LOCK_CLOCK = time.monotonic


def _ensure_distributed_dir() -> Path:
    _DISTRIBUTED_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    info = _DISTRIBUTED_REGISTRY_DIR.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise PermissionError(
            "Tracking directory must be an owned, non-writable-by-others directory"
        )
    return _DISTRIBUTED_REGISTRY_DIR


def _identity_digest(domain: bytes, value: str) -> str:
    # Database identifiers are exact strings; NFC is not a database identity rule.
    raw = value.encode("utf-8")
    return hashlib.sha256(domain + struct.pack(">Q", len(raw)) + raw).hexdigest()


@contextmanager
def _registry_ownership(directory: Path) -> Iterator[None]:
    """Serialize publication and compare/unlink across cooperating POSIX workers."""
    import fcntl

    descriptor = os.open(
        directory / ".registry.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o022
            or info.st_nlink != 1
        ):
            raise PermissionError("Untrusted registry ownership lock")
        deadline = _LOCK_CLOCK() + 1.0
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if _LOCK_CLOCK() >= deadline:
                    raise TimeoutError("Registry ownership lock unavailable") from None
                time.sleep(0.01)
        yield
    finally:
        os.close(descriptor)


def _tracking_filename(organization_id: str, execution_id: str) -> str:
    tenant = _identity_digest(b"WP-INFLIGHT-V2-TENANT\x00", organization_id)
    execution = _identity_digest(b"WP-INFLIGHT-V2-EXEC\x00", execution_id)
    return f"trk_v2_{tenant}_{execution}.json"


def _record_cross_worker_registration(entry: InFlightExecution) -> None:
    d = _ensure_distributed_dir()
    file_path = d / _tracking_filename(entry.organization_id, entry.execution_id)
    data = {
        "execution_id": entry.execution_id,
        "organization_id": entry.organization_id,
        "action_id": entry.action_id,
        "authorization_id": entry.authorization_id,
        "admission_epoch": entry.admission_epoch,
        "pid": os.getpid(),
        "created_at": time.time(),
        "containment_status": entry.containment_status,
        "registration_id": entry.registration_id,
        "container_name": entry.container_name,
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=d, prefix=".tracking-", delete=False) as out:
            temporary = Path(out.name)
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        # Atomic no-replace publication. Existing, corrupt, colliding and symlink
        # records all retain ownership; no check-then-replace overwrite window.
        with _registry_ownership(d):
            os.link(temporary, file_path)
            directory_fd = os.open(d, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _remove_cross_worker_registration(
    organization_id: str, execution_id: str, *, registration_id: str | None = None
) -> None:
    try:
        directory = _ensure_distributed_dir()
        # Inspect actual directory entries, never construct a path from raw IDs.
        with _registry_ownership(directory):
            for file_path in directory.glob("*.json"):
                if file_path.is_symlink():
                    continue
                try:
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and (
                    data.get("organization_id") == organization_id
                    and data.get("execution_id") == execution_id
                ):
                    if (
                        registration_id is not None
                        and data.get("registration_id") != registration_id
                    ):
                        continue
                    file_path.unlink()
    except Exception as exc:
        logger.debug("Failed to remove distributed execution tracking: %s", exc)


def _check_remote_worker_active(
    organization_id: str | None, *, local_execution_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    unresolved_remote: list[dict[str, Any]] = []
    if not _DISTRIBUTED_REGISTRY_DIR.exists():
        return unresolved_remote
    current_pid = os.getpid()
    try:
        _ensure_distributed_dir()
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
        file_exec = filename[:-5]

        try:
            if f.is_symlink():
                raise ValueError("Symbolic link tracking is not authoritative")
            data = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("organization_id"), str):
                raise ValueError("Missing tracking identity")
            if not isinstance(data.get("execution_id"), str):
                raise ValueError("Missing execution identity")
            if filename.startswith("trk_v2_") and filename != _tracking_filename(
                data["organization_id"], data["execution_id"]
            ):
                raise ValueError("Tracking digest and payload identity mismatch")
            if organization_id is not None and data["organization_id"] != organization_id:
                continue
            if not isinstance(data.get("pid"), int) or data["pid"] <= 0:
                raise ValueError("Missing worker identity")
            if data.get("containment_status", "active") not in {"active", "unresolved"}:
                raise ValueError("Unconfirmed containment state")
        except Exception as read_exc:
            # File is unreadable, locked, or corrupted; cannot authoritatively prove absence!
            unreadable_org = "unknown"
            if filename.startswith("trk_v2_"):
                if organization_id is not None and organization_id != "unknown":
                    expected_hash = _identity_digest(b"WP-INFLIGHT-V2-TENANT\x00", organization_id)
                    if filename.startswith(f"trk_v2_{expected_hash}_"):
                        unreadable_org = organization_id
            elif organization_id is not None and filename.startswith(f"{organization_id}_"):
                unreadable_org = organization_id
            elif "_" in filename and not filename.startswith("corrupted"):
                cand_org, cand_exec = filename[:-5].split("_", 1)
                unreadable_org = cand_org
                file_exec = cand_exec

            if organization_id is not None and organization_id != "unknown":
                if unreadable_org != organization_id:
                    continue
            if organization_id == "unknown" and unreadable_org != "unknown":
                continue

            unresolved_remote.append(
                {
                    "execution_id": file_exec,
                    "organization_id": unreadable_org if organization_id is None else organization_id,
                    "action_id": "unknown",
                    "pid": None,
                    "created_at": time.time(),
                    "error": f"Tracking file inaccessible: {read_exc}",
                    "containment_status": "unresolved",
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
                unresolved_remote.append(
                    {**data, "error": "Worker exited; containment unconfirmed"}
                )
        elif data.get("containment_status") == "unresolved":
            unresolved_remote.append(data)
        elif data["execution_id"] not in (local_execution_ids or set()):
            unresolved_remote.append({**data, "error": "Local runtime ownership unconfirmed"})
    return unresolved_remote


async def verify_authoritative_container_containment(
    container_name: str,
    *,
    docker_cmd: str | None = None,
    timeout_seconds: float = 5.0,
) -> bool:
    """Authoritatively inspect and verify that a container is terminated or absent via Docker.

    Returns True ONLY if Docker authoritatively confirms the container is absent
    ('no such container' / 'no such object') or stopped/dead ('exited' / 'dead' and not running).
    Returns False if the container is still running, or if Docker is unreachable /
    inspect fails, failing closed.
    """
    cmd = docker_cmd or shutil.which("docker") or "docker"
    if not shutil.which(cmd) and not os.path.exists(cmd):
        return False

    loop = asyncio.get_running_loop()

    def _sync_inspect_and_terminate() -> bool:
        # First attempt termination
        try:
            rm_res = subprocess.run(
                [cmd, "rm", "-f", container_name],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            rm_err = rm_res.stderr.lower()
            if (
                "no such container" in rm_err or "no such object" in rm_err
            ) and "plugin" not in rm_err and "daemon unavailable" not in rm_err:
                return True
        except Exception:
            pass

        # Inspect state authoritatively
        try:
            inspect_res = subprocess.run(
                [cmd, "inspect", "-f", "{{.State.Status}} {{.State.Running}}", container_name],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if inspect_res.returncode == 0:
                raw_out = inspect_res.stdout.strip()
                if raw_out.startswith(("[", "{")):
                    try:
                        data = json.loads(raw_out)
                        if isinstance(data, list) and data:
                            data = data[0]
                        st = data.get("State", {})
                        if st.get("Running") is False:
                            return True
                    except Exception:
                        pass
                parts = raw_out.lower().split()
                status = parts[0] if parts else ""
                is_running = parts[1] if len(parts) > 1 else ""
                if is_running == "false" and status in {"exited", "dead"}:
                    return True
                return False
            insp_err = inspect_res.stderr.lower()
            if (
                "no such container" in insp_err or "no such object" in insp_err
            ) and "plugin" not in insp_err and "daemon unavailable" not in insp_err:
                return True
            return False
        except Exception:
            return False

    try:
        return await loop.run_in_executor(None, _sync_inspect_and_terminate)
    except Exception:
        return False


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
    registration_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    container_name: str | None = None


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
        local = {
            e.execution_id for e in self._active.values() if e.organization_id == organization_id
        }
        return len(_check_remote_worker_active(organization_id, local_execution_ids=local)) > 0

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
        container_name: str | None = None,
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
            container_name=container_name,
        )
        async with self._lock:
            tracking_owned = False
            duplicate = execution_id in self._active or execution_id in self._unresolved
            if duplicate:
                # Retain the original callback and authority. Track the rejected
                # attempt separately until its own termination is established.
                execution_id = f"{execution_id}:rejected:{uuid.uuid4().hex}"
                entry.execution_id = execution_id
            rejected = duplicate or self.is_revoked(organization_id, admission_epoch)
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
                tracking_owned = True
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
                    if tracking_owned:
                        _remove_cross_worker_registration(
                            organization_id, execution_id, registration_id=entry.registration_id
                        )
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
                _remove_cross_worker_registration(
                    entry.organization_id, execution_id, registration_id=entry.registration_id
                )
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
                    if res is not True:
                        callback_failed = True
                        last_err = "terminate_callback did not confirm target termination"
                except Exception as exc:
                    callback_failed = True
                    last_err = str(exc)
                    logger.error(
                        "in_flight_terminate_callback_failed: %s (%s)",
                        entry.execution_id,
                        exc,
                    )
            elif entry.container_name:
                try:
                    is_contained = await verify_authoritative_container_containment(entry.container_name)
                    if not is_contained:
                        callback_failed = True
                        last_err = f"Container {entry.container_name} is alive or could not be verified terminated"
                except Exception as exc:
                    callback_failed = True
                    last_err = f"Container containment check failed: {exc}"
            elif entry.task is not None:
                callback_failed = True
                last_err = "No termination callback for active task"

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
                    self._active.pop(entry.execution_id, None)
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
                _remove_cross_worker_registration(
                    entry.organization_id, entry.execution_id, registration_id=entry.registration_id
                )
                terminated_ids.append(entry.execution_id)

        # Check cross-worker distributed tracking
        remote_active = _check_remote_worker_active(
            organization_id, local_execution_ids={e.execution_id for e in self._active.values()}
        )
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
                    last_termination_error=r.get("error")
                    or f"Remote worker (pid {r.get('pid')}) still active; distributed termination unconfirmed",
                    containment_status="unresolved",
                    container_name=r.get("container_name"),
                )
                async with self._lock:
                    self._unresolved[exec_id] = entry

        # Attempt authoritative container verification and termination for unresolved records
        resolved_retry = await self.retry_unresolved(organization_id=organization_id)
        terminated_ids.extend([eid for eid in resolved_retry if eid not in terminated_ids])

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
        remote_active = _check_remote_worker_active(
            organization_id, local_execution_ids={e.execution_id for e in self._active.values()}
        )
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
            confirmed = False
            if entry.terminate_callback is not None:
                try:
                    res = entry.terminate_callback()
                    if asyncio.iscoroutine(res):
                        res = await res
                    if res is True:
                        confirmed = True
                    else:
                        entry.last_termination_error = (
                            "terminate_callback did not confirm target termination"
                        )
                except Exception as exc:
                    entry.last_termination_error = str(exc)
            elif entry.container_name:
                cname = entry.container_name
                try:
                    if await verify_authoritative_container_containment(cname):
                        confirmed = True
                    else:
                        entry.last_termination_error = (
                            f"Container {cname} containment unconfirmed; target may still be active"
                        )
                except Exception as exc:
                    entry.last_termination_error = (
                        f"Container {cname} inspect verification failed: {exc}"
                    )
            else:
                entry.last_termination_error = (
                    "No termination callback, task, or authoritative container identifier available"
                )

            if confirmed:
                entry.containment_status = "terminated"
                async with self._lock:
                    self._unresolved.pop(entry.execution_id, None)
                    self._active.pop(entry.execution_id, None)
                _remove_cross_worker_registration(
                    entry.organization_id,
                    entry.execution_id,
                    registration_id=entry.registration_id,
                )
                resolved.append(entry.execution_id)
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
                    epochs.c.organization_id.in_(list(active_orgs)),
                    epochs.c.scope == "governance",
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
