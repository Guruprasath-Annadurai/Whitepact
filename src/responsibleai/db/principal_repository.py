"""Async repository for persisted Verified Principal authentications
(``verified_principals``) -- see ``governance/principal.py`` for what
constructs a ``PrincipalClaim`` in the first place. Append-only audit
log of verification events, not a security gate itself -- by the time a
``PrincipalClaim`` exists, the credential has already been fully
cryptographically verified (see ``auth/verifiable_credential.py``);
this table exists so "who authenticated as a verified principal, and
when" is queryable after the fact, the same audit role
``OutcomeRepository`` plays for execution outcomes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select

from responsibleai.db.engine import DatabaseEngine, verified_principals
from responsibleai.governance.principal import PrincipalClaim


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> PrincipalClaim:
    return PrincipalClaim(
        verification_id=row.id,
        principal_id=row.principal_id,
        org_id=row.org_id,
        issuer=row.issuer,
        credential_type=row.credential_type,
        holder_kind=row.holder_kind,
        claim_keys=tuple(row.claim_keys.split(",")) if row.claim_keys else (),
        verified_at=datetime.fromisoformat(row.verified_at),
    )


class PrincipalRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def record(self, claim: PrincipalClaim) -> PrincipalClaim:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(verified_principals).values(
                    id=claim.verification_id,
                    principal_id=claim.principal_id,
                    org_id=claim.org_id,
                    issuer=claim.issuer,
                    credential_type=claim.credential_type,
                    holder_kind=claim.holder_kind,
                    claim_keys=",".join(claim.claim_keys),
                    verified_at=claim.verified_at.isoformat(),
                )
            )
        return claim

    async def get_recent_for_principal(
        self, principal_id: str, limit: int = 20
    ) -> list[PrincipalClaim]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(verified_principals)
                    .where(verified_principals.c.principal_id == principal_id)
                    .order_by(verified_principals.c.verified_at.desc())
                    .limit(limit)
                )
            ).fetchall()
        return [_row_to_record(row) for row in rows]
