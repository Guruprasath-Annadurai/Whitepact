"""Phase 2 (Enterprise Neural directive) — cryptographic foundation +
key management. See `docs/enterprise-neural/02_PHASE2_DESIGN.md` for
the full design rationale.

This package is the seam between "how data gets encrypted" and "where
keys come from" — every call site (`db/encryption.py`,
`webhooks/manager.py`, `auth/saml.py`) is meant to depend on the
`KeyProvider` Protocol here, never directly on a concrete provider, so
a future `AWSKMSKeyProvider`/`VaultTransitKeyProvider` (documented, not
built this phase — see the design doc Sec 3.8) can be substituted
without touching business logic. This is Step 1 of the design doc's
implementation sequencing (Sec 7): the package, the Protocol, one
production-capable provider (`LocalEnvelopeKeyProvider`), and the
envelope format. Wiring existing call sites onto it, and the
`crypto_keys` migration for a persistent `WrappedKeyStore`, are later
steps.
"""

from __future__ import annotations

from responsibleai.governance.crypto.envelope import (
    decode_envelope,
    decrypt_envelope,
    encode_envelope,
    encrypt_envelope,
)
from responsibleai.governance.crypto.local_envelope import (
    InMemoryWrappedKeyStore,
    LocalEnvelopeKeyProvider,
)
from responsibleai.governance.crypto.provider import KeyProvider, WrappedKeyStore
from responsibleai.governance.crypto.types import (
    CryptoError,
    DecryptionError,
    EnvelopeFormatError,
    KeyId,
    KeyNotFoundError,
    KeyPurpose,
    KeyRevokedError,
    KeyStatus,
    WrappedKeyRecord,
)

__all__ = [
    "CryptoError",
    "DecryptionError",
    "EnvelopeFormatError",
    "InMemoryWrappedKeyStore",
    "KeyId",
    "KeyNotFoundError",
    "KeyProvider",
    "KeyPurpose",
    "KeyRevokedError",
    "KeyStatus",
    "LocalEnvelopeKeyProvider",
    "WrappedKeyRecord",
    "WrappedKeyStore",
    "decode_envelope",
    "decrypt_envelope",
    "encode_envelope",
    "encrypt_envelope",
]
