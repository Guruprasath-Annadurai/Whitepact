"""Phase 2 (Enterprise Neural directive) — the `KeyProvider` abstraction
every call site is meant to depend on, never a concrete provider
directly. This is the seam a future `AWSKMSKeyProvider`/
`VaultTransitKeyProvider` plugs into without touching business logic —
see `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.7-3.8.

`WrappedKeyStore` is the separate persistence seam: Step 1 (this) ships
only `InMemoryWrappedKeyStore` (non-persistent, dev/test); a real
`crypto_keys`-table-backed store is Step 2's `docs/heart-production/`-
style migration, added without changing this Protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from responsibleai.governance.crypto.types import (
        KeyId,
        KeyPurpose,
        KeyStatus,
        WrappedKeyRecord,
    )


class KeyProvider(Protocol):
    """Fail-closed by contract: every method raises rather than falling
    back to plaintext or a default key on any failure (missing key,
    revoked key, backend unavailable) — see design doc Sec 3.16."""

    async def get_encryption_key(
        self, purpose: KeyPurpose, tenant_id: str | None
    ) -> tuple[KeyId, bytes]:
        """Return the current (highest active version) key for
        encrypting new data under *purpose*/*tenant_id* — generating one
        on first use. Must never return a retired or revoked key."""
        ...

    async def get_decryption_key(self, key_id: KeyId) -> bytes:
        """Resolve the raw key bytes for *key_id* — used to decrypt
        data previously encrypted under it. Raises `KeyNotFoundError` if
        no such key exists, `KeyRevokedError` if it has been revoked.
        A retired (not revoked) key is still resolvable, by design —
        see `KeyStatus`."""
        ...

    async def rotate(self, purpose: KeyPurpose, tenant_id: str | None) -> KeyId:
        """Generate a new key version for *purpose*/*tenant_id*, retire
        the previous active version (if any), and return the new
        `KeyId`. Idempotent in effect but not in result: calling twice
        produces two new versions, not the same one."""
        ...

    async def revoke(self, key_id: KeyId) -> None:
        """Mark *key_id* revoked. Unlike `retire`, a revoked key can
        never decrypt data again, even data encrypted under it before
        revocation — use only when a key is suspected compromised."""
        ...

    async def retire(self, key_id: KeyId) -> None:
        """Mark *key_id* retired — it is no longer returned by
        `get_encryption_key` for new writes, but remains valid for
        `get_decryption_key` so already-encrypted data stays readable."""
        ...


class WrappedKeyStore(Protocol):
    """Persistence seam for wrapped DEKs."""

    async def get(self, key_id: KeyId) -> WrappedKeyRecord | None: ...

    async def get_current(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> WrappedKeyRecord | None:
        """Return the highest-version `ACTIVE` record for this
        purpose/tenant/environment, or `None` if none exists yet."""
        ...

    async def get_max_version(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> int:
        """Return the highest version number that exists for this
        purpose/tenant/environment across *every* status (active,
        retired, revoked) — 0 if none exists yet. Callers generating a
        new key version must base it on this, never on
        `get_current()` alone: `get_current()` only sees `ACTIVE`
        records, so a naive "no active record -> start at 1" fallback
        would silently collide with (and overwrite) an existing
        retired or revoked version 1 the first time a key is retired
        or revoked outside of `rotate()`."""
        ...

    async def put(self, record: WrappedKeyRecord) -> None: ...

    async def set_status(self, key_id: KeyId, status: KeyStatus) -> None:
        """Raises `KeyNotFoundError` if *key_id* has no existing record."""
        ...
