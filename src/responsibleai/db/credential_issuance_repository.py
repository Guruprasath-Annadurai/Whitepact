"""Async repository for the JIT Credential Broker's audit trail
(``credential_issuances``) -- see ``governance/jit_credential.py`` for
what issues a ``JITCredential`` in the first place. This repository
never stores a credential's actual token value, only metadata about
when it was issued, for what, and whether it was ultimately consumed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import insert, update

from responsibleai.db.engine import DatabaseEngine, credential_issuances

if TYPE_CHECKING:
    from responsibleai.governance.jit_credential import JITCredential

_logger = logging.getLogger("responsibleai.db.credential_issuance_repository")


def _now() -> str:
    return datetime.now(UTC).isoformat()


class CredentialIssuanceRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def record_issued(
        self,
        credential: JITCredential,
        *,
        action_id: str,
        agent_id: str | None,
    ) -> None:
        """Best-effort, fail-open audit write -- same contract
        ``mcp/upstream_dispatch.py``'s own evidence recording follows:
        a broken audit sink must not block a governed call that
        governance already decided to allow. Logged loudly on failure
        rather than silently swallowed."""
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(credential_issuances).values(
                        credential_id=credential.credential_id,
                        authorization_id=credential.authorization_id,
                        action_id=action_id,
                        server_id=credential.server_id,
                        org_id=credential.org_id,
                        agent_id=agent_id,
                        had_credential=1 if credential.token is not None else 0,
                        issued_at=credential.issued_at.isoformat(),
                        expires_at=credential.expires_at.isoformat(),
                    )
                )
        except Exception:
            _logger.exception(
                "credential_issuance_audit_write_failed credential_id=%s server_id=%s",
                credential.credential_id,
                credential.server_id,
            )

    async def record_consumed(self, credential_id: str) -> None:
        """Same fail-open contract as `record_issued()` -- a failure
        here means the issuance row (which already proves the
        credential was minted) simply never gets its consumed_at
        filled in, not that the call is blocked."""
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(credential_issuances)
                    .where(credential_issuances.c.credential_id == credential_id)
                    .values(consumed_at=_now())
                )
        except Exception:
            _logger.exception(
                "credential_issuance_consumed_write_failed credential_id=%s", credential_id
            )
