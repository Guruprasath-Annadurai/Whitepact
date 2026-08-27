"""Async, DB-backed `WrappedKeyStore` for Enterprise Neural Phase 2
Step 2 (`governance/crypto/`) — see
`docs/enterprise-neural/02_PHASE2_DESIGN.md`.

Persists wrapped DEKs (never plaintext key material — see
`governance/crypto/local_envelope.py`'s own docstring) across process
restarts, replacing `InMemoryWrappedKeyStore` for any real deployment.
Structurally satisfies the `WrappedKeyStore` Protocol
(`governance/crypto/provider.py`) — not a subclass; this project
already prefers structural typing for these small persistence-seam
interfaces (see e.g. how `governance/crypto/local_envelope.py`'s own
`InMemoryWrappedKeyStore` isn't declared as a subclass either).

`key_id` (the canonical `KeyId.to_string()` encoding) is the table's
primary key, so a concurrent write racing to generate the same
purpose/tenant/environment/version hits the database's own uniqueness
constraint and raises `KeyVersionConflictError` — turning the "two
callers rotate at once" race into a hard, typed error instead of one
caller's write silently overwriting the other's wrapped DEK (the exact
class of bug `LocalEnvelopeKeyProvider`'s in-memory store's dict-based
`put()` cannot detect — see Step 1's Phase Report residual risks).
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, governance_crypto_keys
from responsibleai.governance.crypto import (
    KeyId,
    KeyNotFoundError,
    KeyPurpose,
    KeyStatus,
    KeyVersionConflictError,
    WrappedKeyRecord,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _tenant_column_value(tenant_id: str | None) -> str:
    # "" is the same "no tenant" wire encoding KeyId.to_string() itself
    # already uses (governance/crypto/types.py) -- reused here rather
    # than a nullable column, since a composite lookup index benefits
    # from a non-null value and PRIMARY KEY columns cannot be NULL in
    # standard SQL regardless.
    return tenant_id if tenant_id is not None else ""


def _row_to_record(row: Any) -> WrappedKeyRecord:
    key_id = KeyId(
        purpose=KeyPurpose(row.purpose),
        tenant_id=row.tenant_id or None,
        version=row.version,
        environment=row.environment,
    )
    return WrappedKeyRecord(
        key_id=key_id,
        wrapped_dek=base64.urlsafe_b64decode(row.wrapped_dek.encode("ascii")),
        status=KeyStatus(row.status),
    )


class CryptoKeyRepository:
    """DB-backed `WrappedKeyStore`. See
    `governance/crypto/provider.py`'s `WrappedKeyStore` Protocol for
    the exact contract this implements."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get(self, key_id: KeyId) -> WrappedKeyRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_crypto_keys).where(
                        governance_crypto_keys.c.key_id == key_id.to_string()
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_current(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> WrappedKeyRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_crypto_keys)
                    .where(
                        governance_crypto_keys.c.purpose == purpose.value,
                        governance_crypto_keys.c.tenant_id == _tenant_column_value(tenant_id),
                        governance_crypto_keys.c.environment == environment,
                        governance_crypto_keys.c.status == KeyStatus.ACTIVE.value,
                    )
                    .order_by(governance_crypto_keys.c.version.desc())
                    .limit(1)
                )
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_max_version(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> int:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_crypto_keys)
                    .where(
                        governance_crypto_keys.c.purpose == purpose.value,
                        governance_crypto_keys.c.tenant_id == _tenant_column_value(tenant_id),
                        governance_crypto_keys.c.environment == environment,
                    )
                    .order_by(governance_crypto_keys.c.version.desc())
                    .limit(1)
                )
            ).fetchone()
        return row.version if row is not None else 0

    async def put(self, record: WrappedKeyRecord) -> None:
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(governance_crypto_keys).values(
                        key_id=record.key_id.to_string(),
                        purpose=record.key_id.purpose.value,
                        tenant_id=_tenant_column_value(record.key_id.tenant_id),
                        environment=record.key_id.environment,
                        version=record.key_id.version,
                        wrapped_dek=base64.urlsafe_b64encode(record.wrapped_dek).decode("ascii"),
                        status=record.status.value,
                        created_at=_now(),
                    )
                )
        except IntegrityError as exc:
            raise KeyVersionConflictError(record.key_id) from exc

    async def set_status(self, key_id: KeyId, status: KeyStatus) -> None:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(governance_crypto_keys)
                .where(governance_crypto_keys.c.key_id == key_id.to_string())
                .values(status=status.value)
            )
        if result.rowcount == 0:
            raise KeyNotFoundError(key_id)
