"""Security Remediation Gap 1 — production activation for the Phase 2
crypto foundation. See
`docs/enterprise-neural/REMEDIATION_GAP1_CRYPTO_ACTIVATION.md`.

Before this module existed, `governance/crypto/`'s envelope-encryption
`KeyProvider` architecture was fully built and tested but never
constructed or activated by any application-startup path --
`configure_field_encryption_key()`/`configure_session_signing_key()`
had zero call sites outside their own definitions and test files. This
module is that missing wiring, gated behind an explicit, fail-closed
`Settings.enterprise_mode` flag rather than silently activating (which
would risk making a deployment think it configured nothing when
`enterprise_mode` defaults to `False`).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from responsibleai.auth.saml import configure_session_signing_key
from responsibleai.db.crypto_key_repository import CryptoKeyRepository
from responsibleai.db.encryption import configure_field_encryption_key
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider
from responsibleai.governance.crypto.types import KeyPurpose

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings
    from responsibleai.db.engine import DatabaseEngine

_logger = logging.getLogger("responsibleai.crypto_activation")


class CryptoActivationError(RuntimeError):
    """Raised when `enterprise_mode=true` but the crypto foundation
    cannot be activated -- the caller must let this propagate and abort
    startup, never catch-and-continue with encryption silently
    disabled."""


def _decode_root_key(raw: str) -> bytes:
    try:
        key = bytes.fromhex(raw)
    except ValueError as exc:
        raise CryptoActivationError(
            "crypto_root_key is not valid hex. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        ) from exc
    if len(key) != 32:
        raise CryptoActivationError(
            f"crypto_root_key must decode to exactly 32 bytes (AES-256), "
            f"got {len(key)}. Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return key


async def activate_production_crypto(settings: Settings, engine: DatabaseEngine) -> None:
    """Call once at application startup, before the first request is
    served. No-op when `settings.enterprise_mode` is falsy -- this is
    the only thing that keeps development/self-hosted behavior
    completely unchanged; there is no separate "dev mode" flag to
    forget, only the absence of the enterprise one.

    Raises `CryptoActivationError` (fail-closed) if `enterprise_mode`
    is true but `crypto_root_key` is missing or malformed. Never
    catches its own exceptions -- the caller (application startup) must
    let this abort the process, not degrade to plaintext.
    """
    if not settings.enterprise_mode:
        _logger.info("crypto_activation_skipped: enterprise_mode is false")
        return

    root_key_hex = settings.crypto_root_key
    if not root_key_hex:
        raise CryptoActivationError(
            "enterprise_mode=true requires crypto_root_key to be set. "
            "Generate one with: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    root_key = _decode_root_key(root_key_hex)

    store = CryptoKeyRepository(engine)
    provider = LocalEnvelopeKeyProvider(root_key=root_key, environment="production", store=store)

    field_key_id, field_dek = await provider.get_encryption_key(
        KeyPurpose.FIELD_ENCRYPTION, tenant_id=None
    )
    configure_field_encryption_key(field_key_id, field_dek)
    _logger.info("crypto_activation_field_encryption_active key_id=%s", field_key_id.to_string())

    session_key_id, session_dek = await provider.get_encryption_key(
        KeyPurpose.SESSION_SIGNING, tenant_id=None
    )
    configure_session_signing_key(session_key_id, session_dek)
    _logger.info("crypto_activation_session_signing_active key_id=%s", session_key_id.to_string())
