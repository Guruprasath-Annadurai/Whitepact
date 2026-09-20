# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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
- `governance_approvals.arguments` (approved action payloads)
- `governance_upstream_servers.auth_token` (upstream credentials)

Production (`WHITEPACT_ENV`/`RAI_ENV` = production|prod) refuses to
start unless `WHITEPACT_FIELD_ENCRYPTION_KEY` or
`RAI_FIELD_ENCRYPTION_KEY` is configured. Local development may leave
the key unset; `EncryptedString` remains a transparent passthrough.

Design choices, stated plainly:
- Development remains opt-in via `RAI_FIELD_ENCRYPTION_KEY`. Unset by
  default so existing self-hosted installs aren't broken by a new
  required env var — this mirrors how `RAI_OIDC_CLIENT_SECRET` etc.
  are optional until a deployer configures SSO. When unset,
  `EncryptedString` is a transparent passthrough (plaintext in,
  plaintext out) and a decrypt failure is impossible because nothing
  was ever encrypted.
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

_WHITEPACT_ENV_VAR = "WHITEPACT_FIELD_ENCRYPTION_KEY"
_LEGACY_ENV_VAR = "RAI_FIELD_ENCRYPTION_KEY"
_ENV_VAR = _WHITEPACT_ENV_VAR


def _load_fernet() -> Fernet | MultiFernet | None:
    """Read the encryption key(s) from the environment, once per column type.

    Returns None (passthrough mode) if neither env var is set. Checks
    WHITEPACT_FIELD_ENCRYPTION_KEY first, with fallback to legacy
    RAI_FIELD_ENCRYPTION_KEY. If both are set and differ, raises ValueError
    to fail closed against key mismatch. Accepts either one Fernet key or a
    comma-separated list for rotation.
    """
    raw_whitepact = os.environ.get(_WHITEPACT_ENV_VAR)
    raw_legacy = os.environ.get(_LEGACY_ENV_VAR)

    if raw_whitepact and raw_legacy and raw_whitepact.strip() != raw_legacy.strip():
        raise ValueError(
            f"Conflicting canonical and legacy field encryption keys configured: "
            f"{_WHITEPACT_ENV_VAR} and {_LEGACY_ENV_VAR} are both set with different values. "
            "Refusing to start."
        )

    raw = raw_whitepact if raw_whitepact is not None else raw_legacy
    source_var = _WHITEPACT_ENV_VAR if raw_whitepact is not None else _LEGACY_ENV_VAR

    if not raw:
        return None
    key_strs = [k.strip() for k in raw.split(",") if k.strip()]
    if not key_strs:
        return None
    try:
        fernets = [Fernet(k.encode()) for k in key_strs]
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"{source_var} is set but contains an invalid Fernet key. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc
    return fernets[0] if len(fernets) == 1 else MultiFernet(fernets)


SENSITIVE_ENCRYPTED_COLUMNS: tuple[tuple[str, str], ...] = (
    ("org_api_keys", "mfa_secret"),
    ("webhook_configs", "secret"),
    ("governance_approvals", "arguments"),
    ("upstream_mcp_servers", "auth_token"),
    ("audit_log", "ip_address"),
    ("public_incident_reports", "reporter_name"),
    ("public_incident_reports", "reporter_contact"),
    ("human_totp_factors", "secret_encrypted"),
    ("human_totp_factors", "pending_secret_encrypted"),
    ("organization_sso_configs", "client_secret_encrypted"),
    ("identity_verifications", "legal_name_encrypted"),
)


def field_encryption_is_configured() -> bool:
    """True when a usable Fernet key is present in the environment."""
    return _load_fernet() is not None


_ENVELOPE_V1 = "wpenc:v1:"
_LEGACY_PLAINTEXT = "wplegacy:v0:"
_FERNET_PREFIX = "gAAAA"


class FieldEncryptionError(ValueError):
    """Encrypted field could not be authenticated. Never includes secrets."""


def _environment_name() -> str:
    return (
        (os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENV") or "development")
        .strip()
        .lower()
    )


def _is_production() -> bool:
    return _environment_name() in {"production", "prod"}


def _legacy_plaintext_allowed() -> bool:
    if _is_production():
        return False
    flag = (
        (
            os.environ.get("WHITEPACT_ALLOW_LEGACY_PLAINTEXT")
            or os.environ.get("RAI_ALLOW_LEGACY_PLAINTEXT")
            or ""
        )
        .strip()
        .lower()
    )
    return flag in {"1", "true", "yes"}


def _looks_like_fernet_token(value: str) -> bool:
    return value.startswith(_FERNET_PREFIX)


class EncryptedString(TypeDecorator):
    """A Text column that transparently encrypts/decrypts its value.

    Envelope:
    - ``wpenc:v1:<fernet>`` current ciphertext
    - ``gAAAA...`` historical Fernet tokens written before the envelope
    - ``wplegacy:v0:<text>`` explicit legacy plaintext (non-production only)

    Production and any environment without WHITEPACT_ALLOW_LEGACY_PLAINTEXT
    fail closed on unknown formats and authentication failure. Ciphertext is
    never returned as plaintext. Secrets are never logged.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        fernet = _load_fernet()
        if fernet is None:
            return value
        token = fernet.encrypt(value.encode()).decode()
        return f"{_ENVELOPE_V1}{token}"

    def process_result_value(self, value: str | None, dialect) -> str | None:  # noqa: ANN001
        if value is None:
            return None
        fernet = _load_fernet()
        if value.startswith(_ENVELOPE_V1) or _looks_like_fernet_token(value):
            if fernet is None:
                raise FieldEncryptionError(
                    "Encrypted identity data is present but field encryption is not configured."
                )
            token = value[len(_ENVELOPE_V1) :] if value.startswith(_ENVELOPE_V1) else value
            try:
                return fernet.decrypt(token.encode()).decode()
            except (InvalidToken, ValueError) as exc:
                raise FieldEncryptionError("Ciphertext authentication failed.") from exc
        if value.startswith(_LEGACY_PLAINTEXT):
            if not _legacy_plaintext_allowed():
                raise FieldEncryptionError(
                    "Explicit legacy plaintext is not permitted in this environment."
                )
            return value[len(_LEGACY_PLAINTEXT) :]
        if fernet is None:
            return value
        if _legacy_plaintext_allowed():
            return value
        raise FieldEncryptionError("Unrecognized encrypted field format.")
