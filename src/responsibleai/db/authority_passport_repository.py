"""Async repository for Authority Passports (Authority Everywhere
Phase 5) -- persists `AuthorityPassport`s issued via
`POST /api/governance/authority-passports`, resolves the currently
active one per principal, and handles revocation.

**Latest declared, still-active passport wins**, the same resolution
`DelegationRepository.get_latest_delegation()` and
`IntentContractRepository.get_active_for_agent()` already use: a new
issuance doesn't delete or overwrite an older one (both persist as an
audit trail), but only the most recently issued, still-active row is
what `get_active_for_principal()` returns.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, governance_authority_passports
from responsibleai.governance.authority_passport import AuthorityPassport


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> AuthorityPassport:
    return AuthorityPassport(
        passport_id=row.id,
        organization_id=row.org_id,
        principal_id=row.principal_id,
        source=row.source,
        source_id=row.source_id,
        granted_action_types=tuple(json.loads(row.granted_action_types)),
        max_value_usd=row.max_value_usd,
        allowed_targets=tuple(json.loads(row.allowed_targets)) if row.allowed_targets else None,
        denied_targets=tuple(json.loads(row.denied_targets)) if row.denied_targets else None,
        require_approval_for=(
            tuple(json.loads(row.require_approval_for)) if row.require_approval_for else ()
        ),
        max_delegation_depth=row.max_delegation_depth,
        issued_at=datetime.fromisoformat(row.issued_at),
        expires_at=datetime.fromisoformat(row.expires_at) if row.expires_at else None,
        revoked_at=datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
    )


class AuthorityPassportNotFoundError(Exception):
    pass


class AuthorityPassportRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def issue(self, passport: AuthorityPassport) -> AuthorityPassport:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_authority_passports).values(
                    id=passport.passport_id,
                    org_id=passport.organization_id,
                    principal_id=passport.principal_id,
                    source=passport.source,
                    source_id=passport.source_id,
                    granted_action_types=json.dumps(list(passport.granted_action_types)),
                    max_value_usd=passport.max_value_usd,
                    allowed_targets=(
                        json.dumps(list(passport.allowed_targets))
                        if passport.allowed_targets
                        else None
                    ),
                    denied_targets=(
                        json.dumps(list(passport.denied_targets))
                        if passport.denied_targets
                        else None
                    ),
                    require_approval_for=(
                        json.dumps(list(passport.require_approval_for))
                        if passport.require_approval_for
                        else None
                    ),
                    max_delegation_depth=passport.max_delegation_depth,
                    issued_at=passport.issued_at.isoformat(),
                    expires_at=passport.expires_at.isoformat() if passport.expires_at else None,
                    revoked_at=None,
                    revoked_by=None,
                    revoke_reason=None,
                )
            )
        return passport

    async def get(self, org_id: str, passport_id: str) -> AuthorityPassport | None:
        """Fetch a passport only from the caller's tenant."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_authority_passports).where(
                        governance_authority_passports.c.org_id == org_id,
                        governance_authority_passports.c.id == passport_id,
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def get_active_for_principal(
        self, org_id: str, principal_id: str
    ) -> AuthorityPassport | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_authority_passports)
                    .where(
                        governance_authority_passports.c.org_id == org_id,
                        governance_authority_passports.c.principal_id == principal_id,
                    )
                    .order_by(governance_authority_passports.c.issued_at.desc())
                    .limit(1)
                )
            ).fetchone()
        if row is None:
            return None
        passport = _row_to_record(row)
        return passport if passport.is_active() else None

    async def revoke(
        self,
        org_id: str,
        passport_id: str,
        *,
        revoked_by: str,
        reason: str | None = None,
    ) -> AuthorityPassport:
        existing = await self.get(org_id, passport_id)
        if existing is None:
            raise AuthorityPassportNotFoundError(passport_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(governance_authority_passports)
                .where(
                    governance_authority_passports.c.org_id == org_id,
                    governance_authority_passports.c.id == passport_id,
                )
                .values(revoked_at=_now(), revoked_by=revoked_by, revoke_reason=reason)
            )
        updated = await self.get(org_id, passport_id)
        assert updated is not None
        return updated
