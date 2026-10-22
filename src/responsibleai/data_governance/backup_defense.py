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
        conn = sqlite3.connect(
            self._path.as_uri() + "?mode=rw", uri=True, timeout=10.0, isolation_level=None
        )
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

    def requires_operator_recovery(self) -> bool:
        """A hosted failure cannot become a development recovery by changing flags."""
        conn = self._get_connection()
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operator_recovery_policy'"
            ).fetchone()
            return bool(
                exists
                and conn.execute(
                    "SELECT 1 FROM operator_recovery_policy WHERE id=1 AND required=1"
                ).fetchone()
            )
        finally:
            conn.close()

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
                from responsibleai.data_governance.operator_recovery_control import (
                    assert_completed_binding,
                )

                if self.requires_operator_recovery():
                    from responsibleai.data_governance.operator_recovery import (
                        RecoveryAuthorizationError,
                    )

                    raise RecoveryAuthorizationError(
                        "Durable recovery readiness evidence is missing"
                    )
                assert_completed_binding(self)
                return None
            state = RestoreReadinessState(row[0])
            if state == RestoreReadinessState.READY:
                from responsibleai.data_governance.operator_recovery_control import (
                    assert_completed_binding,
                )

                verified = assert_completed_binding(self)
                if self.requires_operator_recovery() and not verified:
                    from responsibleai.data_governance.operator_recovery import (
                        RecoveryAuthorizationError,
                    )

                    raise RecoveryAuthorizationError(
                        "Hosted recovery READY requires a completed signed receipt"
                    )
            return state
        finally:
            conn.close()

    def set_readiness_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        if not self._available:
            raise StoreBUnavailableError("CurrentLifecycleStateProvider is unavailable")
        if state == RestoreReadinessState.READY:
            from responsibleai.data_governance.operator_recovery_control import (
                assert_ready_write_authorized,
            )

            # First establishment remains distinct from recovery of a durable
            # non-READY state. Caller labels never confer operator authority.
            if self.get_readiness_state() not in (None, RestoreReadinessState.READY):
                assert_ready_write_authorized(self)
        now = datetime.now(UTC).isoformat()
        conn = self._get_connection()
        try:
            with conn:
                from responsibleai.data_governance.operator_recovery_control import (
                    enforcement_required,
                )

                conn.execute("BEGIN IMMEDIATE")
                if state != RestoreReadinessState.READY and enforcement_required():
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS operator_recovery_policy "
                        "(id INTEGER PRIMARY KEY CHECK(id=1),required INTEGER NOT NULL CHECK(required=1))"
                    )
                    conn.execute("INSERT OR IGNORE INTO operator_recovery_policy VALUES(1,1)")
                if state == RestoreReadinessState.READY:
                    from responsibleai.data_governance.operator_recovery_control import (
                        authorized_ready_epoch,
                    )

                    if enforcement_required() or self.requires_operator_recovery():
                        current = conn.execute(
                            "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
                        ).fetchone()
                        if current and current[0] != RestoreReadinessState.READY:
                            expected_epoch = authorized_ready_epoch(self)
                            if current != (RestoreReadinessState.RECONCILING, expected_epoch):
                                from responsibleai.data_governance.operator_recovery import (
                                    RecoveryAuthorizationError,
                                )

                                raise RecoveryAuthorizationError(
                                    "Recovery readiness compare-and-swap failed"
                                )
                            from responsibleai.data_governance.operator_recovery_control import (
                                validate_ready_lifecycle,
                            )

                            validate_ready_lifecycle(self)
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
        if state == RestoreReadinessState.READY and self._readiness_state not in (
            None,
            RestoreReadinessState.READY,
        ):
            from responsibleai.data_governance.operator_recovery_control import (
                assert_ready_write_authorized,
            )

            assert_ready_write_authorized(self)
        self._readiness_state = state


class StartupAuthorityMode(StrEnum):
    NORMAL = "NORMAL"
    RECOVERY = "RECOVERY"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class StartupAuthorityEvaluation:
    mode: StartupAuthorityMode
    readiness_state: RestoreReadinessState
    reason: str
    durable_provider_present: bool
    integrity_verified: bool


