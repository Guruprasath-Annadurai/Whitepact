# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Backup Resurrection Defense and Restore Reconciliation Engine for WhitePact Phase 5.

Guarantees:
- Persistent Tombstone Ledger tracking all deleted organizations and generation IDs.
- CurrentLifecycleStateProvider outside application database restore domain.
- Forward deletion state recorded prior to destructive purge.
- Restore Readiness Gate (RESTORE_PENDING -> RECONCILING -> READY / FAILED).
- Restore Quarantine Guard: Automatically detects and quarantines resurrected organizations post-restore.
- Immediate Revocation: Purges restored sessions, API keys, and credentials of deleted tenants.
- Fail-Closed: Blocks operational traffic if restore reconciliation fails or detects unresolved state.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import stat
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    eval_baselines,
    eval_runs,
    governance_approval_votes,
    governance_approvals,
    governance_consent_proofs,
    governance_delegations,
    governance_execution_authorizations,
    governance_execution_nonces,
    governance_policies,
    governance_policy_activations,
    governance_policy_history,
    governance_policy_revisions,
    governance_policy_versions,
    governance_revocation_epochs,
    governance_root_authority_records,
    iam_api_key_lineage,
    iam_scim_groups,
    iam_scim_users,
    iam_sessions,
    mcp_tool_calls,
    org_api_key_metadata,
    org_api_keys,
    organizations,
    restore_reconciliation_records,
    runtime_execution_attempts,
    runtime_execution_dispatch_outbox,
    runtime_execution_fences,
    runtime_execution_requests,
    runtime_worker_leases,
    tenant_tombstones,
    token_usage,
    web_memberships,
    web_sessions,
)
from responsibleai.rbac.models import GovernanceStatus


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RestoreReconciliationError(Exception):
    """Raised when restore reconciliation fails."""


class RestoreQuarantineError(Exception):
    """Raised when operational traffic is attempted while system is quarantined/not ready."""


class MissingLifecycleProviderError(RestoreReconciliationError):
    """Raised when durable Store B provider is missing in production."""


class LifecycleRollbackError(ValueError):
    """Raised when an illegal backward state or epoch transition is attempted."""


class LifecycleIntegrityError(RestoreReconciliationError):
    """Raised when a lifecycle record fails cryptographic integrity verification."""


class StoreBUnavailableError(RestoreReconciliationError):
    """Raised when the Store B provider or database connection is unavailable."""


class LifecycleState(StrEnum):
    """Security lifecycle state of a tenant."""

    ACTIVE = "ACTIVE"
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"
    TOMBSTONED = "TOMBSTONED"


_STATE_RANK: dict[LifecycleState, int] = {
    LifecycleState.ACTIVE: 1,
    LifecycleState.DELETION_IN_PROGRESS: 2,
    LifecycleState.TOMBSTONED: 3,
}


def compute_lifecycle_digest(
    tenant_id: str,
    generation_id: str,
    state: str,
    effective_at: str,
    security_epoch: int = 1,
    revocation_floor: int = 1,
    erasure_request_ref: str = "",
    secret_key: str = "",
) -> str:
    payload = f"{tenant_id}:{generation_id}:{state}:{effective_at}:{security_epoch}:{revocation_floor}:{erasure_request_ref}"
    if secret_key:
        return hmac.new(
            secret_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_production_environment() -> bool:
    from responsibleai.environment import is_production

    return is_production()


class RestoreReadinessState(StrEnum):
    """Operational readiness states for restored environment admission."""

    RESTORE_PENDING = "RESTORE_PENDING"
    RECONCILING = "RECONCILING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class LifecycleStateRecord:
    tenant_id: str
    generation_id: str
    state: LifecycleState
    effective_at: str
    security_epoch: int = 1
    revocation_floor: int = 1
    erasure_request_ref: str = ""
    digest: str = ""


class CurrentLifecycleStateProvider(ABC):
    """Independent control-plane store providing current lifecycle state outside application restore domain."""

    @abstractmethod
    def record_state(self, record: LifecycleStateRecord) -> None:
        """Record or update tenant lifecycle state forward."""

    @abstractmethod
    def get_state(self, tenant_id: str) -> LifecycleStateRecord | None:
        """Retrieve current lifecycle state for tenant."""

    @abstractmethod
    def is_tombstoned(self, tenant_id: str) -> bool:
        """Check if tenant is tombstoned."""

    @abstractmethod
    def is_deletion_in_progress(self, tenant_id: str) -> bool:
        """Check if tenant deletion is currently in progress."""

    @abstractmethod
    def list_tombstones(self) -> list[LifecycleStateRecord]:
        """List all tombstones in the current lifecycle state store."""

    @abstractmethod
    def list_all(self) -> list[LifecycleStateRecord]:
        """List all lifecycle records in the current lifecycle state store."""

    @abstractmethod
    def verify_integrity(self) -> bool:
        """Verify integrity and availability of current lifecycle store."""

    @abstractmethod
    def set_available(self, available: bool) -> None:
        """Configure availability for failure simulation testing."""

    @abstractmethod
    def set_corrupted(self, corrupted: bool) -> None:
        """Configure corruption for integrity failure testing."""

    @abstractmethod
    def get_readiness_state(self) -> RestoreReadinessState | None:
        """Get authoritative shared readiness state."""

    @abstractmethod
    def set_readiness_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        """Set authoritative shared readiness state."""


_FORBIDDEN_STORE_B_FILENAMES = frozenset(
    {
        "whitepact_store_b_lifecycle.db",
    }
)


def resolve_store_b_path(db_path: str | Path | None = None) -> Path:
    """Resolve Store B path. Never silently fall back to a shared /tmp file."""
    raw: str | Path | None = db_path
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        env = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
            "WHITEPACT_LIFECYCLE_STORE_PATH"
        )
        raw = env.strip() if env else None
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        raise MissingLifecycleProviderError(
            "Durable Store-B path is required. Set WHITEPACT_STORE_B_PATH to an "
            "operator-owned location. There is no shared /tmp fallback."
        )
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if path.name in _FORBIDDEN_STORE_B_FILENAMES:
        raise MissingLifecycleProviderError(
            "Refusing the well-known shared Store-B filename. Choose an "
            "unpredictable operator-owned path."
        )
    return path


