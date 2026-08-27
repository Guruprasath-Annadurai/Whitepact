"""Phase 2 (Enterprise Neural directive) — the one production-capable
`KeyProvider` this phase builds. See
`docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.8-3.9: real envelope
encryption (a root key-encrypting-key wraps per-purpose/tenant
data-encrypting-keys via AES-256-GCM), self-hosted rather than calling
out to a managed HSM — not "an env var dictionary pretending to be a
KMS." A future `AWSKMSKeyProvider`/`VaultTransitKeyProvider` implements
the same `KeyProvider` Protocol without any call site changing.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from responsibleai.governance.crypto.types import (
    DecryptionError,
    KeyId,
    KeyNotFoundError,
    KeyPurpose,
    KeyRevokedError,
    KeyStatus,
    WrappedKeyRecord,
)

_ROOT_KEY_SIZE_BYTES = 32  # AES-256
_DEK_SIZE_BYTES = 32
_NONCE_SIZE_BYTES = 12


class InMemoryWrappedKeyStore:
    """Non-persistent `WrappedKeyStore` — the dev/test default, and the
    fallback until a DB-backed `crypto_keys`-table store lands (a later
    slice of Phase 2). Never use this for a real deployment: every
    process restart loses all key state, silently generating fresh DEKs
    on next use — which makes anything encrypted under the lost DEK
    permanently undecryptable. Documented, not hidden.
    """

    def __init__(self) -> None:
        self._records: dict[str, WrappedKeyRecord] = {}

    async def get(self, key_id: KeyId) -> WrappedKeyRecord | None:
        return self._records.get(key_id.to_string())

    async def get_current(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> WrappedKeyRecord | None:
        candidates = [
            record
            for record in self._records.values()
            if record.key_id.purpose == purpose
            and record.key_id.tenant_id == tenant_id
            and record.key_id.environment == environment
            and record.status == KeyStatus.ACTIVE
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda record: record.key_id.version)

    async def get_max_version(
        self, purpose: KeyPurpose, tenant_id: str | None, environment: str
    ) -> int:
        versions = [
            record.key_id.version
            for record in self._records.values()
            if record.key_id.purpose == purpose
            and record.key_id.tenant_id == tenant_id
            and record.key_id.environment == environment
        ]
        return max(versions, default=0)

    async def put(self, record: WrappedKeyRecord) -> None:
        self._records[record.key_id.to_string()] = record

    async def set_status(self, key_id: KeyId, status: KeyStatus) -> None:
        existing = self._records.get(key_id.to_string())
        if existing is None:
            raise KeyNotFoundError(key_id)
        self._records[key_id.to_string()] = WrappedKeyRecord(
            key_id=existing.key_id, wrapped_dek=existing.wrapped_dek, status=status
        )


def _derive_kek(
    root_key: bytes, purpose: KeyPurpose, tenant_id: str | None, environment: str
) -> bytes:
    """HKDF-derive a per-purpose/tenant/environment KEK from the root
    key — the root key itself never wraps a DEK directly, so a
    compromised derived KEK for one purpose/tenant doesn't expose the
    root key or any other purpose/tenant's KEK (HKDF's one-way
    property)."""
    info = f"whitepact-kek:{environment}:{purpose.value}:{tenant_id or '-'}".encode()
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info)
    return hkdf.derive(root_key)


class LocalEnvelopeKeyProvider:
    """See module docstring. `root_key` must be exactly 32 bytes (AES-256)
    — generate one with `os.urandom(32)` or an equivalent CSPRNG, held
    per the same custody guidance `compliance/KEY_MANAGEMENT.md` already
    gives for today's field-encryption key."""

    def __init__(
        self,
        root_key: bytes,
        environment: str,
        store: InMemoryWrappedKeyStore | None = None,
    ) -> None:
        if len(root_key) != _ROOT_KEY_SIZE_BYTES:
            raise ValueError(
                f"root_key must be exactly {_ROOT_KEY_SIZE_BYTES} bytes "
                f"(AES-256), got {len(root_key)}"
            )
        if not environment:
            raise ValueError("environment must be non-empty")
        self._root_key = root_key
        self._environment = environment
        self._store = store if store is not None else InMemoryWrappedKeyStore()

    def _kek(self, purpose: KeyPurpose, tenant_id: str | None) -> bytes:
        return _derive_kek(self._root_key, purpose, tenant_id, self._environment)

    def _wrap(self, kek: bytes, dek: bytes, key_id: KeyId) -> bytes:
        nonce = os.urandom(_NONCE_SIZE_BYTES)
        ciphertext = AESGCM(kek).encrypt(nonce, dek, key_id.to_aad())
        return nonce + ciphertext

    def _unwrap(self, kek: bytes, wrapped: bytes, key_id: KeyId) -> bytes:
        if len(wrapped) < _NONCE_SIZE_BYTES:
            raise DecryptionError("Wrapped key material is too short to contain a nonce")
        nonce, ciphertext = wrapped[:_NONCE_SIZE_BYTES], wrapped[_NONCE_SIZE_BYTES:]
        try:
            return AESGCM(kek).decrypt(nonce, ciphertext, key_id.to_aad())
        except InvalidTag as exc:
            raise DecryptionError(
                "Failed to unwrap key material — corrupted ciphertext, "
                "tampered metadata, or wrong key"
            ) from exc

    async def get_encryption_key(
        self, purpose: KeyPurpose, tenant_id: str | None
    ) -> tuple[KeyId, bytes]:
        current = await self._store.get_current(purpose, tenant_id, self._environment)
        if current is not None:
            kek = self._kek(purpose, tenant_id)
            dek = self._unwrap(kek, current.wrapped_dek, current.key_id)
            return current.key_id, dek
        # No ACTIVE record -- but a retired/revoked one may already
        # occupy version 1 (e.g. `retire()`/`revoke()` called directly,
        # not via `rotate()`). Base the next version on the max across
        # *every* status, never hardcode 1, or a fresh key here would
        # silently overwrite that record's wrapped DEK under the same
        # KeyId, destroying it.
        max_version = await self._store.get_max_version(purpose, tenant_id, self._environment)
        return await self._generate(purpose, tenant_id, version=max_version + 1)

    async def get_decryption_key(self, key_id: KeyId) -> bytes:
        if key_id.environment != self._environment:
            # Reported identically to "key doesn't exist" -- see
            # KeyNotFoundError's own docstring for why.
            raise KeyNotFoundError(key_id)
        record = await self._store.get(key_id)
        if record is None:
            raise KeyNotFoundError(key_id)
        if record.status == KeyStatus.REVOKED:
            raise KeyRevokedError(key_id)
        kek = self._kek(key_id.purpose, key_id.tenant_id)
        return self._unwrap(kek, record.wrapped_dek, key_id)

    async def rotate(self, purpose: KeyPurpose, tenant_id: str | None) -> KeyId:
        current = await self._store.get_current(purpose, tenant_id, self._environment)
        # Same reasoning as get_encryption_key's fallback: base the new
        # version on the max across every status, not just the current
        # ACTIVE record's version, or rotating after a direct
        # retire()/revoke() (with no ACTIVE record left) would collide
        # with and overwrite an existing retired/revoked version.
        max_version = await self._store.get_max_version(purpose, tenant_id, self._environment)
        new_key_id, _ = await self._generate(purpose, tenant_id, version=max_version + 1)
        if current is not None:
            await self._store.set_status(current.key_id, KeyStatus.RETIRED)
        return new_key_id

    async def revoke(self, key_id: KeyId) -> None:
        await self._store.set_status(key_id, KeyStatus.REVOKED)

    async def retire(self, key_id: KeyId) -> None:
        await self._store.set_status(key_id, KeyStatus.RETIRED)

    async def _generate(
        self, purpose: KeyPurpose, tenant_id: str | None, version: int
    ) -> tuple[KeyId, bytes]:
        key_id = KeyId(
            purpose=purpose,
            tenant_id=tenant_id,
            version=version,
            environment=self._environment,
        )
        dek = os.urandom(_DEK_SIZE_BYTES)
        kek = self._kek(purpose, tenant_id)
        wrapped = self._wrap(kek, dek, key_id)
        await self._store.put(
            WrappedKeyRecord(key_id=key_id, wrapped_dek=wrapped, status=KeyStatus.ACTIVE)
        )
        return key_id, dek