class RestoreReadinessGate:
    """Operational readiness admission gate for restored environments."""

    def __init__(
        self,
        initial_state: RestoreReadinessState = RestoreReadinessState.RESTORE_PENDING,
        provider: CurrentLifecycleStateProvider | None = None,
        db_engine: DatabaseEngine | None = None,
    ) -> None:
        self._local_state = initial_state
        self._provider_error: str | None = None
        self._db_engine = db_engine
        self._db_authority_status: str | None = None
        if provider is None:
            store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
                "WHITEPACT_LIFECYCLE_STORE_PATH"
            )
            if store_b_path:
                try:
                    provider = DurableLifecycleStateProvider(store_b_path)
                except Exception as exc:
                    self._provider_error = str(exc)
                    provider = None
            elif is_restore_pending_default():
                self._provider_error = "Recovery startup requires durable Store B provider"
            elif is_production_environment():
                self._provider_error = "Production environment requires durable Store B provider"
        self._provider = provider
        from responsibleai.data_governance.operator_recovery_control import enforcement_required

        if enforcement_required() and type(provider) is not SqliteDurableLifecycleStateProvider:
            self._provider_error = "Hosted readiness requires the durable Store B provider"

    @property
    def provider(self) -> CurrentLifecycleStateProvider | None:
        return self._provider

    @property
    def provider_error(self) -> str | None:
        return self._provider_error

    def _retain_provider_failure(self) -> None:
        self._local_state = RestoreReadinessState.FAILED
        self._provider_error = "Store B recovery evidence could not be verified"
        from responsibleai.data_governance.operator_recovery_control import (
            record_restrictive_failure,
        )

        try:
            record_restrictive_failure()
        except Exception:
            # Local quarantine remains effective even when the independent
            # receipt store is unavailable; no permissive storage fallback.
            pass
        if self._provider is not None:
            try:
                self._provider.set_readiness_state(
                    RestoreReadinessState.FAILED, updated_by="provider_failure"
                )
            except Exception:
                pass

    @property
    def state(self) -> RestoreReadinessState:
        # If Store B was configured but could not be initialized (corrupt, unreadable, permission denied)
        if self._provider_error is not None:
            return RestoreReadinessState.FAILED

        # If provider is present, consult durable state with integrity verification
        if self._provider is not None:
            from responsibleai.data_governance.operator_recovery_control import (
                RecoveryInProgressError,
            )

            try:
                if (
                    hasattr(self._provider, "verify_integrity")
                    and not self._provider.verify_integrity()
                ):
                    self._retain_provider_failure()
                    return RestoreReadinessState.FAILED
                shared = self._provider.get_readiness_state()
                if shared is not None:
                    return shared
            except RecoveryInProgressError:
                return RestoreReadinessState.RECONCILING
            except Exception:
                self._retain_provider_failure()
                return RestoreReadinessState.FAILED

        # If restore mode is active via environment, gate must be at least RESTORE_PENDING
        if is_restore_pending_default():
            return (
                self._local_state
                if self._local_state != RestoreReadinessState.READY
                else RestoreReadinessState.RESTORE_PENDING
            )

        return self._local_state

    def set_state(self, state: RestoreReadinessState, updated_by: str = "") -> None:
        if state == RestoreReadinessState.READY and self.state != RestoreReadinessState.READY:
            from responsibleai.data_governance.operator_recovery_control import (
                assert_ready_write_authorized,
            )

            assert_ready_write_authorized(self._provider)
        self._local_state = state
        if self._provider_error is not None and state != RestoreReadinessState.FAILED:
            raise StoreBUnavailableError(
                f"Cannot transition state: Store B provider failed to initialize: {self._provider_error}"
            )
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
        if self._db_engine is not None:
            raise RestoreQuarantineError(
                "Current database authority requires asynchronous admission verification."
            )
        self._assert_state_admitted()

    def _assert_state_admitted(self) -> None:
        current_state = self.state
        if current_state != RestoreReadinessState.READY:
            raise RestoreQuarantineError(
                f"Operational traffic blocked: system is in {current_state.value} state."
            )

    async def assert_current_traffic_admitted(self, engine: DatabaseEngine | None = None) -> None:
        """Check durable database authority on every consequential admission."""
        await self.check_database_authority(engine)
        self._assert_state_admitted()

    async def check_database_authority(
        self, engine: DatabaseEngine | None = None
    ) -> RestoreReadinessState:
        """Validate database-level restore consistency alongside durable provider."""
        eng = engine or self._db_engine
        if eng is None:
            return self.state
        from responsibleai.data_governance.operator_recovery_control import RecoveryInProgressError

        try:
            await assert_database_restore_consistent(eng)
            self._db_authority_status = "RECONCILED"
            if (
                self._provider_error is not None
                and (
                    self._provider_error.startswith("Database restore inconsistency:")
                    or self._provider_error == "Store B recovery evidence could not be verified"
                )
                and self._provider is not None
            ):
                from responsibleai.data_governance.operator_recovery_control import (
                    assert_completed_binding,
                )

                # A fresh cross-store database check above and a completed,
                # signed, externally consumed recovery receipt are both required.
                # Reconnection by itself never clears this sticky failure.
                if assert_completed_binding(self._provider) and self._provider.verify_integrity():
                    self._provider_error = None
        except RecoveryInProgressError:
            return RestoreReadinessState.RECONCILING
        except Exception as exc:
            self._local_state = RestoreReadinessState.FAILED
            self._db_authority_status = "FAILED"
            self._provider_error = f"Database restore inconsistency: {exc}"
            from responsibleai.data_governance.operator_recovery_control import (
                record_restrictive_failure,
            )

            try:
                record_restrictive_failure()
            except Exception:
                pass
            if self._provider is not None:
                try:
                    self._provider.set_readiness_state(
                        RestoreReadinessState.FAILED, updated_by="db_consistency_check"
                    )
                except Exception:
                    pass
            return RestoreReadinessState.FAILED
        return self.state


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
        provider_error = None
        store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
            "WHITEPACT_LIFECYCLE_STORE_PATH"
        )
        if store_b_path:
            try:
                provider = DurableLifecycleStateProvider(store_b_path)
            except Exception as exc:
                provider = None
                provider_error = str(exc)
        elif is_restore_pending_default():
            provider_error = "Recovery startup requires durable Store B provider (WHITEPACT_STORE_B_PATH missing)"
        elif is_production_environment():
            provider_error = "Production environment requires durable Store B provider (WHITEPACT_STORE_B_PATH missing)"

        gate = RestoreReadinessGate(initial_state=initial, provider=provider)
        if provider_error is not None:
            gate._provider_error = provider_error
            gate._local_state = RestoreReadinessState.FAILED
        _GLOBAL_RESTORE_GATE = gate
    return _GLOBAL_RESTORE_GATE


