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

Design choices, stated plainly:
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
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

_ENV_VAR = "RAI_FIELD_ENCRYPTION_KEY"


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
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        ) from exc
    return fernets[0] if len(fernets) == 1 else MultiFernet(fernets)


class EncryptedString(TypeDecorator):
    """A Text column that transparently encrypts/decrypts its value.

    No-op passthrough when `RAI_FIELD_ENCRYPTION_KEY` is unset, so this
    is safe to apply to a column in an existing deployment without
    forcing encryption on immediately.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        fernet = _load_fernet()
        if fernet is None:
            return value
        # Fernet tokens are already URL-safe base64 text.
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
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
