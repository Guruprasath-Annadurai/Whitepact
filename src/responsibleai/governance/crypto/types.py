"""Phase 2 (Enterprise Neural directive) — key hierarchy vocabulary.

See `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.1-3.3 for the
full design rationale. `KeyId` is the identifier every wrapped key,
every encrypted envelope, and every audit event carries — deliberately
separate from the key *material* itself (a `KeyId` is safe to log; the
bytes it identifies never are).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class KeyPurpose(StrEnum):
    """Closed, versioned set of what a key may be used for. A DEK issued
    for one purpose must never decrypt/verify data written under
    another — enforced by binding `purpose` into every AEAD operation's
    associated data (`KeyId.to_aad()`), not left to callers to keep
    straight."""

    FIELD_ENCRYPTION = "field_encryption"
    WEBHOOK_SIGNING = "webhook_signing"
    SESSION_SIGNING = "session_signing"
    AUDIT_ANCHOR = "audit_anchor"


class KeyStatus(StrEnum):
    """`RETIRED` and `REVOKED` are deliberately distinct: a retired key
    still decrypts old data during a graceful rotation window; a
    revoked key never decrypts anything again, even data encrypted
    under it before revocation — use `REVOKED` only when a key is
    suspected compromised."""

    ACTIVE = "active"
    RETIRED = "retired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class KeyId:
    """Identifies a single key version — never the key material itself.

    `to_string()`/`from_string()` round-trip through a canonical form
    used both as AEAD associated data (`to_aad()`) and as the embedded,
    self-describing prefix of an encrypted envelope
    (`governance/crypto/envelope.py`).
    """

    purpose: KeyPurpose
    tenant_id: str | None
    version: int
    environment: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError(f"KeyId.version must be >= 1, got {self.version}")
        if not self.environment:
            raise ValueError("KeyId.environment must be non-empty")
        if ":" in self.environment or "\x00" in self.environment:
            raise ValueError("KeyId.environment must not contain ':' or NUL")
        if self.tenant_id is not None:
            # Empty string is reserved as the wire encoding of "no
            # tenant" (see to_string/from_string) -- a caller meaning
            # "no tenant" must pass None, not "". NUL is reserved as the
            # envelope format's own field separator
            # (`governance/crypto/envelope.py`); allowing it here would
            # let a crafted tenant_id corrupt envelope parsing.
            if self.tenant_id == "":
                raise ValueError("KeyId.tenant_id must be None, not an empty string")
            if ":" in self.tenant_id or "\x00" in self.tenant_id:
                raise ValueError("KeyId.tenant_id must not contain ':' or NUL")

    def to_aad(self) -> bytes:
        """Canonical bytes bound into every AEAD operation as associated
        data — tampering with any field here breaks the authentication
        tag the same as tampering with ciphertext itself."""
        return self.to_string().encode("utf-8")

    def to_string(self) -> str:
        tenant = self.tenant_id if self.tenant_id is not None else ""
        return f"{self.environment}:{self.purpose.value}:{tenant}:{self.version}"

    @classmethod
    def from_string(cls, s: str) -> KeyId:
        parts = s.split(":")
        if len(parts) != 4:
            raise ValueError(f"Malformed KeyId string: {s!r}")
        environment, purpose, tenant, version = parts
        try:
            version_int = int(version)
        except ValueError as exc:
            raise ValueError(f"Malformed KeyId string: {s!r}") from exc
        return cls(
            purpose=KeyPurpose(purpose),
            tenant_id=None if tenant == "" else tenant,
            version=version_int,
            environment=environment,
        )


@dataclass(frozen=True)
class WrappedKeyRecord:
    """A DEK, wrapped (never plaintext) under its purpose/tenant KEK,
    plus its lifecycle status. This is what a `WrappedKeyStore`
    persists — safe to write to a database or a backup, since the
    wrapped bytes are useless without the root key held separately
    (see the design doc's custody guidance)."""

    key_id: KeyId
    wrapped_dek: bytes
    status: KeyStatus


class CryptoError(Exception):
    """Base class for every error this package raises."""


class KeyNotFoundError(CryptoError):
    """No key exists for the given `KeyId` — including a `KeyId` whose
    `environment` doesn't match the resolving provider's own
    environment, which is deliberately reported identically to "key
    doesn't exist" rather than "wrong environment", to avoid leaking
    which environments a given key ID pattern might exist in."""

    def __init__(self, key_id: KeyId) -> None:
        self.key_id = key_id
        super().__init__(f"No key found for {key_id.to_string()!r}")


class KeyRevokedError(CryptoError):
    def __init__(self, key_id: KeyId) -> None:
        self.key_id = key_id
        super().__init__(f"Key {key_id.to_string()!r} is revoked and cannot be used")


class KeyVersionConflictError(CryptoError):
    """A `WrappedKeyStore.put()` was attempted for a `KeyId` that
    already has a record. A correct `KeyProvider` never triggers this
    under sequential use (it always computes the next version via
    `get_max_version()` first) — this is the DB-backed store's own
    concurrency-safety guarantee (a `UNIQUE`/primary-key constraint on
    `key_id`) turning the race "two callers rotate the same
    purpose/tenant/environment at once" into a hard, typed error
    instead of one caller's write silently overwriting the other's
    wrapped DEK."""

    def __init__(self, key_id: KeyId) -> None:
        self.key_id = key_id
        super().__init__(
            f"A key record already exists for {key_id.to_string()!r} — "
            "concurrent rotation/generation race"
        )


class EnvelopeFormatError(CryptoError):
    """An encrypted envelope is structurally malformed — truncated,
    missing its KeyId prefix, or otherwise not well-formed — as
    distinct from one that parses but fails authentication
    (`DecryptionError`)."""


class DecryptionError(CryptoError):
    """Ciphertext or its associated authenticated metadata failed AEAD
    verification — corrupted ciphertext, a tampered embedded `KeyId`,
    or a key/purpose/tenant mismatch. Deliberately does not distinguish
    *which* of these occurred: reporting the exact cause of an AEAD
    verification failure is itself an information leak (the same
    "don't build a decryption oracle" reasoning `auth/oidc.py` already
    applies to its own error messages)."""
