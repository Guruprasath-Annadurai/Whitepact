"""Tenant-scoped persistence for Heart production legitimacy inputs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    heart_consent_proofs,
    heart_purpose_bindings,
    heart_root_authorities,
)
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    ConsentProof,
    compute_consent_digest,
)
from responsibleai.governance.purpose_binding import (
    PurposeBinding,
    compute_purpose_binding_digest,
)
from responsibleai.governance.root_authority import (
    RootAuthorityRecord,
    RootType,
    compute_root_digest,
)


class HeartRecordIntegrityError(Exception):
    """A persisted Heart record no longer matches its canonical digest."""


class HeartRecordNotFoundError(Exception):
    pass


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _root_from_row(row: Any) -> RootAuthorityRecord:
    record = RootAuthorityRecord(
        root_id=row.id,
        subject_id=row.subject_id,
        root_type=RootType(row.root_type),
        organization_id=row.org_id,
        issuer=row.issuer,
        verification_method=row.verification_method,
        authority_source=row.authority_source,
        jurisdiction=row.jurisdiction,
        evidence_refs=tuple(json.loads(row.evidence_refs)),
        issued_at=datetime.fromisoformat(row.issued_at),
        not_before=_dt(row.not_before),
        expires_at=_dt(row.expires_at),
        revoked_at=_dt(row.revoked_at),
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
        canonical_digest=row.canonical_digest,
    )
    expected = compute_root_digest(
        record.root_id,
        record.root_type,
        record.subject_id,
        record.organization_id,
        record.issuer,
        record.verification_method,
        record.authority_source,
        record.jurisdiction,
        record.evidence_refs,
        record.issued_at,
        record.not_before,
        record.expires_at,
    )
    if expected != record.canonical_digest:
        raise HeartRecordIntegrityError(f"Root authority digest mismatch: {record.root_id}")
    return record


def _consent_from_row(row: Any) -> ConsentProof:
    record = ConsentProof(
        consent_id=row.id,
        subject_id=row.subject_id,
        consenting_root_id=row.consenting_root_id,
        grantee_id=row.grantee_id,
        scope_description=row.scope_description,
        purpose=row.purpose,
        consent_method=ConsentMethod(row.consent_method),
        evidence_refs=tuple(json.loads(row.evidence_refs)),
        consented_at=datetime.fromisoformat(row.consented_at),
        not_before=_dt(row.not_before),
        expires_at=_dt(row.expires_at),
        revoked_at=_dt(row.revoked_at),
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
        canonical_digest=row.canonical_digest,
    )
    expected = compute_consent_digest(
        record.consent_id,
        record.subject_id,
        record.consenting_root_id,
        record.grantee_id,
        record.scope_description,
        record.purpose,
        record.consent_method,
        record.evidence_refs,
        record.consented_at,
        record.not_before,
        record.expires_at,
    )
    if expected != record.canonical_digest:
        raise HeartRecordIntegrityError(f"Consent proof digest mismatch: {record.consent_id}")
    return record


def _binding_from_row(row: Any) -> PurposeBinding:
    record = PurposeBinding(
        binding_id=row.id,
        purpose=row.purpose,
        intent_ref=row.intent_ref,
        consent_ref=row.consent_ref,
        bound_at=datetime.fromisoformat(row.bound_at),
        canonical_digest=row.canonical_digest,
    )
    expected = compute_purpose_binding_digest(
        record.binding_id,
        record.purpose,
        record.intent_ref,
        record.consent_ref,
        record.bound_at,
    )
    if expected != record.canonical_digest:
        raise HeartRecordIntegrityError(f"Purpose binding digest mismatch: {record.binding_id}")
    return record


class RootAuthorityRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def issue(self, org_id: str, record: RootAuthorityRecord) -> RootAuthorityRecord:
        if record.organization_id != org_id:
            raise ValueError("Root authority organization does not match repository tenant")
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(heart_root_authorities).values(
                    id=record.root_id,
                    org_id=org_id,
                    subject_id=record.subject_id,
                    root_type=record.root_type.value,
                    issuer=record.issuer,
                    verification_method=record.verification_method,
                    authority_source=record.authority_source,
                    jurisdiction=record.jurisdiction,
                    evidence_refs=json.dumps(list(record.evidence_refs)),
                    issued_at=record.issued_at.isoformat(),
                    not_before=record.not_before.isoformat() if record.not_before else None,
                    expires_at=record.expires_at.isoformat() if record.expires_at else None,
                    revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
                    revoked_by=record.revoked_by,
                    revoke_reason=record.revoke_reason,
                    canonical_digest=record.canonical_digest,
                )
            )
        return record

    async def get(self, org_id: str, root_id: str) -> RootAuthorityRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(heart_root_authorities).where(
                        heart_root_authorities.c.org_id == org_id,
                        heart_root_authorities.c.id == root_id,
                    )
                )
            ).fetchone()
        return _root_from_row(row) if row else None

    async def get_latest_for_subject(
        self, org_id: str, subject_id: str
    ) -> RootAuthorityRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(heart_root_authorities)
                    .where(
                        heart_root_authorities.c.org_id == org_id,
                        heart_root_authorities.c.subject_id == subject_id,
                    )
                    .order_by(heart_root_authorities.c.issued_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _root_from_row(row) if row else None

    async def load_chain(
        self, org_id: str, record: RootAuthorityRecord
    ) -> dict[str, RootAuthorityRecord]:
        """Preload a tenant-scoped chain for Heart's synchronous resolver."""
        chain = {record.root_id: record}
        current = record
        for _ in range(32):
            if not current.authority_source or current.authority_source in chain:
                break
            parent = await self.get(org_id, current.authority_source)
            if parent is None:
                break
            chain[parent.root_id] = parent
            current = parent
        return chain

    async def revoke(
        self, org_id: str, root_id: str, *, revoked_by: str, reason: str | None = None
    ) -> RootAuthorityRecord:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(heart_root_authorities)
                .where(
                    heart_root_authorities.c.org_id == org_id,
                    heart_root_authorities.c.id == root_id,
                    heart_root_authorities.c.revoked_at.is_(None),
                )
                .values(
                    revoked_at=datetime.now(UTC).isoformat(),
                    revoked_by=revoked_by,
                    revoke_reason=reason,
                )
            )
        if result.rowcount != 1:
            raise HeartRecordNotFoundError(root_id)
        record = await self.get(org_id, root_id)
        assert record is not None
        return record


class ConsentProofRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def issue(self, org_id: str, proof: ConsentProof) -> ConsentProof:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(heart_consent_proofs).values(
                    id=proof.consent_id,
                    org_id=org_id,
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
                    revoked_at=proof.revoked_at.isoformat() if proof.revoked_at else None,
                    revoked_by=proof.revoked_by,
                    revoke_reason=proof.revoke_reason,
                    canonical_digest=proof.canonical_digest,
                )
            )
        return proof

    async def get(self, org_id: str, consent_id: str) -> ConsentProof | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(heart_consent_proofs).where(
                        heart_consent_proofs.c.org_id == org_id,
                        heart_consent_proofs.c.id == consent_id,
                    )
                )
            ).fetchone()
        return _consent_from_row(row) if row else None

    async def get_latest_for_grantee(
        self, org_id: str, grantee_id: str, purpose: str
    ) -> ConsentProof | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(heart_consent_proofs)
                    .where(
                        heart_consent_proofs.c.org_id == org_id,
                        heart_consent_proofs.c.grantee_id == grantee_id,
                        heart_consent_proofs.c.purpose == purpose,
                    )
                    .order_by(heart_consent_proofs.c.consented_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _consent_from_row(row) if row else None

    async def revoke(
        self, org_id: str, consent_id: str, *, revoked_by: str, reason: str | None = None
    ) -> ConsentProof:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(heart_consent_proofs)
                .where(
                    heart_consent_proofs.c.org_id == org_id,
                    heart_consent_proofs.c.id == consent_id,
                    heart_consent_proofs.c.revoked_at.is_(None),
                )
                .values(
                    revoked_at=datetime.now(UTC).isoformat(),
                    revoked_by=revoked_by,
                    revoke_reason=reason,
                )
            )
        if result.rowcount != 1:
            raise HeartRecordNotFoundError(consent_id)
        proof = await self.get(org_id, consent_id)
        assert proof is not None
        return proof


class PurposeBindingRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def bind(self, org_id: str, principal_id: str, binding: PurposeBinding) -> PurposeBinding:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(heart_purpose_bindings).values(
                    id=binding.binding_id,
                    org_id=org_id,
                    principal_id=principal_id,
                    purpose=binding.purpose,
                    intent_ref=binding.intent_ref,
                    consent_ref=binding.consent_ref,
                    bound_at=binding.bound_at.isoformat(),
                    canonical_digest=binding.canonical_digest,
                )
            )
        return binding

    async def get_for_refs(
        self,
        org_id: str,
        principal_id: str,
        intent_ref: str,
        consent_ref: str,
    ) -> PurposeBinding | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(heart_purpose_bindings)
                    .where(
                        heart_purpose_bindings.c.org_id == org_id,
                        heart_purpose_bindings.c.principal_id == principal_id,
                        heart_purpose_bindings.c.intent_ref == intent_ref,
                        heart_purpose_bindings.c.consent_ref == consent_ref,
                    )
                    .order_by(heart_purpose_bindings.c.bound_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _binding_from_row(row) if row else None
