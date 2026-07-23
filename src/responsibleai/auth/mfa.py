"""TOTP (RFC 6238) multi-factor auth for the dashboard login flow.

Scope, stated plainly: this platform authenticates via bearer API keys and
OIDC SSO, not a username/password login — there's no per-human account to
attach MFA to in the classic sense. The one interactive human entry point is
`/login` (a browser establishing a trusted dashboard session by presenting an
API key). This module gates *that* step: an org can require a TOTP code
alongside the key before the browser is trusted, closing the "an API key
alone is a full login" gap enterprise security reviewers ask about. It does
not — and cannot — add MFA to machine-to-machine API calls, where there is
no human present to hold a second factor; those continue to authenticate on
the key alone, same as before.

Each named API key (`org_api_keys` row) can enroll its own TOTP secret,
since a key's `name` is the closest thing this model has to a "user" (e.g.
"jane-dashboard", "ci-pipeline"). An org can additionally set
`mfa_required=True` to force every key under it through enrollment before
`/login` succeeds — the same enforcement pattern as `sso_required`.

Uses `pyotp` (opt-in via the `mfa` extra) rather than hand-rolling RFC 6238 —
small, single-purpose, widely used, not worth re-implementing.
"""

from __future__ import annotations

import hashlib
import secrets

import pyotp

_BACKUP_CODE_COUNT = 10
_BACKUP_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
_BACKUP_CODE_LENGTH = 10


def generate_secret() -> str:
    """A fresh base32 TOTP seed. Store via EncryptedString; never log it."""
    return pyotp.random_base32()


def provisioning_uri(secret: str, *, account_name: str, issuer: str = "ResponsibleAI") -> str:
    """otpauth:// URI for a TOTP app (Google Authenticator, 1Password, Authy, ...).

    No QR image is rendered server-side — the frontend shows this URI as
    text plus the raw secret, since any TOTP app accepts manual entry.
    Avoids adding a QR-rendering dependency for a one-time enrollment step.
    """
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)


def verify_code(secret: str, code: str) -> bool:
    """Check a 6-digit TOTP code, allowing 1 step (30s) of clock drift either way."""
    if not code or not code.isdigit():
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes() -> list[str]:
    """10 single-use recovery codes, shown once at enrollment confirmation."""
    return [
        "".join(secrets.choice(_BACKUP_CODE_ALPHABET) for _ in range(_BACKUP_CODE_LENGTH))
        for _ in range(_BACKUP_CODE_COUNT)
    ]


def hash_backup_code(code: str) -> str:
    """SHA-256 hash for storage — codes are never stored in plaintext,
    same principle as API keys themselves (see org_repository._hash_key)."""
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def verify_and_consume_backup_code(hashed_codes: list[str], code: str) -> list[str] | None:
    """Check *code* against the stored hash list. Returns the remaining
    (post-consumption) hash list on success, or None if the code didn't
    match anything — the caller persists the returned list so each backup
    code works exactly once."""
    if not code:
        return None
    target = hash_backup_code(code)
    if target not in hashed_codes:
        return None
    remaining = list(hashed_codes)
    remaining.remove(target)
    return remaining
