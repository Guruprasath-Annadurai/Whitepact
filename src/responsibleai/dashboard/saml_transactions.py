# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable SAML AuthnRequest correlation for the dashboard ACS.

Process-local dicts cannot coordinate SP-initiated SAML across replicas.
Request IDs live in the same DatabaseEngine as the rest of identity state.
Redis is not used. Storage failure fails closed.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from responsibleai.db.engine import DatabaseEngine, dashboard_saml_transactions

logger = logging.getLogger(__name__)

SAML_REQUEST_TTL_SECONDS = 300


class SamlTransactionUnavailableError(RuntimeError):
    """Raised when SAML request state cannot be stored or consumed."""


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _hash(request_id: str) -> str:
    return hashlib.sha256(request_id.encode("utf-8")).hexdigest()


class DurableSamlAuthnStore:
    """Insert-once / consume-once SAML AuthnRequest store."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    async def remember(
        self,
        request_id: str,
        *,
        idp_entity_id: str,
        acs_url: str,
        ttl_seconds: float = SAML_REQUEST_TTL_SECONDS,
    ) -> None:
        created = _now()
        expires = created + timedelta(seconds=ttl_seconds)
        try:
            async with self.engine.raw.begin() as conn:
                await conn.execute(
                    insert(dashboard_saml_transactions).values(
                        request_id_hash=_hash(request_id),
                        idp_entity_id=idp_entity_id,
                        acs_url=acs_url,
                        status="PENDING",
                        created_at=_iso(created),
                        expires_at=_iso(expires),
                        consumed_at=None,
                    )
                )
        except IntegrityError:
            raise SamlTransactionUnavailableError("SAML request id already recorded") from None
        except SQLAlchemyError:
            logger.warning("saml_transaction_store_unavailable")
            raise SamlTransactionUnavailableError(
                "SAML request state is unavailable. Try again later."
            ) from None

    async def consume(
        self,
        request_id: str,
        *,
        idp_entity_id: str,
        acs_url: str,
    ) -> bool:
        """Atomically consume a pending, unexpired, bound request.

        Returns False for unknown, expired, already-used, or binding-mismatch
        ids (non-disclosing). Raises SamlTransactionUnavailableError on storage failure.
        """
        now = _iso()
        try:
            async with self.engine.raw.begin() as conn:
                result = await conn.execute(
                    update(dashboard_saml_transactions)
                    .where(
                        dashboard_saml_transactions.c.request_id_hash == _hash(request_id),
                        dashboard_saml_transactions.c.status == "PENDING",
                        dashboard_saml_transactions.c.consumed_at.is_(None),
                        dashboard_saml_transactions.c.expires_at > now,
                        dashboard_saml_transactions.c.idp_entity_id == idp_entity_id,
                        dashboard_saml_transactions.c.acs_url == acs_url,
                    )
                    .values(status="CONSUMED", consumed_at=now)
                )
                return int(getattr(result, "rowcount", 0) or 0) == 1
        except SQLAlchemyError:
            logger.warning("saml_transaction_consume_unavailable")
            raise SamlTransactionUnavailableError(
                "SAML request state is unavailable. Try again later."
            ) from None

    async def peek_status(self, request_id: str) -> str | None:
        try:
            async with self.engine.raw.connect() as conn:
                row = (
                    await conn.execute(
                        select(dashboard_saml_transactions.c.status).where(
                            dashboard_saml_transactions.c.request_id_hash == _hash(request_id)
                        )
                    )
                ).fetchone()
                return None if row is None else str(row.status)
        except SQLAlchemyError:
            raise SamlTransactionUnavailableError(
                "SAML request state is unavailable. Try again later."
            ) from None
