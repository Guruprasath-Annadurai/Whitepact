"""Async repositories for Enterprise Neural Phase 4 Step 2 — the
per-category consent ledger and the Neural Vault index. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md` Sec 6-7.

`NeuralVaultRepository` stores metadata/references about captured
`NeuralPayload`s, never their raw N0/N1/N2 content by default — see
`governance/neural/types.py`'s `NeuralVaultEntry` docstring.

**Latest version wins** for consent, the same resolution
`AuthorityPassportRepository`/`DelegationRepository` already use: a new
grant or revocation doesn't delete or overwrite an older record (both
persist as an audit trail), but only the most recent, still-active
record for a given (subject, category) is what governs a policy
decision (`governance/neural/policy.py::evaluate_neural_data_flow`).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    governance_neural_consent,
    governance_neural_vault_index,
)
from responsibleai.governance.neural import (
    ConsentCategory,
    ConsentRecord,
    ConsentStatus,
    NeuralDataClass,
    NeuralVaultEntry,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _consent_row_to_record(row: Any) -> ConsentRecord:
    return ConsentRecord(
        consent_id=row.consent_id,
        subject_id=row.subject_id,
        organization_id=row.organization_id,
        category=ConsentCategory(row.category),
        status=ConsentStatus(row.status),
        version=row.version,
        granted_at=datetime.fromisoformat(row.granted_at),
        revoked_at=datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
    )


def _vault_row_to_entry(row: Any) -> NeuralVaultEntry:
    return NeuralVaultEntry(
        entry_id=row.entry_id,
        subject_id=row.subject_id,
        session_id=row.session_id,
        data_class=NeuralDataClass(row.data_class),
        captured_at=datetime.fromisoformat(row.captured_at),
        device_reference=row.device_reference,
        retention_expires_at=(
            datetime.fromisoformat(row.retention_expires_at) if row.retention_expires_at else None
        ),
        deleted_at=datetime.fromisoformat(row.deleted_at) if row.deleted_at else None,
        encrypted_sync_copy=row.encrypted_sync_copy,
    )


class NeuralVaultEntryNotFoundError(Exception):
    pass


class NeuralConsentRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def grant(self, record: ConsentRecord) -> ConsentRecord:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                governance_neural_consent.insert().values(
                    consent_id=record.consent_id,
                    subject_id=record.subject_id,
                    organization_id=record.organization_id,
                    category=record.category.value,
                    status=record.status.value,
                    version=record.version,
                    granted_at=record.granted_at.isoformat(),
                    revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
                )
            )
        return record

    async def list_for_subject(
        self, subject_id: str, category: ConsentCategory | None = None
    ) -> list[ConsentRecord]:
        stmt = select(governance_neural_consent).where(
            governance_neural_consent.c.subject_id == subject_id
        )
        if category is not None:
            stmt = stmt.where(governance_neural_consent.c.category == category.value)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [_consent_row_to_record(r) for r in rows]

    async def get_active(self, subject_id: str, category: ConsentCategory) -> ConsentRecord | None:
        """The latest-version record for (subject_id, category), or
        `None` if none exists — mirrors
        `governance/neural/policy.py::evaluate_neural_data_flow`'s own
        "latest version wins" resolution, but this method returns the
        record itself (active or not) rather than a policy decision;
        callers wanting the fail-closed ALLOW/DENY should still go
        through `evaluate_neural_data_flow`."""
        records = await self.list_for_subject(subject_id, category)
        if not records:
            return None
        return max(records, key=lambda r: r.version)

    async def revoke(
        self, subject_id: str, organization_id: str | None, category: ConsentCategory
    ) -> ConsentRecord:
        """Inserts a new REVOKED record at the next version — never
        mutates an existing GRANTED record, preserving the audit trail
        (same pattern as `grant`)."""
        current = await self.get_active(subject_id, category)
        next_version = current.version + 1 if current is not None else 1
        record = ConsentRecord(
            consent_id=f"{subject_id}:{category.value}:v{next_version}",
            subject_id=subject_id,
            organization_id=organization_id,
            category=category,
            status=ConsentStatus.REVOKED,
            version=next_version,
            granted_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        return await self.grant(record)


class NeuralVaultRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create_entry(self, entry: NeuralVaultEntry) -> NeuralVaultEntry:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                governance_neural_vault_index.insert().values(
                    entry_id=entry.entry_id,
                    subject_id=entry.subject_id,
                    session_id=entry.session_id,
                    data_class=entry.data_class.value,
                    device_reference=entry.device_reference,
                    captured_at=entry.captured_at.isoformat(),
                    retention_expires_at=(
                        entry.retention_expires_at.isoformat()
                        if entry.retention_expires_at
                        else None
                    ),
                    deleted_at=entry.deleted_at.isoformat() if entry.deleted_at else None,
                    encrypted_sync_copy=entry.encrypted_sync_copy,
                )
            )
        return entry

    async def get(self, entry_id: str) -> NeuralVaultEntry | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_neural_vault_index).where(
                        governance_neural_vault_index.c.entry_id == entry_id
                    )
                )
            ).fetchone()
        return _vault_row_to_entry(row) if row is not None else None

    async def list_for_subject(
        self, subject_id: str, *, include_deleted: bool = False
    ) -> list[NeuralVaultEntry]:
        stmt = select(governance_neural_vault_index).where(
            governance_neural_vault_index.c.subject_id == subject_id
        )
        if not include_deleted:
            stmt = stmt.where(governance_neural_vault_index.c.deleted_at.is_(None))
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [_vault_row_to_entry(r) for r in rows]

    async def soft_delete(self, entry_id: str) -> NeuralVaultEntry:
        """Marks the entry deleted (sets `deleted_at`) — never a hard
        delete, so the Vault index retains a record that a subject
        exercised their delete right, without the raw content this
        table never stored in the first place. See design doc Sec 8's
        explicit "deletion semantics must be explicit" requirement:
        this removes the Vault index reference (and, if present, the
        opt-in encrypted sync copy field is left in place -- explicitly
        NOT purged in this method, since a hard-delete/purge operation
        is a distinct, separately-scoped capability, not silently
        folded into a "soft delete" call that only marks the record)."""
        existing = await self.get(entry_id)
        if existing is None:
            raise NeuralVaultEntryNotFoundError(entry_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(governance_neural_vault_index)
                .where(governance_neural_vault_index.c.entry_id == entry_id)
                .values(deleted_at=_now())
            )
        updated = await self.get(entry_id)
        assert updated is not None
        return updated
