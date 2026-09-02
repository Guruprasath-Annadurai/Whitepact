"""Async repository for `ConsentProof` (Heart Phase H4,
governance/consent_proof.py) -- Heart Production Integration Phase 3.

Pure persistence: `create()`, `get()`, `revoke()`. Same "storage only,
no validation logic" discipline as `root_authority_repository.py` --
`consent_proof.validate_consent_proof()` is unchanged and stays free
of any dependency on this table.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    governance_consent_proofs,
    governance_root_authority_records,
)
from responsibleai.governance.consent_proof import ConsentMethod, ConsentProof


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> ConsentProof:
    return ConsentProof(
        consent_id=row.consent_id,
        subject_id=row.subject_id,
        consenting_root_id=row.consenting_root_id,
        grantee_id=row.grantee_id,
        scope_description=row.scope_description,
        purpose=row.purpose,
        consent_method=ConsentMethod(row.consent_method),
        evidence_refs=tuple(json.loads(row.evidence_refs)),
        consented_at=datetime.fromisoformat(row.consented_at),
        not_before=datetime.fromisoformat(row.not_before) if row.not_before else None,
        expires_at=datetime.fromisoformat(row.expires_at) if row.expires_at else None,
        revoked_at=datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
        canonical_digest=row.canonical_digest,
        allowed_action_types=tuple(json.loads(row.allowed_action_types)),
        allowed_targets=tuple(json.loads(row.allowed_targets)),
    )


class ConsentProofNotFoundError(Exception):
    pass


class ConsentProofRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(self, proof: ConsentProof) -> ConsentProof:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_consent_proofs).values(
                    consent_id=proof.consent_id,
                    subject_id=proof.subject_id,
                    consenting_root_id=proof.consenting_root_id,
                    grantee_id=proof.grantee_id,
                    scope_description=proof.scope_description,
                    purpose=proof.purpose,
                    consent_method=proof.consent_method.value,
                    evidence_refs=json.dumps(list(proof.evidence_refs)),
                    consented_at=proof.consented_at.isoformat(),
                    not_before=proof.not_before.isoformat() if proof.not_before else None,
                    expires_at=proof.expires_at.isoformat() if proof.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                    canonical_digest=proof.canonical_digest,
                    allowed_action_types=json.dumps(list(proof.allowed_action_types)),
                    allowed_targets=json.dumps(list(proof.allowed_targets)),
                )
            )
        return proof

    async def get(self, consent_id: str) -> ConsentProof | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_consent_proofs).where(
                        governance_consent_proofs.c.consent_id == consent_id
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def get_latest_for_grantee(
        self, grantee_id: str, *, organization_id: str
    ) -> ConsentProof | None:
        """Latest non-tenant-crossing consent proof for a grantee.

        Joins to `governance_root_authority_records` on
        `consenting_root_id == root_id` because `ConsentProof` carries
        no `organization_id` of its own -- its tenant is defined
        entirely by which root vouches for it. This is the JOIN that
        makes cross-org consent structurally impossible to return:
        a proof whose consenting root belongs to a different
        organization is excluded by the WHERE clause, not merely
        filtered after the fact.
        """
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_consent_proofs)
                    .join(
                        governance_root_authority_records,
                        governance_consent_proofs.c.consenting_root_id
                        == governance_root_authority_records.c.root_id,
                    )
                    .where(
                        governance_consent_proofs.c.grantee_id == grantee_id,
                        governance_root_authority_records.c.organization_id == organization_id,
                    )
                    .order_by(governance_consent_proofs.c.consented_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def revoke(
        self, consent_id: str, *, revoked_by: str, reason: str | None = None
    ) -> ConsentProof:
        existing = await self.get(consent_id)
        if existing is None:
            raise ConsentProofNotFoundError(consent_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(governance_consent_proofs)
                .where(governance_consent_proofs.c.consent_id == consent_id)
                .values(revoked_at=_now(), revoked_by=revoked_by, revoke_reason=reason)
            )
        updated = await self.get(consent_id)
        assert updated is not None
        return updated