def bind_restore_gate_engine(engine: DatabaseEngine) -> None:
    """Bind application database engine to the global restore gate."""
    gate = get_restore_readiness_gate()
    gate._db_engine = engine


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


async def assert_current_restore_readiness_admitted() -> None:
    await get_restore_readiness_gate().assert_current_traffic_admitted()


async def assert_database_restore_consistent(engine: DatabaseEngine) -> None:
    """Assert that the database does not contain an unreconciled or failed recovery state."""
    from responsibleai.db.containment_repository import ContainmentRepository
    from responsibleai.isolation.durable_intent import process_generation

    await ContainmentRepository(engine).assert_admitted(owner_generation=process_generation())
    from responsibleai.data_governance.operator_recovery_control import (
        assert_database_recovery_binding,
    )

    await assert_database_recovery_binding(engine)
    from responsibleai.isolation.mode import unisolated_execution_allowed

    if not unisolated_execution_allowed():
        import asyncio

        from responsibleai.isolation.container_backend import DockerContainerBackend
        from responsibleai.isolation.durable_intent import (
            assert_runtime_inventory,
            daemon_identity,
        )

        if engine.raw.dialect.name != "postgresql":
            raise RestoreQuarantineError(
                "Hosted runtime readiness requires the durable PostgreSQL journal"
            )
        backend = DockerContainerBackend()
        identity = await asyncio.to_thread(daemon_identity, backend.docker_cmd)
        await assert_runtime_inventory(ContainmentRepository(engine), backend.docker_cmd, identity)
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(restore_reconciliation_records.c.status)
                .order_by(restore_reconciliation_records.c.restored_at.desc())
                .limit(1)
            )
        ).fetchone()
        if row and row[0] not in ("RECONCILED", None):
            raise RestoreQuarantineError(
                f"Database restore state is {row[0]}; authority reconciliation is required."
            )


