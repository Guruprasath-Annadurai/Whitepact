"""Async repository for `RootAuthorityRecord` (Heart Phase H3,
governance/root_authority.py) -- Heart Production Integration Phase 3.

Pure persistence: `create()`, `get()`, `revoke()`. This module does not
resolve chains, validate anything, or decide what makes a root
legitimate -- that stays `root_authority.validate_root_chain()`'s job,
unchanged. A future `RootResolver` (Phase 5, the Authority Resolver)
can be built by wrapping `get()`, but building that resolver is
explicitly out of this phase's scope, matching the same "ship storage
only" discipline `authority_passport_repository.py` established for
Authority Passports.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, governance_root_authority_records
from responsibleai.governance.root_authority import RootAuthorityRecord, RootType


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> RootAuthorityRecord:
    return RootAuthorityRecord(
        root_id=row.root_id,
        subject_id=row.subject_id,
        root_type=RootType(row.root_type),
        organization_id=row.organization_id,
        issuer=row.issuer,
        verification_method=row.verification_method,
        authority_source=row.authority_source,
        jurisdiction=row.jurisdiction,
        evidence_refs=tuple(json.loads(row.evidence_refs)),
        issued_at=datetime.fromisoformat(row.issued_at),
        not_before=datetime.fromisoformat(row.not_before) if row.not_before else None,
        expires_at=datetime.fromisoformat(row.expires_at) if row.expires_at else None,
        revoked_at=datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
        canonical_digest=row.canonical_digest,
    )


class RootAuthorityRecordNotFoundError(Exception):
    pass


class RootAuthorityRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(self, record: RootAuthorityRecord) -> RootAuthorityRecord:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_root_authority_records).values(
                    root_id=record.root_id,
                    subject_id=record.subject_id,
                    root_type=record.root_type.value,
                    organization_id=record.organization_id,
                    issuer=record.issuer,
                    verification_method=record.verification_method,
                    authority_source=record.authority_source,
                    jurisdiction=record.jurisdiction,
                    evidence_refs=json.dumps(list(record.evidence_refs)),
                    issued_at=record.issued_at.isoformat(),
                    not_before=record.not_before.isoformat() if record.not_before else None,
                    expires_at=record.expires_at.isoformat() if record.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=record.canonical_digest,
                )
            )
        return record

    async def get(self, root_id: str) -> RootAuthorityRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_root_authority_records).where(
                        governance_root_authority_records.c.root_id == root_id
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def revoke(
        self, root_id: str, *, revoked_by: str, reason: str | None = None
    ) -> RootAuthorityRecord:
        existing = await self.get(root_id)
        if existing is None:
            raise RootAuthorityRecordNotFoundError(root_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(governance_root_authority_records)
                .where(governance_root_authority_records.c.root_id == root_id)
                .values(revoked_at=_now(), revoked_by=revoked_by, revoke_reason=reason)
            )
        updated = await self.get(root_id)
        assert updated is not None
        return updated