def _secure_create_store_b_file(path: Path) -> None:
    """Create the SQLite file without following symlinks; mode 0600."""
    if path.exists() and path.is_symlink():
        raise MissingLifecycleProviderError("Store B path must not be a symlink")
    parent = path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise MissingLifecycleProviderError(f"Cannot open Store B path: {exc}") from exc
    try:
        os.fchmod(fd, 0o600)
        st = os.fstat(fd)
        if stat.S_ISLNK(st.st_mode):
            raise MissingLifecycleProviderError("Store B path must not be a symlink")
    finally:
        os.close(fd)


class SqliteDurableLifecycleStateProvider(CurrentLifecycleStateProvider):
    """Production-grade durable lifecycle state provider backed by an independent database outside Store A."""

    def __init__(self, db_path: str | Path | None = None, secret_key: str = "") -> None:
        self._path = resolve_store_b_path(db_path)
        self._secret_key = secret_key or os.environ.get("WHITEPACT_STORE_B_KEY", "")
        self._available: bool = True
        self._corrupted: bool = False
        self._init_db()

    @property
    def path(self) -> Path:
        return self._path

    def _get_connection(self) -> sqlite3.Connection:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        conn = sqlite3.connect(str(self._path), timeout=10.0, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        return conn

    def _init_db(self) -> None:
        _secure_create_store_b_file(self._path)
        conn = self._get_connection()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS durable_tenant_lifecycle_states (
                        tenant_id TEXT PRIMARY KEY,
                        generation_id TEXT NOT NULL,
                        state TEXT NOT NULL,
                        effective_at TEXT NOT NULL,
                        security_epoch INTEGER NOT NULL DEFAULT 1,
                        revocation_floor INTEGER NOT NULL DEFAULT 1,
                        erasure_request_ref TEXT NOT NULL DEFAULT '',
                        digest TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS durable_restore_readiness (
                        key TEXT PRIMARY KEY,
                        state TEXT NOT NULL,
                        epoch INTEGER NOT NULL DEFAULT 1,
                        updated_at TEXT NOT NULL,
                        updated_by TEXT NOT NULL DEFAULT ''
                    )
                """)
        finally:
            conn.close()

    def record_state(self, record: LifecycleStateRecord) -> None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")

        expected_digest = compute_lifecycle_digest(
            tenant_id=record.tenant_id,
            generation_id=record.generation_id,
            state=record.state.value,
            effective_at=record.effective_at,
            security_epoch=record.security_epoch,
            revocation_floor=record.revocation_floor,
            erasure_request_ref=record.erasure_request_ref,
            secret_key=self._secret_key,
        )
        if record.digest and record.digest != expected_digest:
            raise LifecycleIntegrityError("Tampered lifecycle state record digest")

        digest_to_store = record.digest or expected_digest
        now = datetime.now(UTC).isoformat()

        conn = self._get_connection()
        try:
            with conn:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    "SELECT state, security_epoch, effective_at, generation_id FROM durable_tenant_lifecycle_states WHERE tenant_id = ?",
                    (record.tenant_id,),
                )
                row = cursor.fetchone()
                if row:
                    curr_state_str, curr_epoch, curr_eff, curr_gen = row
                    curr_rank = _STATE_RANK.get(LifecycleState(curr_state_str), 0)
                    new_rank = _STATE_RANK.get(record.state, 0)
                    if new_rank < curr_rank:
                        raise LifecycleRollbackError(
                            f"Lifecycle state rollback rejected: cannot transition from {curr_state_str} to {record.state.value}"
                        )
                    if record.security_epoch < curr_epoch:
                        raise LifecycleRollbackError(
                            f"Security epoch rollback rejected: {record.security_epoch} < {curr_epoch}"
                        )
                    if (
                        new_rank == curr_rank
                        and record.security_epoch == curr_epoch
                        and record.effective_at <= curr_eff
                        and record.generation_id == curr_gen
                    ):
                        return

                conn.execute(
                    """
                    INSERT INTO durable_tenant_lifecycle_states (
                        tenant_id, generation_id, state, effective_at, security_epoch, revocation_floor, erasure_request_ref, digest, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id) DO UPDATE SET
                        generation_id = excluded.generation_id,
                        state = excluded.state,
                        effective_at = excluded.effective_at,
                        security_epoch = excluded.security_epoch,
                        revocation_floor = excluded.revocation_floor,
                        erasure_request_ref = excluded.erasure_request_ref,
                        digest = excluded.digest,
                        updated_at = excluded.updated_at
                    """,
                    (
                        record.tenant_id,
                        record.generation_id,
                        record.state.value,
                        record.effective_at,
                        record.security_epoch,
                        record.revocation_floor,
                        record.erasure_request_ref,
                        digest_to_store,
                        now,
                    ),
                )
        finally:
            conn.close()

    def get_state(self, tenant_id: str) -> LifecycleStateRecord | None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT tenant_id, generation_id, state, effective_at, security_epoch, revocation_floor, erasure_request_ref, digest FROM durable_tenant_lifecycle_states WHERE tenant_id = ?",
                (tenant_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return LifecycleStateRecord(
                tenant_id=row[0],
                generation_id=row[1],
                state=LifecycleState(row[2]),
                effective_at=row[3],
                security_epoch=row[4],
                revocation_floor=row[5],
                erasure_request_ref=row[6],
                digest=row[7],
            )
        finally:
            conn.close()

    def is_tombstoned(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state == LifecycleState.TOMBSTONED

    def is_deletion_in_progress(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state in (
            LifecycleState.DELETION_IN_PROGRESS,
            LifecycleState.TOMBSTONED,
        )

    def list_tombstones(self) -> list[LifecycleStateRecord]:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT tenant_id, generation_id, state, effective_at, security_epoch, revocation_floor, erasure_request_ref, digest FROM durable_tenant_lifecycle_states WHERE state IN (?, ?)",
                (LifecycleState.DELETION_IN_PROGRESS.value, LifecycleState.TOMBSTONED.value),
            )
            rows = cursor.fetchall()
            return [
                LifecycleStateRecord(
                    tenant_id=r[0],
                    generation_id=r[1],
                    state=LifecycleState(r[2]),
                    effective_at=r[3],
                    security_epoch=r[4],
                    revocation_floor=r[5],
                    erasure_request_ref=r[6],
                    digest=r[7],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def list_all(self) -> list[LifecycleStateRecord]:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT tenant_id, generation_id, state, effective_at, security_epoch, revocation_floor, erasure_request_ref, digest FROM durable_tenant_lifecycle_states"
            )
            rows = cursor.fetchall()
            return [
                LifecycleStateRecord(
                    tenant_id=r[0],
                    generation_id=r[1],
                    state=LifecycleState(r[2]),
                    effective_at=r[3],
                    security_epoch=r[4],
                    revocation_floor=r[5],
                    erasure_request_ref=r[6],
                    digest=r[7],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def verify_integrity(self) -> bool:
        if not self._available or self._corrupted:
            return False
        try:
            conn = self._get_connection()
        except Exception:
            return False
        try:
            cursor = conn.execute(
                "SELECT tenant_id, generation_id, state, effective_at, security_epoch, revocation_floor, erasure_request_ref, digest FROM durable_tenant_lifecycle_states"
            )
            rows = cursor.fetchall()
            for r in rows:
                expected = compute_lifecycle_digest(
                    tenant_id=r[0],
                    generation_id=r[1],
                    state=r[2],
                    effective_at=r[3],
                    security_epoch=r[4],
                    revocation_floor=r[5],
                    erasure_request_ref=r[6],
                    secret_key=self._secret_key,
                )
                if r[7] != expected:
                    return False
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_corrupted(self, corrupted: bool) -> None:
        self._corrupted = corrupted

    def get_readiness_state(self) -> RestoreReadinessState | None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT state FROM durable_restore_readiness WHERE key = 'global'"
            )
            row = cursor.fetchone()
            if not row:
                return None
            return RestoreReadinessState(row[0])
        finally:
            conn.close()

    def set_readiness_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        now = datetime.now(UTC).isoformat()
        conn = self._get_connection()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO durable_restore_readiness (key, state, epoch, updated_at, updated_by)
                    VALUES ('global', ?, 1, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        state = excluded.state,
                        epoch = durable_restore_readiness.epoch + 1,
                        updated_at = excluded.updated_at,
                        updated_by = excluded.updated_by
                    """,
                    (state.value, now, updated_by),
                )
        finally:
            conn.close()


DurableLifecycleStateProvider = SqliteDurableLifecycleStateProvider


class InMemoryLifecycleStateProvider(CurrentLifecycleStateProvider):
    """Thread-safe, independently persisted in-memory lifecycle state provider representing Store B for test fixtures."""

    def __init__(self) -> None:
        self._records: dict[str, LifecycleStateRecord] = {}
        self._available: bool = True
        self._corrupted: bool = False
        self._readiness_state: RestoreReadinessState | None = None

    def record_state(self, record: LifecycleStateRecord) -> None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")

        expected_digest = compute_lifecycle_digest(
            tenant_id=record.tenant_id,
            generation_id=record.generation_id,
            state=record.state.value,
            effective_at=record.effective_at,
            security_epoch=record.security_epoch,
            revocation_floor=record.revocation_floor,
            erasure_request_ref=record.erasure_request_ref,
        )
        if record.digest and record.digest != expected_digest:
            raise LifecycleIntegrityError("Tampered lifecycle state record digest")

        if record.tenant_id in self._records:
            existing = self._records[record.tenant_id]
            curr_rank = _STATE_RANK.get(existing.state, 0)
            new_rank = _STATE_RANK.get(record.state, 0)
            if new_rank < curr_rank:
                raise LifecycleRollbackError(
                    f"Lifecycle state rollback rejected: cannot transition from {existing.state.value} to {record.state.value}"
                )
            if record.security_epoch < existing.security_epoch:
                raise LifecycleRollbackError(
                    f"Security epoch rollback rejected: {record.security_epoch} < {existing.security_epoch}"
                )
            if (
                new_rank == curr_rank
                and record.security_epoch == existing.security_epoch
                and record.effective_at <= existing.effective_at
                and record.generation_id == existing.generation_id
            ):
                return

        digest_to_store = record.digest or expected_digest
        self._records[record.tenant_id] = LifecycleStateRecord(
            tenant_id=record.tenant_id,
            generation_id=record.generation_id,
            state=record.state,
            effective_at=record.effective_at,
            security_epoch=record.security_epoch,
            revocation_floor=record.revocation_floor,
            erasure_request_ref=record.erasure_request_ref,
            digest=digest_to_store,
        )

    def get_state(self, tenant_id: str) -> LifecycleStateRecord | None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        return self._records.get(tenant_id)

    def is_tombstoned(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state == LifecycleState.TOMBSTONED

    def is_deletion_in_progress(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state in (
            LifecycleState.DELETION_IN_PROGRESS,
            LifecycleState.TOMBSTONED,
        )

    def list_tombstones(self) -> list[LifecycleStateRecord]:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        return [
            r
            for r in self._records.values()
            if r.state in (LifecycleState.DELETION_IN_PROGRESS, LifecycleState.TOMBSTONED)
        ]

    def list_all(self) -> list[LifecycleStateRecord]:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        return list(self._records.values())

    def verify_integrity(self) -> bool:
        if not self._available or self._corrupted:
            return False
        for rec in self._records.values():
            expected = compute_lifecycle_digest(
                tenant_id=rec.tenant_id,
                generation_id=rec.generation_id,
                state=rec.state.value,
                effective_at=rec.effective_at,
                security_epoch=rec.security_epoch,
                revocation_floor=rec.revocation_floor,
                erasure_request_ref=rec.erasure_request_ref,
            )
            if rec.digest and rec.digest != expected:
                return False
        return True

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_corrupted(self, corrupted: bool) -> None:
        self._corrupted = corrupted

    def get_readiness_state(self) -> RestoreReadinessState | None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        return self._readiness_state

    def set_readiness_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        self._readiness_state = state


class RestoreReadinessGate:
    """Operational readiness admission gate for restored environments."""

    def __init__(
        self,
        initial_state: RestoreReadinessState = RestoreReadinessState.RESTORE_PENDING,
        provider: CurrentLifecycleStateProvider | None = None,
    ) -> None:
        self._local_state = initial_state
        self._provider = provider

    @property
    def state(self) -> RestoreReadinessState:
        if self._provider is not None:
            try:
                shared = self._provider.get_readiness_state()
                if shared is not None:
                    return shared
            except Exception:
                return RestoreReadinessState.FAILED
        return self._local_state

    def set_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        self._local_state = state
        if self._provider is not None:
            try:
                self._provider.set_readiness_state(state, updated_by=updated_by)
            except Exception:
                self._local_state = RestoreReadinessState.FAILED
                raise

    def is_admitted(self) -> bool:
        return self.state == RestoreReadinessState.READY

    def assert_traffic_admitted(self) -> None:
        """Enforce that traffic is only served once lifecycle reconciliation succeeds."""
        current_state = self.state
        if current_state != RestoreReadinessState.READY:
            raise RestoreQuarantineError(
                f"Operational traffic blocked: system is in {current_state.value} state."
            )


_GLOBAL_RESTORE_GATE: RestoreReadinessGate | None = None


def is_restore_pending_default() -> bool:
    return (
        os.environ.get("WHITEPACT_RESTORE_MODE") == "1"
        or os.environ.get("WHITEPACT_RESTORE_PENDING") == "1"
    )


def get_restore_readiness_gate() -> RestoreReadinessGate:
    global _GLOBAL_RESTORE_GATE
    if _GLOBAL_RESTORE_GATE is None:
        initial = (
            RestoreReadinessState.RESTORE_PENDING
            if is_restore_pending_default()
            else RestoreReadinessState.READY
        )
        provider = None
        store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
            "WHITEPACT_LIFECYCLE_STORE_PATH"
        )
        if store_b_path:
            try:
                provider = DurableLifecycleStateProvider(store_b_path)
            except Exception:
                provider = None
        _GLOBAL_RESTORE_GATE = RestoreReadinessGate(initial_state=initial, provider=provider)
    return _GLOBAL_RESTORE_GATE


def set_restore_readiness_gate(gate: RestoreReadinessGate | None) -> None:
    global _GLOBAL_RESTORE_GATE
    _GLOBAL_RESTORE_GATE = gate


def reset_restore_readiness_gate(
    state: RestoreReadinessState = RestoreReadinessState.RESTORE_PENDING,
    provider: CurrentLifecycleStateProvider | None = None,
) -> RestoreReadinessGate:
    global _GLOBAL_RESTORE_GATE
    _GLOBAL_RESTORE_GATE = RestoreReadinessGate(initial_state=state, provider=provider)
    return _GLOBAL_RESTORE_GATE


def assert_restore_readiness_admitted() -> None:
    get_restore_readiness_gate().assert_traffic_admitted()


@dataclass(frozen=True)
class TenantTombstone:
    id: str
    org_id: str
    original_name: str
    generation_id: str
    tombstoned_at: str
    tombstoned_by: str
    authority_hash: str
    evidence_digest: str
    details: dict[str, Any]


@dataclass(frozen=True)
class RestoreReconciliationReport:
    id: str
    restored_at: str
    status: str
    tombstones_detected: int
    tenants_quarantined: int
    reconciled_by: str
    details: dict[str, Any]


class TombstoneLedger:
    """Query interface for persistent tenant tombstones."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get_tombstone(self, org_id: str) -> TenantTombstone | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(tenant_tombstones).where(tenant_tombstones.c.org_id == org_id)
                )
            ).fetchone()
            if not row:
                return None
            return TenantTombstone(
                id=row.id,
                org_id=row.org_id,
                original_name=row.original_name,
                generation_id=row.generation_id,
                tombstoned_at=row.tombstoned_at,
                tombstoned_by=row.tombstoned_by,
                authority_hash=row.authority_hash,
                evidence_digest=row.evidence_digest,
                details=json.loads(row.details_json) if row.details_json else {},
            )

    async def is_tombstoned(self, org_id: str) -> bool:
        ts = await self.get_tombstone(org_id)
        return ts is not None


class RestoreReconciliationEngine:
    """Audits restored database state against the current lifecycle security store (Store B)."""

    def __init__(
        self,
        engine: DatabaseEngine,
        lifecycle_provider: CurrentLifecycleStateProvider | None = None,
        gate: RestoreReadinessGate | None = None,
        require_durable: bool | None = None,
    ) -> None:
        self._engine = engine
        is_prod = is_production_environment()
        must_require_durable = require_durable if require_durable is not None else is_prod

        if must_require_durable:
            if lifecycle_provider is None:
                store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
                    "WHITEPACT_LIFECYCLE_STORE_PATH"
                )
                if store_b_path:
                    try:
                        lifecycle_provider = DurableLifecycleStateProvider(store_b_path)
                    except Exception as e:
                        if gate:
                            gate.set_state(RestoreReadinessState.FAILED)
                        raise MissingLifecycleProviderError(
                            f"Failed to initialize durable Store-B provider: {e}"
                        ) from e
                else:
                    if gate:
                        gate.set_state(RestoreReadinessState.FAILED)
                    raise MissingLifecycleProviderError(
                        "Durable Store-B CurrentLifecycleStateProvider is required in production/strict restore reconciliation."
                    )
            elif isinstance(lifecycle_provider, InMemoryLifecycleStateProvider):
                if gate:
                    gate.set_state(RestoreReadinessState.FAILED)
                raise MissingLifecycleProviderError(
                    "InMemoryLifecycleStateProvider is forbidden in production/strict restore reconciliation."
                )

        if lifecycle_provider is None:
            store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
                "WHITEPACT_LIFECYCLE_STORE_PATH"
            )
            if store_b_path:
                lifecycle_provider = DurableLifecycleStateProvider(store_b_path)
            else:
                lifecycle_provider = InMemoryLifecycleStateProvider()

        self._provider: CurrentLifecycleStateProvider = lifecycle_provider
        self._gate: RestoreReadinessGate = gate or RestoreReadinessGate(provider=self._provider)
        self._ledger = TombstoneLedger(engine)

    @property
    def gate(self) -> RestoreReadinessGate:
        return self._gate

    @property
    def provider(self) -> CurrentLifecycleStateProvider:
        return self._provider

    async def reconcile_post_restore(self, reconciled_by: str) -> RestoreReconciliationReport:
        """Reconcile restored organizations against current lifecycle state from Store B.

        Fail-Closed Reconciliation Protocol:
        1. Atomically marks gate as RECONCILING.
        2. Validates cryptographic integrity and availability of Store B.
        3. Identifies all tombstones from Store B and existing Store A tombstones.
        4. For every tombstoned/resurrected tenant:
           - Quarantines organization with supported governance_status="DISABLED" (satisfying
             PostgreSQL chk_org_governance_status constraint) and suffixed name.
           - Executes a strictly ordered topological FK purge of active operational authority:
             runtime_worker_leases -> runtime_execution_dispatch_outbox -> runtime_execution_fences ->
             runtime_execution_attempts -> governance_execution_authorizations ->
             runtime_execution_requests -> governance_approval_votes -> governance_approvals ->
             governance_policy_activations -> governance_policy_revisions ->
             governance_policy_versions -> governance_policies -> governance_policy_history ->
             governance_execution_nonces -> governance_delegations -> org_api_key_metadata ->
             org_api_keys -> iam_api_key_lineage -> web_sessions -> iam_sessions ->
             eval_runs -> eval_baselines -> mcp_tool_calls -> token_usage ->
             iam_scim_users -> iam_scim_groups -> web_memberships.
           - Forensically revokes root authority records and consent proofs (revoked_at=now,
             revoked_by=reconciled_by) so no restored root or consent record ever confers active authority,
             preserving audit evidence without violating legal retention obligations or FK integrity.
           - Durably elevates tenant revocation epochs to max(current_epoch + 1, store_b_floor)
             across canonical "governance" and "tenant_global" scopes without arbitrary constants.
        5. Synchronizes Store B revocation floors across all active tenants in Store A:
           ensures canonical "governance" and "tenant_global" scopes meet or exceed
           max(security_epoch, revocation_floor).
        6. Synchronizes tombstone ledger in Store A from Store B.
        7. Triggers active in-flight execution containment against InFlightExecutionRegistry.
        8. Durably records reconciliation audit trail in restore_reconciliation_records.
        9. Advances gate to READY only upon complete error-free transaction commit; on any
           failure, transitions gate to FAILED, logs the failure, and fails closed.
        """
        now = _now()
        rec_id = str(uuid.uuid4())
        quarantined_orgs: list[str] = []
        revoked_sessions = 0
        revoked_keys = 0
        erased_records = 0
        fenced_epochs = 0
        revoked_root_records = 0
        revoked_consent_proofs = 0

        # Mark gate as RECONCILING
        self._gate.set_state(RestoreReadinessState.RECONCILING, updated_by=reconciled_by)

        try:
            # 1. Verify provider integrity and availability
            if not self._provider.verify_integrity():
                self._gate.set_state(RestoreReadinessState.FAILED)
                raise RestoreReconciliationError(
                    "CurrentLifecycleStateProvider integrity check failed or provider unavailable."
                )

            # 2. Fetch tombstones from independent Store B
            tombstones_b = self._provider.list_tombstones()
            tombstoned_ids = {t.tenant_id for t in tombstones_b}

            async with self._engine.raw.begin() as conn:
                # Also include any tombstones already in Store A
                tombstones_a = (await conn.execute(select(tenant_tombstones))).fetchall()
                for t in tombstones_a:
                    tombstoned_ids.add(t.org_id)

                if tombstoned_ids:
                    # Find restored orgs matching tombstone IDs
                    matching_orgs = (
                        await conn.execute(
                            select(organizations).where(organizations.c.id.in_(tombstoned_ids))
                        )
                    ).fetchall()

                    for org in matching_orgs:
                        org_id = org.id
                        # Force quarantine using supported PostgreSQL governance_status
                        new_name = (
                            f"{org.name}-RESTORE_QUARANTINED"
                            if "-RESTORE_QUARANTINED" not in org.name
                            else org.name
                        )
                        await conn.execute(
                            update(organizations)
                            .where(organizations.c.id == org_id)
                            .values(
                                name=new_name,
                                governance_status=GovernanceStatus.DISABLED.value,
                                deactivated_at=now,
                            )
                        )
                        quarantined_orgs.append(org_id)

                        # Collect foreign key IDs for safe child deletion
                        req_rows = (
                            await conn.execute(
                                select(runtime_execution_requests.c.request_id).where(
                                    runtime_execution_requests.c.organization_id == org_id
                                )
                            )
                        ).fetchall()
                        tenant_req_ids = [r[0] for r in req_rows]

                        app_rows = (
                            await conn.execute(
                                select(governance_approvals.c.id).where(
                                    governance_approvals.c.org_id == org_id
                                )
                            )
                        ).fetchall()
                        tenant_app_ids = [r[0] for r in app_rows]

                        key_rows = (
                            await conn.execute(
                                select(org_api_keys.c.id).where(org_api_keys.c.org_id == org_id)
                            )
                        ).fetchall()
                        tenant_key_ids = [r[0] for r in key_rows]

                        # --- Strict Topological Cascade Purge ---
                        # 1. runtime_worker_leases (references attempts, requests, organizations)
                        await conn.execute(
                            delete(runtime_worker_leases).where(
                                runtime_worker_leases.c.organization_id == org_id
                            )
                        )
                        if tenant_req_ids:
                            await conn.execute(
                                delete(runtime_worker_leases).where(
                                    runtime_worker_leases.c.request_id.in_(tenant_req_ids)
                                )
                            )

                        # 2. runtime_execution_dispatch_outbox (references attempts, requests, organizations)
                        await conn.execute(
                            delete(runtime_execution_dispatch_outbox).where(
                                runtime_execution_dispatch_outbox.c.organization_id == org_id
                            )
                        )
                        if tenant_req_ids:
                            await conn.execute(
                                delete(runtime_execution_dispatch_outbox).where(
                                    runtime_execution_dispatch_outbox.c.request_id.in_(tenant_req_ids)
                                )
                            )

                        # 3. runtime_execution_fences (references requests)
                        if tenant_req_ids:
                            await conn.execute(
                                delete(runtime_execution_fences).where(
                                    runtime_execution_fences.c.request_id.in_(tenant_req_ids)
                                )
                            )

                        # 4. runtime_execution_attempts (references authorizations, requests, organizations)
                        await conn.execute(
                            delete(runtime_execution_attempts).where(
                                runtime_execution_attempts.c.organization_id == org_id
                            )
                        )
                        if tenant_req_ids:
                            await conn.execute(
                                delete(runtime_execution_attempts).where(
                                    runtime_execution_attempts.c.request_id.in_(tenant_req_ids)
                                )
                            )

                        # 5. governance_execution_authorizations (references requests, approvals, organizations)
                        r_auth = await conn.execute(
                            delete(governance_execution_authorizations).where(
                                governance_execution_authorizations.c.organization_id == org_id
                            )
                        )
                        erased_records += r_auth.rowcount or 0

                        # 6. runtime_execution_requests:
                        # CRITICAL INVARIANT: runtime_execution_requests is immutable audit evidence
                        # and admission state (protected by PostgreSQL trigger reject_execution_request_mutation).
                        # Prohibits UPDATE and DELETE; rows must be preserved.

                        # 7 & 8. governance_approvals and governance_approval_votes:
                        # runtime_execution_requests.approval_id has ON DELETE RESTRICT to governance_approvals.id.
                        # Approvals referenced by runtime_execution_requests cannot be deleted without violating FK RESTRICT.
                        # Therefore, we partition approvals:
                        # - Referenced approvals are neutralized/revoked (status='REVOKED', resolved_by=reconciled_by)
                        #   so they can never confer execution authority, while preserving evidence integrity.
                        # - Unreferenced approvals (and their votes) are safely deleted topologically.
                        ref_req_app_rows = (
                            await conn.execute(
                                select(runtime_execution_requests.c.approval_id).where(
                                    runtime_execution_requests.c.organization_id == org_id,
                                    runtime_execution_requests.c.approval_id.isnot(None),
                                )
                            )
                        ).fetchall()
                        referenced_app_ids = {r[0] for r in ref_req_app_rows if r[0]}
                        unreferenced_app_ids = set(tenant_app_ids) - referenced_app_ids

                        if referenced_app_ids:
                            await conn.execute(
                                update(governance_approvals)
                                .where(
                                    governance_approvals.c.id.in_(referenced_app_ids),
                                    governance_approvals.c.status != "REVOKED",
                                )
                                .values(
                                    status="REVOKED",
                                    resolved_by=reconciled_by,
                                    resolved_at=now,
                                    resolution_notes="Tenant tombstoned during post-restore reconciliation",
                                )
                            )

                        if unreferenced_app_ids:
                            await conn.execute(
                                delete(governance_approval_votes).where(
                                    governance_approval_votes.c.approval_id.in_(unreferenced_app_ids)
                                )
                            )
                            r_app = await conn.execute(
                                delete(governance_approvals).where(
                                    governance_approvals.c.id.in_(unreferenced_app_ids)
                                )
                            )
                            erased_records += r_app.rowcount or 0

                        # 9. Policy hierarchy: activations -> revisions -> versions -> policies -> history
                        await conn.execute(
                            delete(governance_policy_activations).where(
                                governance_policy_activations.c.org_id == org_id
                            )
                        )
                        await conn.execute(
                            delete(governance_policy_revisions).where(
                                governance_policy_revisions.c.org_id == org_id
                            )
                        )
                        await conn.execute(
                            delete(governance_policy_versions).where(
                                governance_policy_versions.c.org_id == org_id
                            )
                        )
                        await conn.execute(
                            delete(governance_policies).where(governance_policies.c.org_id == org_id)
                        )
                        await conn.execute(
                            delete(governance_policy_history).where(
                                governance_policy_history.c.org_id == org_id
                            )
                        )

                        # 10. Nonces & delegations
                        r_nonces = await conn.execute(
                            delete(governance_execution_nonces).where(
                                governance_execution_nonces.c.organization_id == org_id
                            )
                        )
                        r_del = await conn.execute(
                            delete(governance_delegations).where(
                                governance_delegations.c.org_id == org_id
                            )
                        )
                        erased_records += (r_nonces.rowcount or 0) + (r_del.rowcount or 0)

                        # 11. Sessions
                        r_s = await conn.execute(
                            delete(web_sessions).where(web_sessions.c.org_id == org_id)
                        )
                        r_is = await conn.execute(
                            delete(iam_sessions).where(iam_sessions.c.org_id == org_id)
                        )
                        revoked_sessions += (r_s.rowcount or 0) + (r_is.rowcount or 0)

                        # 12. API keys & lineage
                        if tenant_key_ids:
                            await conn.execute(
                                delete(org_api_key_metadata).where(
                                    org_api_key_metadata.c.key_id.in_(tenant_key_ids)
                                )
                            )
                        r_k = await conn.execute(
                            delete(org_api_keys).where(org_api_keys.c.org_id == org_id)
                        )
                        r_ik = await conn.execute(
                            delete(iam_api_key_lineage).where(
                                iam_api_key_lineage.c.org_id == org_id
                            )
                        )
                        revoked_keys += (r_k.rowcount or 0) + (r_ik.rowcount or 0)

                        # 13. Evaluative and transient operational data
                        for tbl, col in [
                            (eval_runs, "org_id"),
                            (eval_baselines, "org_id"),
                            (mcp_tool_calls, "org_id"),
                            (token_usage, "org_id"),
                            (iam_scim_users, "org_id"),
                            (iam_scim_groups, "org_id"),
                            (web_memberships, "org_id"),
                        ]:
                            c_attr = getattr(tbl.c, col)
                            r_eval = await conn.execute(delete(tbl).where(c_attr == org_id))
                            erased_records += r_eval.rowcount or 0

                        # 14. Forensically revoke root authority records and consent proofs
                        # Preserves forensic evidence for audit without leaving active authority
                        r_root = await conn.execute(
                            update(governance_root_authority_records)
                            .where(
                                governance_root_authority_records.c.organization_id == org_id,
                                governance_root_authority_records.c.revoked_at.is_(None),
                            )
                            .values(
                                revoked_at=now,
                                revoked_by=reconciled_by,
                                revoke_reason="Tombstoned tenant post-restore reconciliation fencing",
                            )
                        )
                        revoked_root_records += r_root.rowcount or 0

                        r_cp = await conn.execute(
                            update(governance_consent_proofs)
                            .where(
                                governance_consent_proofs.c.organization_id == org_id,
                                governance_consent_proofs.c.revoked_at.is_(None),
                            )
                            .values(
                                revoked_at=now,
                                revoked_by=reconciled_by,
                                revoke_reason="Tombstoned tenant post-restore reconciliation fencing",
                            )
                        )
                        revoked_consent_proofs += r_cp.rowcount or 0

                        # 15. Monotonic epoch advancement for tombstoned tenant
                        store_b_rec = self._provider.get_state(org_id)
                        floor = (
                            max(store_b_rec.security_epoch, store_b_rec.revocation_floor)
                            if store_b_rec
                            else 1
                        )
                        existing_epochs = (
                            await conn.execute(
                                select(
                                    governance_revocation_epochs.c.scope,
                                    governance_revocation_epochs.c.epoch,
                                ).where(governance_revocation_epochs.c.organization_id == org_id)
                            )
                        ).fetchall()
                        known_scopes = {row[0]: row[1] for row in existing_epochs}
                        for sc, ep in known_scopes.items():
                            target_epoch = max(ep + 1, floor)
                            await conn.execute(
                                update(governance_revocation_epochs)
                                .where(
                                    governance_revocation_epochs.c.organization_id == org_id,
                                    governance_revocation_epochs.c.scope == sc,
                                )
                                .values(epoch=target_epoch, updated_at=now)
                            )
                            fenced_epochs += 1

                        for required_scope in ("governance", "tenant_global"):
                            if required_scope not in known_scopes:
                                await conn.execute(
                                    insert(governance_revocation_epochs).values(
                                        organization_id=org_id,
                                        scope=required_scope,
                                        epoch=max(1, floor),
                                        updated_at=now,
                                    )
                                )
                                fenced_epochs += 1

                    # Ensure Store A tenant_tombstones contains all Store B tombstones
                    existing_a_ids = {t.org_id for t in tombstones_a}
                    for tb in tombstones_b:
                        if tb.tenant_id not in existing_a_ids:
                            await conn.execute(
                                insert(tenant_tombstones).values(
                                    id=str(uuid.uuid4()),
                                    org_id=tb.tenant_id,
                                    original_name=f"Tombstoned-{tb.tenant_id}",
                                    generation_id=tb.generation_id,
                                    tombstoned_at=tb.effective_at,
                                    tombstoned_by=reconciled_by,
                                    authority_hash=tb.digest or "tombstone-hash",
                                    evidence_digest=tb.digest or "tombstone-digest",
                                    details_json=json.dumps({"reconciled_from_store_b": True}),
                                )
                            )
                            existing_a_ids.add(tb.tenant_id)

                # Synchronize revocation floors from Store B for all active records
                all_b_records = self._provider.list_all()
                for rec in all_b_records:
                    if rec.tenant_id in tombstoned_ids:
                        continue
                    floor = max(rec.security_epoch, rec.revocation_floor)
                    if floor <= 0:
                        continue

                    existing_epochs = (
                        await conn.execute(
                            select(
                                governance_revocation_epochs.c.scope,
                                governance_revocation_epochs.c.epoch,
                            ).where(governance_revocation_epochs.c.organization_id == rec.tenant_id)
                        )
                    ).fetchall()
                    known_scopes = {row[0]: row[1] for row in existing_epochs}

                    for sc, ep in known_scopes.items():
                        if ep < floor:
                            await conn.execute(
                                update(governance_revocation_epochs)
                                .where(
                                    governance_revocation_epochs.c.organization_id == rec.tenant_id,
                                    governance_revocation_epochs.c.scope == sc,
                                )
                                .values(epoch=floor, updated_at=now)
                            )
                            fenced_epochs += 1

                    org_exists = (
                        await conn.execute(
                            select(organizations.c.id).where(
                                organizations.c.id == rec.tenant_id
                            )
                        )
                    ).fetchone()
                    if org_exists:
                        for required_scope in ("governance", "tenant_global"):
                            if required_scope not in known_scopes:
                                await conn.execute(
                                    insert(governance_revocation_epochs).values(
                                        organization_id=rec.tenant_id,
                                        scope=required_scope,
                                        epoch=floor,
                                        updated_at=now,
                                    )
                                )
                                fenced_epochs += 1
                            elif known_scopes[required_scope] < floor:
                                await conn.execute(
                                    update(governance_revocation_epochs)
                                    .where(
                                        governance_revocation_epochs.c.organization_id == rec.tenant_id,
                                        governance_revocation_epochs.c.scope == required_scope,
                                    )
                                    .values(epoch=floor, updated_at=now)
                                )
                                fenced_epochs += 1

                status = "RECONCILED"
                details = {
                    "quarantined_orgs": quarantined_orgs,
                    "revoked_sessions": revoked_sessions,
                    "revoked_keys": revoked_keys,
                    "erased_records": erased_records,
                    "fenced_epochs": fenced_epochs,
                    "revoked_root_records": revoked_root_records,
                    "revoked_consent_proofs": revoked_consent_proofs,
                }

                await conn.execute(
                    insert(restore_reconciliation_records).values(
                        id=rec_id,
                        restored_at=now,
                        status=status,
                        tombstones_detected=len(tombstoned_ids),
                        tenants_quarantined=len(quarantined_orgs),
                        details_json=json.dumps(details),
                        reconciled_by=reconciled_by,
                    )
                )

            # In-flight execution containment
            try:
                from responsibleai.isolation.in_flight import InFlightExecutionRegistry

                registry = InFlightExecutionRegistry.get_instance()
                for q_org in quarantined_orgs:
                    await registry.terminate_in_flight(organization_id=q_org)
                await registry.reconcile_epochs(self._engine)
            except Exception:
                pass

            # Reached here without error -> advance gate to READY
            self._gate.set_state(RestoreReadinessState.READY, updated_by=reconciled_by)

            return RestoreReconciliationReport(
                id=rec_id,
                restored_at=now,
                status=status,
                tombstones_detected=len(tombstoned_ids),
                tenants_quarantined=len(quarantined_orgs),
                reconciled_by=reconciled_by,
                details=details,
            )

        except Exception as exc:
            # On failure, transition gate to FAILED so traffic remains blocked
            self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
            try:
                async with self._engine.raw.begin() as conn:
                    await conn.execute(
                        insert(restore_reconciliation_records).values(
                            id=rec_id,
                            restored_at=now,
                            status="FAILED",
                            tombstones_detected=0,
                            tenants_quarantined=0,
                            details_json=json.dumps({"error": str(exc)}),
                            reconciled_by=reconciled_by,
                        )
                    )
            except Exception:
                pass
            if isinstance(exc, RestoreReconciliationError):
                raise
            raise RestoreReconciliationError(f"Restore reconciliation aborted: {exc}") from exc


BackupResurrectionDefense = RestoreReconciliationEngine