def evaluate_startup_authority(
    gate: RestoreReadinessGate | None = None,
    engine: DatabaseEngine | None = None,
    db_status: str | None = None,
) -> StartupAuthorityEvaluation:
    """Evaluate and categorize system startup authority into NORMAL, RECOVERY, or UNCERTAIN."""
    g = gate or get_restore_readiness_gate()
    if g.provider_error is not None:
        return StartupAuthorityEvaluation(
            mode=StartupAuthorityMode.UNCERTAIN,
            readiness_state=RestoreReadinessState.FAILED,
            reason=f"Store B provider initialization failure: {g.provider_error}",
            durable_provider_present=False,
            integrity_verified=False,
        )

    recorded_db_status = db_status or getattr(g, "_db_authority_status", None)
    if recorded_db_status in ("CONTAINMENT_PENDING", "FAILED", "RECONCILING"):
        return StartupAuthorityEvaluation(
            mode=StartupAuthorityMode.RECOVERY,
            readiness_state=RestoreReadinessState.FAILED,
            reason=f"Database persists unreconciled recovery event: status={recorded_db_status}",
            durable_provider_present=g.provider is not None,
            integrity_verified=False,
        )

    provider = g.provider
    if provider is not None:
        try:
            if hasattr(provider, "verify_integrity") and not provider.verify_integrity():
                return StartupAuthorityEvaluation(
                    mode=StartupAuthorityMode.UNCERTAIN,
                    readiness_state=RestoreReadinessState.FAILED,
                    reason="Store B cryptographic integrity verification failed",
                    durable_provider_present=True,
                    integrity_verified=False,
                )
            shared = provider.get_readiness_state()
            if shared in (
                RestoreReadinessState.FAILED,
                RestoreReadinessState.RECONCILING,
                RestoreReadinessState.RESTORE_PENDING,
            ):
                return StartupAuthorityEvaluation(
                    mode=StartupAuthorityMode.RECOVERY,
                    readiness_state=shared,
                    reason=f"Durable Store B persists {shared.value} recovery state",
                    durable_provider_present=True,
                    integrity_verified=True,
                )
            if shared == RestoreReadinessState.READY:
                return StartupAuthorityEvaluation(
                    mode=StartupAuthorityMode.NORMAL,
                    readiness_state=RestoreReadinessState.READY,
                    reason="Durable Store B confirms READY admission",
                    durable_provider_present=True,
                    integrity_verified=True,
                )
        except Exception as exc:
            return StartupAuthorityEvaluation(
                mode=StartupAuthorityMode.UNCERTAIN,
                readiness_state=RestoreReadinessState.FAILED,
                reason=f"Store B provider communication error: {exc}",
                durable_provider_present=True,
                integrity_verified=False,
            )

    if is_production_environment() and provider is None:
        return StartupAuthorityEvaluation(
            mode=StartupAuthorityMode.UNCERTAIN,
            readiness_state=RestoreReadinessState.FAILED,
            reason="Durable Store B is required in production environment",
            durable_provider_present=False,
            integrity_verified=False,
        )

    if is_restore_pending_default():
        return StartupAuthorityEvaluation(
            mode=StartupAuthorityMode.UNCERTAIN
            if provider is None
            else StartupAuthorityMode.RECOVERY,
            readiness_state=RestoreReadinessState.FAILED
            if provider is None
            else RestoreReadinessState.RESTORE_PENDING,
            reason="Restore environment flag active without Store B"
            if provider is None
            else "Restore environment flag active",
            durable_provider_present=provider is not None,
            integrity_verified=provider is not None,
        )

    return StartupAuthorityEvaluation(
        mode=StartupAuthorityMode.NORMAL,
        readiness_state=g.state,
        reason="Normal startup with established authority",
        durable_provider_present=provider is not None,
        integrity_verified=True,
    )


