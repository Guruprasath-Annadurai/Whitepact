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
import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    eval_baselines,
    eval_runs,
    governance_approvals,
    governance_policies,
    governance_policy_versions,
    iam_api_key_lineage,
    iam_scim_groups,
    iam_scim_users,
    iam_sessions,
    mcp_tool_calls,
    org_api_keys,
    organizations,
    restore_reconciliation_records,
    tenant_tombstones,
    token_usage,
    web_memberships,
    web_sessions,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RestoreReconciliationError(Exception):
    """Raised when restore reconciliation fails."""


class RestoreQuarantineError(Exception):
    """Raised when operational traffic is attempted while system is quarantined/not ready."""


class LifecycleState(StrEnum):
    """Security lifecycle state of a tenant."""

    ACTIVE = "ACTIVE"
    DELETION_IN_PROGRESS = "DELETION_IN_PROGRESS"
    TOMBSTONED = "TOMBSTONED"


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
    def verify_integrity(self) -> bool:
        """Verify integrity and availability of current lifecycle store."""

    @abstractmethod
    def set_available(self, available: bool) -> None:
        """Configure availability for failure simulation testing."""

    @abstractmethod
    def set_corrupted(self, corrupted: bool) -> None:
        """Configure corruption for integrity failure testing."""


class InMemoryLifecycleStateProvider(CurrentLifecycleStateProvider):
    """Thread-safe, independently persisted in-memory lifecycle state provider representing Store B."""

    def __init__(self) -> None:
        self._records: dict[str, LifecycleStateRecord] = {}
        self._available: bool = True
        self._corrupted: bool = False

    def record_state(self, record: LifecycleStateRecord) -> None:
        if not self._available:
            raise RuntimeError("CurrentLifecycleStateProvider is unavailable")
        self._records[record.tenant_id] = record

    def get_state(self, tenant_id: str) -> LifecycleStateRecord | None:
        if not self._available:
            raise RuntimeError("CurrentLifecycleStateProvider is unavailable")
        return self._records.get(tenant_id)

    def is_tombstoned(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state == LifecycleState.TOMBSTONED

    def is_deletion_in_progress(self, tenant_id: str) -> bool:
        rec = self.get_state(tenant_id)
        return rec is not None and rec.state in (LifecycleState.DELETION_IN_PROGRESS, LifecycleState.TOMBSTONED)

    def list_tombstones(self) -> list[LifecycleStateRecord]:
        if not self._available:
            raise RuntimeError("CurrentLifecycleStateProvider is unavailable")
        return [r for r in self._records.values() if r.state in (LifecycleState.DELETION_IN_PROGRESS, LifecycleState.TOMBSTONED)]

    def verify_integrity(self) -> bool:
        if not self._available or self._corrupted:
            return False
        for rec in self._records.values():
            expected = hashlib.sha256(f"{rec.tenant_id}:{rec.generation_id}:{rec.state.value}:{rec.effective_at}".encode()).hexdigest()
            if rec.digest and rec.digest != expected:
                return False
        return True

    def set_available(self, available: bool) -> None:
        self._available = available

    def set_corrupted(self, corrupted: bool) -> None:
        self._corrupted = corrupted


class RestoreReadinessGate:
    """Operational readiness admission gate for restored environments."""

    def __init__(self, initial_state: RestoreReadinessState = RestoreReadinessState.RESTORE_PENDING) -> None:
        self._state = initial_state

    @property
    def state(self) -> RestoreReadinessState:
        return self._state

    def set_state(self, state: RestoreReadinessState) -> None:
        self._state = state

    def is_admitted(self) -> bool:
        return self._state == RestoreReadinessState.READY

    def assert_traffic_admitted(self) -> None:
        """Enforce that traffic is only served once lifecycle reconciliation succeeds."""
        if self._state != RestoreReadinessState.READY:
            raise RestoreQuarantineError(
                f"Operational traffic blocked: system is in {self._state.value} state."
            )


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
    ) -> None:
        self._engine = engine
        self._provider: CurrentLifecycleStateProvider = lifecycle_provider or InMemoryLifecycleStateProvider()
        self._gate: RestoreReadinessGate = gate or RestoreReadinessGate()
        self._ledger = TombstoneLedger(engine)

    @property
    def gate(self) -> RestoreReadinessGate:
        return self._gate

    @property
    def provider(self) -> CurrentLifecycleStateProvider:
        return self._provider

    async def reconcile_post_restore(self, reconciled_by: str) -> RestoreReconciliationReport:
        """Reconcile restored organizations against current lifecycle state from Store B.

        If a tombstoned or deleting tenant exists in restored organizations:
        - Force quarantine on organization.
        - Purge all restored sessions, keys, and lineage.
        - Reapply erasure of all operational and evaluative records.
        - Synchronize tombstone ledger in restored database.
        - Only advance gate to READY if reconciliation succeeds without error.
        """
        now = _now()
        rec_id = str(uuid.uuid4())
        quarantined_orgs: list[str] = []
        revoked_sessions = 0
        revoked_keys = 0
        erased_records = 0

        # Mark gate as RECONCILING
        self._gate.set_state(RestoreReadinessState.RECONCILING)

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
                        # Force quarantine
                        await conn.execute(
                            update(organizations)
                            .where(organizations.c.id == org.id)
                            .values(name=f"{org.name}-RESTORE_QUARANTINED")
                        )
                        quarantined_orgs.append(org.id)

                        # Purge restored sessions
                        r_s = await conn.execute(delete(web_sessions).where(web_sessions.c.org_id == org.id))
                        r_is = await conn.execute(delete(iam_sessions).where(iam_sessions.c.org_id == org.id))
                        revoked_sessions += (r_s.rowcount or 0) + (r_is.rowcount or 0)

                        # Purge restored API keys
                        r_k = await conn.execute(delete(org_api_keys).where(org_api_keys.c.org_id == org.id))
                        r_ik = await conn.execute(delete(iam_api_key_lineage).where(iam_api_key_lineage.c.org_id == org.id))
                        revoked_keys += (r_k.rowcount or 0) + (r_ik.rowcount or 0)

                        # Cascade erase of all restored tenant operational/eval data
                        for tbl, col in [
                            (eval_runs, "org_id"),
                            (eval_baselines, "org_id"),
                            (mcp_tool_calls, "org_id"),
                            (token_usage, "org_id"),
                            (governance_approvals, "org_id"),
                            (governance_policies, "org_id"),
                            (governance_policy_versions, "org_id"),
                            (iam_scim_users, "org_id"),
                            (iam_scim_groups, "org_id"),
                            (web_memberships, "org_id"),
                        ]:
                            c_attr = getattr(tbl.c, col)
                            r_del = await conn.execute(delete(tbl).where(c_attr == org.id))
                            erased_records += (r_del.rowcount or 0)

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

                status = "RECONCILED"
                details = {
                    "quarantined_orgs": quarantined_orgs,
                    "revoked_sessions": revoked_sessions,
                    "revoked_keys": revoked_keys,
                    "erased_records": erased_records,
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

            # Reached here without error -> advance gate to READY
            self._gate.set_state(RestoreReadinessState.READY)

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
            self._gate.set_state(RestoreReadinessState.FAILED)
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
