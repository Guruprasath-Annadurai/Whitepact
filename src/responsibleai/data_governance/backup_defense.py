# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Backup Resurrection Defense and Restore Reconciliation Engine for WhitePact Phase 5.

Guarantees:
- Persistent Tombstone Ledger tracking all deleted organizations and generation IDs.
- Restore Quarantine Guard: Automatically detects and quarantines resurrected organizations post-restore.
- Immediate Revocation: Purges restored sessions, API keys, and credentials of deleted tenants.
- Fail-Closed: Blocks operational traffic if restore reconciliation fails or detects unresolved state.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    iam_api_key_lineage,
    iam_sessions,
    org_api_keys,
    organizations,
    restore_reconciliation_records,
    tenant_tombstones,
    web_sessions,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RestoreReconciliationError(Exception):
    """Raised when restore reconciliation fails."""


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
    """Audits restored database state against the tombstone ledger."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._ledger = TombstoneLedger(engine)

    async def reconcile_post_restore(self, reconciled_by: str) -> RestoreReconciliationReport:
        """Reconcile all restored organizations against tombstones.

        If a tombstoned tenant exists in restored organizations, force quarantine
        and revoke all restored credentials.
        """
        now = _now()
        rec_id = str(uuid.uuid4())
        quarantined_orgs: list[str] = []
        revoked_sessions = 0
        revoked_keys = 0

        try:
            async with self._engine.raw.begin() as conn:
                # 1. Fetch all tombstones
                tombstones = (await conn.execute(select(tenant_tombstones))).fetchall()
                tombstoned_ids = {t.org_id for t in tombstones}

                if tombstoned_ids:
                    # 2. Find restored orgs matching tombstone IDs
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
                            .values(
                                name=f"{org.name}-RESTORE_QUARANTINED",
                                        )
                        )
                        quarantined_orgs.append(org.id)

                        # Revoke restored sessions
                        r_s = await conn.execute(delete(web_sessions).where(web_sessions.c.org_id == org.id))
                        r_is = await conn.execute(delete(iam_sessions).where(iam_sessions.c.org_id == org.id))
                        revoked_sessions += (r_s.rowcount or 0) + (r_is.rowcount or 0)

                        # Revoke restored API keys
                        r_k = await conn.execute(delete(org_api_keys).where(org_api_keys.c.org_id == org.id))
                        r_ik = await conn.execute(delete(iam_api_key_lineage).where(iam_api_key_lineage.c.org_id == org.id))
                        revoked_keys += (r_k.rowcount or 0) + (r_ik.rowcount or 0)

                status = "RECONCILED"
                details = {
                    "quarantined_orgs": quarantined_orgs,
                    "revoked_sessions": revoked_sessions,
                    "revoked_keys": revoked_keys,
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
            # On failure, record FAILED and re-raise
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
            raise RestoreReconciliationError(f"Restore reconciliation aborted: {exc}") from exc


BackupResurrectionDefense = RestoreReconciliationEngine