async def evaluate_startup_authority_async(
    gate: RestoreReadinessGate | None = None,
    engine: DatabaseEngine | None = None,
) -> StartupAuthorityEvaluation:
    """Asynchronously evaluate startup authority including live database check."""
    g = gate or get_restore_readiness_gate()
    eng = engine or getattr(g, "_db_engine", None)
    db_status = None
    if eng is not None:
        try:
            await assert_database_restore_consistent(eng)
            db_status = "RECONCILED"
            g._db_authority_status = "RECONCILED"
        except RestoreQuarantineError as rqe:
            g._local_state = RestoreReadinessState.FAILED
            g._db_authority_status = "FAILED"
            g._provider_error = f"Database restore inconsistency: {rqe}"
            return StartupAuthorityEvaluation(
                mode=StartupAuthorityMode.RECOVERY,
                readiness_state=RestoreReadinessState.FAILED,
                reason=f"Database persists unreconciled recovery event: {rqe}",
                durable_provider_present=g.provider is not None,
                integrity_verified=False,
            )
        except Exception as exc:
            g._local_state = RestoreReadinessState.FAILED
            g._db_authority_status = "FAILED"
            g._provider_error = f"Database authority verification error: {exc}"
            return StartupAuthorityEvaluation(
                mode=StartupAuthorityMode.UNCERTAIN,
                readiness_state=RestoreReadinessState.FAILED,
                reason=f"Database authority verification error: {exc}",
                durable_provider_present=g.provider is not None,
                integrity_verified=False,
            )
    return evaluate_startup_authority(gate=g, engine=eng, db_status=db_status)


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
        # Production authority is server policy, never a caller opt-out flag.
        must_require_durable = is_prod or require_durable is True

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

    async def reconcile_post_restore(
        self,
        reconciled_by: str,
        *,
        fail_closed_on_unestablished_tenant: bool = True,
    ) -> RestoreReconciliationReport:
        """Reconcile restored organizations against current lifecycle state from Store B.

        Fail-Closed Reconciliation Protocol:
        1. Atomically marks gate as RECONCILING.
        2. Validates cryptographic integrity and availability of Store B.
        3. Identifies all tombstones from Store B, Store A, and detects any Store A organization
           lacking an authoritative Store B lifecycle record (orphaned / unverified).
        4. For every tombstoned tenant:
           - Quarantines organization with supported governance_status="DISABLED" and suffixed name.
           - Executes a strictly ordered topological FK purge of active operational authority.
           - Forensically revokes root authority records and consent proofs.
           - Elevates revocation epochs to fence in-flight tokens.
        5. For every unestablished/missing tenant:
           - Preserves quarantine (governance_status="DISABLED") WITHOUT deleting customer authority data.
           - Fails closed into FAILED state pending a controlled operator decision.
        6. Synchronizes Store B revocation floors across all active verified tenants in Store A,
           enforcing strict sibling tenant isolation.
        7. Synchronizes tombstone ledger in Store A from Store B.
        8. Triggers in-flight execution containment against InFlightExecutionRegistry and
           verifies zero active or unresolved executions. Never swallows containment errors.
        9. Advances gate to READY only upon complete error-free transaction commit and confirmed
           containment. On any error, gate transitions to FAILED and fails closed.
        """
        now = _now()
        from responsibleai.data_governance.operator_recovery_control import assert_engine_authorized

        assert_engine_authorized(self._engine, self._provider)
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
                from responsibleai.data_governance.operator_recovery_control import (
                    begin_locked_reconciliation_inputs,
                )

                await begin_locked_reconciliation_inputs(conn, self._provider)
                # Also include any tombstones already in Store A
                tombstones_a = (await conn.execute(select(tenant_tombstones))).fetchall()
                for t in tombstones_a:
                    tombstoned_ids.add(t.org_id)

                # Fetch all organizations present in restored database Store A
                store_a_orgs = (await conn.execute(select(organizations))).fetchall()
                store_a_org_map = {org.id: org for org in store_a_orgs}

                # Restored ID-only foreign keys do not establish tenant ownership.
                # Reject malformed graphs before any purge, revocation or quarantine
                # mutation, rather than following a tenant's reference into another
                # tenant's authority records. The enclosing transaction rolls back.
                foreign_approval = await conn.scalar(
                    select(runtime_execution_requests.c.request_id)
                    .join(
                        governance_approvals,
                        runtime_execution_requests.c.approval_id == governance_approvals.c.id,
                    )
                    .where(
                        runtime_execution_requests.c.organization_id
                        != governance_approvals.c.org_id
                    )
                    .limit(1)
                )
                if foreign_approval is not None:
                    raise RestoreReconciliationError(
                        "Cross-tenant approval reference in restored authority graph."
                    )
                for child in (
                    runtime_worker_leases,
                    runtime_execution_dispatch_outbox,
                    runtime_execution_attempts,
                    governance_execution_authorizations,
                ):
                    foreign_child = await conn.scalar(
                        select(child.c.request_id)
                        .join(
                            runtime_execution_requests,
                            child.c.request_id == runtime_execution_requests.c.request_id,
                        )
                        .where(
                            child.c.organization_id != runtime_execution_requests.c.organization_id
                        )
                        .limit(1)
                    )
                    if foreign_child is not None:
                        raise RestoreReconciliationError(
                            "Cross-tenant runtime reference in restored authority graph."
                        )

                # Evaluate Store B lifecycle completeness for EVERY tenant in Store A
                # An active organization in Store A without an authoritative Store B lifecycle record
                # is unverified and cannot be trusted.
                missing_store_b_ids: list[str] = []
                for org_id in store_a_org_map:
                    if org_id not in tombstoned_ids and self._provider.get_state(org_id) is None:
                        missing_store_b_ids.append(org_id)

                # 4A. Quarantine unestablished/missing Store B tenants WITHOUT deleting customer authority data
                if missing_store_b_ids:
                    missing_orgs = (
                        await conn.execute(
                            select(organizations).where(organizations.c.id.in_(missing_store_b_ids))
                        )
                    ).fetchall()
                    for org in missing_orgs:
                        new_name = (
                            f"{org.name}-RESTORE_QUARANTINED"
                            if "-RESTORE_QUARANTINED" not in org.name
                            else org.name
                        )
                        await conn.execute(
                            update(organizations)
                            .where(organizations.c.id == org.id)
                            .values(
                                name=new_name,
                                governance_status=GovernanceStatus.DISABLED.value,
                                deactivated_at=now,
                            )
                        )
                        quarantined_orgs.append(org.id)

                # 4B. Confirmed Tombstoned Tenants: Quarantine and Execute Strictly Ordered Topological FK Purge
                if tombstoned_ids:
                    matching_orgs = (
                        await conn.execute(
                            select(organizations).where(organizations.c.id.in_(tombstoned_ids))
                        )
                    ).fetchall()

                    for org in matching_orgs:
                        org_id = org.id
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
                        if org_id not in quarantined_orgs:
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
                                    runtime_execution_dispatch_outbox.c.request_id.in_(
                                        tenant_req_ids
                                    )
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
                                    governance_approvals.c.org_id == org_id,
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
                                    governance_approval_votes.c.approval_id.in_(
                                        unreferenced_app_ids
                                    )
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
                            delete(governance_policies).where(
                                governance_policies.c.org_id == org_id
                            )
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

                # Synchronize revocation floors from Store B for all active verified records
                # Sibling isolation: query ONLY records for organizations that exist in Store A
                for org_id in store_a_org_map:
                    if org_id in quarantined_orgs:
                        continue
                    b_rec = self._provider.get_state(org_id)
                    if b_rec is None:
                        continue
                    floor = max(b_rec.security_epoch, b_rec.revocation_floor)
                    if floor <= 0:
                        continue

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
                        if ep < floor:
                            await conn.execute(
                                update(governance_revocation_epochs)
                                .where(
                                    governance_revocation_epochs.c.organization_id == org_id,
                                    governance_revocation_epochs.c.scope == sc,
                                )
                                .values(epoch=floor, updated_at=now)
                            )
                            fenced_epochs += 1

                    for required_scope in ("governance", "tenant_global"):
                        if required_scope not in known_scopes:
                            await conn.execute(
                                insert(governance_revocation_epochs).values(
                                    organization_id=org_id,
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
                                    governance_revocation_epochs.c.organization_id == org_id,
                                    governance_revocation_epochs.c.scope == required_scope,
                                )
                                .values(epoch=floor, updated_at=now)
                            )
                            fenced_epochs += 1

                # Check Store B completeness:
                # If Store B has records or fail_closed_on_unestablished_tenant is True:
                # Any organization in Store A lacking an authoritative Store B lifecycle record
                # represents an integrity gap. We quarantine it and fail closed.
                store_b_has_records = (
                    len(self._provider.list_all()) > 0 or len(self._provider.list_tombstones()) > 0
                )
                has_missing_b_failure = bool(
                    missing_store_b_ids
                    and (store_b_has_records or fail_closed_on_unestablished_tenant)
                )
                status = "FAILED" if has_missing_b_failure else "CONTAINMENT_PENDING"
                details = {
                    "quarantined_orgs": quarantined_orgs,
                    "missing_store_b_tenants": missing_store_b_ids,
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

                from responsibleai.data_governance.operator_recovery_control import (
                    capture_reconciled_authority,
                )

                await capture_reconciled_authority(conn, self._provider)

            from responsibleai.data_governance.operator_recovery_control import (
                release_reconciliation_store_lock,
            )

            release_reconciliation_store_lock()
            # Check if Store B completeness failure occurred:
            # Quarantine is committed in DB above; now transition gate to FAILED and raise.
            if has_missing_b_failure:
                self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                raise RestoreReconciliationError(
                    f"Restored database contains {len(missing_store_b_ids)} organization(s) "
                    f"lacking authoritative Store B lifecycle record: {missing_store_b_ids}. "
                    f"Tenants quarantined in Store A; admission blocked."
                )

            # In-flight execution containment
            # CRITICAL SECURITY INVARIANT: Recovery must NEVER enter READY while required
            # containment evidence is missing, unconfirmed, or failing.
            try:
                from responsibleai.isolation.in_flight import InFlightExecutionRegistry

                registry = InFlightExecutionRegistry.get_instance()
            except Exception as reg_exc:
                self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                raise RestoreReconciliationError(
                    f"InFlightExecutionRegistry unavailable or corrupted: {reg_exc}"
                ) from reg_exc

            # Active restored tenants being considered for admission
            active_restored_orgs = [
                org_id for org_id in store_a_org_map if org_id not in quarantined_orgs
            ]

            # Check if any legacy unresolved containment exists for active restored tenants or unattributed executions
            unattributed_entries = [
                rec
                for rec in registry.get_unresolved_containments()
                if not rec.organization_id or rec.organization_id == "unknown"
            ]
            unattributed_count = len(unattributed_entries) + registry.count_unresolved("unknown")
            active_unresolved = (
                sum(registry.count_unresolved(org_id) for org_id in active_restored_orgs)
                + unattributed_count
            )
            if active_unresolved > 0:
                unresolved_details = [
                    rec
                    for org_id in active_restored_orgs
                    for rec in registry.get_unresolved(org_id)
                ] + [e.__dict__ for e in unattributed_entries]
                self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                raise RestoreReconciliationError(
                    f"Pre-existing unresolved containment detected for active/unattributed tenants "
                    f"({active_unresolved} executions). "
                    f"Cannot admit traffic while legacy executions remain uncontained: {unresolved_details}"
                )

            # 1. Terminate in-flight executions for all quarantined organizations
            for q_org in quarantined_orgs:
                try:
                    await registry.terminate_in_flight(organization_id=q_org)
                except Exception as term_exc:
                    self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                    raise RestoreReconciliationError(
                        f"In-flight containment termination failed for quarantined tenant '{q_org}': {term_exc}"
                    ) from term_exc

                # Strict containment verification: must have zero active AND zero unresolved executions
                active_for_org = registry.count_active(q_org)
                unresolved_for_org = registry.count_unresolved(q_org)
                unresolved_records = registry.get_unresolved(q_org)
                if active_for_org > 0 or unresolved_for_org > 0 or len(unresolved_records) > 0:
                    self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                    raise RestoreReconciliationError(
                        f"Containment unconfirmed for quarantined tenant '{q_org}': "
                        f"{active_for_org} active executions, {unresolved_for_org} unresolved executions. "
                        f"Diagnostics: {unresolved_records}"
                    )

            # 2. Reconcile epochs across all active tenants against the database
            try:
                await registry.reconcile_epochs(self._engine)
            except Exception as rec_exc:
                self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                raise RestoreReconciliationError(
                    f"Revocation epoch reconciliation failed during post-restore containment: {rec_exc}"
                ) from rec_exc

            # 3. Final containment verification: ensure zero active or unresolved executions across ALL tenants in Store A or unattributed
            final_active = sum(registry.count_active(org_id) for org_id in store_a_org_map)
            final_unresolved = sum(registry.count_unresolved(org_id) for org_id in store_a_org_map)
            final_unattributed = sum(
                1
                for rec in registry.get_unresolved_containments()
                if not rec.organization_id or rec.organization_id == "unknown"
            ) + registry.count_unresolved("unknown")

            from responsibleai.isolation.in_flight import _check_remote_worker_active

            alive_remote_workers = [
                r
                for r in _check_remote_worker_active(None)
                if r.get("organization_id") in store_a_org_map
            ]

            if (
                final_active > 0
                or final_unresolved > 0
                or final_unattributed > 0
                or len(alive_remote_workers) > 0
            ):
                unresolved_all = (
                    [rec for org_id in store_a_org_map for rec in registry.get_unresolved(org_id)]
                    + [
                        e.__dict__
                        for e in registry.get_unresolved_containments()
                        if not e.organization_id or e.organization_id == "unknown"
                    ]
                    + alive_remote_workers
                )
                self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
                raise RestoreReconciliationError(
                    f"Post-reconciliation containment unconfirmed: "
                    f"{final_active} active, {final_unresolved} unresolved, "
                    f"{final_unattributed} unattributed, {len(alive_remote_workers)} remote alive workers. "
                    f"Diagnostics: {unresolved_all}"
                )

            # Update database record to RECONCILED now that containment is verified
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(restore_reconciliation_records)
                    .where(restore_reconciliation_records.c.id == rec_id)
                    .values(
                        status="RECONCILED",
                        details_json=json.dumps(details),
                    )
                )

            # All containment proven, confirmed, and verified -> advance gate to READY
            from responsibleai.data_governance.operator_recovery_control import (
                verify_engine_final_state,
            )

            await verify_engine_final_state(self._engine, self._provider)
            self._gate.set_state(RestoreReadinessState.READY, updated_by=reconciled_by)

            return RestoreReconciliationReport(
                id=rec_id,
                restored_at=now,
                status="RECONCILED",
                tombstones_detected=len(tombstoned_ids),
                tenants_quarantined=len(quarantined_orgs),
                reconciled_by=reconciled_by,
                details=details,
            )

        except Exception as exc:
            # On failure, transition gate to FAILED so traffic remains blocked
            from responsibleai.data_governance.operator_recovery_control import (
                release_reconciliation_store_lock,
            )

            release_reconciliation_store_lock()
            self._gate.set_state(RestoreReadinessState.FAILED, updated_by=reconciled_by)
            try:
                async with self._engine.raw.begin() as conn:
                    res = await conn.execute(
                        update(restore_reconciliation_records)
                        .where(restore_reconciliation_records.c.id == rec_id)
                        .values(
                            status="FAILED",
                            details_json=json.dumps({"error": str(exc), "stage": "failed"}),
                        )
                    )
                    if (res.rowcount or 0) == 0:
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
        finally:
            from responsibleai.data_governance.operator_recovery_control import (
                release_reconciliation_store_lock,
            )

            release_reconciliation_store_lock()


BackupResurrectionDefense = RestoreReconciliationEngine
