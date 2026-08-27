"""Opt-in field-level encryption for individual PII/secret columns.

Encryption at rest for the *whole database* is the deployer's
responsibility (see `ENTERPRISE_SECURITY.md`'s "Encryption at rest"
section) — disk/volume encryption, not something the application can
retrofit onto an existing Postgres/SQLite install. This module covers a
narrower, real gap: encrypting specific columns' *values* so they're
unreadable even to someone with raw table access but no application key
(a stolen backup file, a misconfigured read replica, a DBA who shouldn't
see raw IPs, names, or webhook secrets).

Columns currently using `EncryptedString` (audit via
`grep -rn EncryptedString src/responsibleai/db/engine.py`):
- `audit_log.ip_address`
- `public_incident_reports.reporter_name`, `.reporter_contact`
- `org_api_keys.mfa_secret` (TOTP seed — see `auth/mfa.py`)
- `webhook_configs.secret` (HMAC signing secret)

**Two co-existing encryption schemes, one column type** (Enterprise
Neural Phase 2 Step 3, `docs/enterprise-neural/02_PHASE2_DESIGN.md`
Sec 3.14):

1. **Legacy**: `RAI_FIELD_ENCRYPTION_KEY`-based Fernet, described below
   under "Legacy scheme". Unchanged behavior, still fully supported —
   no deployer is forced to migrate.
2. **New**: `governance/crypto/`'s `KeyProvider` abstraction
   (`KeyPurpose.FIELD_ENCRYPTION`, `tenant_id=None` — field encryption
   has always been one application-global key, not per-tenant, so this
   wiring preserves that scope rather than silently introducing tenant
   separation `EncryptedString` has no row context to enforce anyway),
   activated by calling `configure_field_encryption_key()` once.

**Format detection on read, via an explicit prefix, not a structural
guess.** An earlier version of this module tried to distinguish the two
schemes by decoding the stored base64 and inspecting a byte (Fernet's
fixed version byte vs. the new envelope's `KeyId`-prefixed layout).
That approach had a real, exploitable collision found while wiring
this up: `auth/mfa.py`'s TOTP secrets are base32
(`pyotp.random_base32()`) — an alphabet that is a strict subset of
base64's, at a length (32 chars) that happens to be base64-block-
aligned, so a genuine plaintext TOTP secret **would successfully decode
as base64** and get misidentified as new-scheme ciphertext. Any
heuristic based on "is this valid base64" is unsound in general — some
real plaintext values legitimately are. The fix: new-scheme ciphertext
carries an explicit, versioned prefix (`_NEW_SCHEME_PREFIX`) that is
never base64 output and astronomically unlikely to occur in real
plaintext by chance. `process_result_value` checks for the literal
prefix string first — no decoding, no guessing. Everything without the
prefix goes through the legacy path exactly as before (Fernet's own
`InvalidToken`/`ValueError` handling already correctly passes through
genuine plaintext, TOTP secrets included, unaffected by this change).

**Fail-closed for the new scheme, not the legacy one — a deliberate
asymmetry.** The legacy path's `except (InvalidToken, ValueError):
return value` exists for a known, expected transitional state: rows
written before encryption was ever turned on. There is no equivalent
"expected historical state" for the new format — if a value carries
the new-scheme prefix but `decrypt_envelope()` still fails, that means
either genuine tampering or a real misconfiguration (no key configured
for data encrypted under the new scheme), and this module raises
rather than silently returning corrupted bytes as if they were valid
plaintext.

**New writes always use the new scheme once configured** — matching
the design doc's "new writes use current key version" requirement.
There's no dial to keep writing legacy-Fernet after the new scheme is
active; that's the whole point of migrating.

## Legacy scheme

- Opt-in via `RAI_FIELD_ENCRYPTION_KEY`. Unset by default so existing
  self-hosted installs aren't broken by a new required env var — this
  mirrors how `RAI_OIDC_CLIENT_SECRET` etc. are optional until a
  deployer configures SSO. When unset, `EncryptedString` is a
  transparent passthrough (plaintext in, plaintext out) and a decrypt
  failure is impossible because nothing was ever encrypted.
- **Key rotation**: `RAI_FIELD_ENCRYPTION_KEY` accepts either one Fernet
  key or a comma-separated list of them. New writes always encrypt with
  the *first* key in the list; reads try every key in the list in order
  until one decrypts successfully (`cryptography.fernet.MultiFernet`'s
  own semantics). To rotate: generate a new key, put it *first* in the
  list (old key(s) stay after it so existing ciphertext still decrypts),
  restart, then run `scripts/rotate_field_encryption_key.py` to
  re-encrypt existing rows under the new key, and only drop the old key
  from the list once that sweep has completed. See
  `compliance/KEY_MANAGEMENT.md` for the full procedure and custody
  guidance — this module only implements the mechanism, not the process.
- Fernet (symmetric, authenticated encryption — AES-128-CBC + HMAC)
  rather than a bespoke scheme. It's the standard "encrypt a string
  value with an app-held key" primitive in the `cryptography` package,
  already a transitive dependency via `PyJWT[crypto]`.
- Ciphertext is base64 text, so it's stored as `Text`, not a fixed-width
  `String` — see migration 0005 for the `audit_log.ip_address` widening
  this required.
- Not applied to `audit_log`'s hash-chain fields: `_compute_entry_hash`
  in `audit_repository.py` never includes `ip_address` in its hash
  material, so encrypting it here has zero interaction with tamper
  detection — verified before wiring this up, not assumed.

## New scheme activation

`EncryptedString`'s hooks (`process_bind_param`/`process_result_value`)
are called synchronously by SQLAlchemy — they must never `await`.
Resolving a key from an async `KeyProvider`
(`await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, None)`)
therefore has to happen once, up front, in the application's own async
startup code, which then calls the plain, synchronous
`configure_field_encryption_key(key_id, dek)` here to install the
result into this module's in-process cache. This module deliberately
has no `asyncio` import and no knowledge of `KeyProvider` beyond the
`KeyId`/`KeyPurpose` vocabulary — wiring the actual application startup
sequence to call `configure_field_encryption_key()` is a separate,
later step from this module's own change.
"""

from __future__ import annotations

import os
import threading

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from responsibleai.governance.crypto import (
    DecryptionError,
    KeyId,
    KeyPurpose,
    decode_envelope,
    decrypt_envelope,
    encode_envelope,
    encrypt_envelope,
)

_ENV_VAR = "RAI_FIELD_ENCRYPTION_KEY"

# Explicit, versioned marker distinguishing new-scheme ciphertext from
# everything else (legacy Fernet ciphertext, or genuine plaintext --
# including plaintext that happens to be valid base64, e.g. base32 TOTP
# secrets, see module docstring). Not base64 alphabet-safe by itself
# (contains ":"), so it can never be confused with the base64 payload
# that follows it, and no real Fernet token or plaintext column value
# in this codebase starts with this literal string.
_NEW_SCHEME_PREFIX = "wpcrypto2:"

_active_field_encryption_key: tuple[KeyId, bytes] | None = None
_active_key_lock = threading.Lock()


def configure_field_encryption_key(key_id: KeyId, dek: bytes) -> None:
    """Install the key `EncryptedString` uses for all new writes and
    for decrypting new-format ciphertext. See this module's docstring
    ("New scheme activation") for why this is a plain synchronous
    setter rather than something that resolves the key itself."""
    if key_id.purpose is not KeyPurpose.FIELD_ENCRYPTION:
        raise ValueError(
            f"configure_field_encryption_key requires a KeyId with "
            f"purpose=FIELD_ENCRYPTION, got {key_id.purpose!r}"
        )
    global _active_field_encryption_key
    with _active_key_lock:
        _active_field_encryption_key = (key_id, dek)


def clear_field_encryption_key() -> None:
    """Revert to the legacy-Fernet-only path. Primarily for tests —
    `_active_field_encryption_key` is process-global state that would
    otherwise leak between test cases."""
    global _active_field_encryption_key
    with _active_key_lock:
        _active_field_encryption_key = None


def _get_active_field_encryption_key() -> tuple[KeyId, bytes] | None:
    with _active_key_lock:
        return _active_field_encryption_key


def _load_fernet() -> Fernet | MultiFernet | None:
    """Read the encryption key(s) from the environment, once per column type.

    Returns None (passthrough mode) if the env var is unset. Accepts either
    one Fernet key or a comma-separated list for rotation (see this module's
    docstring and `compliance/KEY_MANAGEMENT.md`) — a single key returns a
    plain `Fernet` (unchanged behavior for the common case); multiple keys
    return a `MultiFernet`, which encrypts with the first key and tries all
    of them on decrypt. Raises at import/table-definition time if any key is
    malformed — better to fail loudly at startup than silently store
    unencrypted data because of a typo'd key.
    """
    raw = os.environ.get(_ENV_VAR)
    if not raw:
        return None
    key_strs = [k.strip() for k in raw.split(",") if k.strip()]
    if not key_strs:
        return None
    try:
        fernets = [Fernet(k.encode()) for k in key_strs]
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{_ENV_VAR} is set but contains an invalid Fernet key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc
    return fernets[0] if len(fernets) == 1 else MultiFernet(fernets)


class EncryptedString(TypeDecorator):
    """A Text column that transparently encrypts/decrypts its value.

    No-op passthrough when neither the new scheme is configured
    (`configure_field_encryption_key()`) nor the legacy
    `RAI_FIELD_ENCRYPTION_KEY` is set, so this is safe to apply to a
    column in an existing deployment without forcing encryption on
    immediately.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        active = _get_active_field_encryption_key()
        if active is not None:
            key_id, dek = active
            envelope = encrypt_envelope(dek, key_id, value.encode("utf-8"))
            return _NEW_SCHEME_PREFIX + encode_envelope(envelope)
        fernet = _load_fernet()
        if fernet is None:
            return value
        # Fernet tokens are already URL-safe base64 text.
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None

        if value.startswith(_NEW_SCHEME_PREFIX):
            # Explicit marker, not a guess (see module docstring) --
            # fail closed rather than fall through to the legacy/
            # plaintext paths below.
            active = _get_active_field_encryption_key()
            if active is None:
                raise DecryptionError(
                    "Column value is in the new envelope-encryption format "
                    "but no field-encryption key is configured — call "
                    "configure_field_encryption_key() during application "
                    "startup before reading columns encrypted under the "
                    "new scheme."
                )
            key_id, dek = active
            raw = decode_envelope(value[len(_NEW_SCHEME_PREFIX) :])
            return decrypt_envelope(dek, key_id, raw).decode("utf-8")

        fernet = _load_fernet()
        if fernet is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            # Value was written before encryption was enabled (or the key
            # rotated) — return it as-is rather than crashing the request;
            # this is stored plaintext from before the feature was turned
            # on, not corrupted data.
            return value
