# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Minimum cryptographic-strength policy for keys and secrets this
codebase either generates itself or accepts from a caller/external
party (OpenSSF Best Practices `crypto_keylength` criterion).

Two different trust boundaries, two different checks:

- **WhitePact-generated secrets** (API keys via `secrets.token_urlsafe(32)`
  in `db/org_repository.py`, TOTP seeds via `pyotp.random_base32()` in
  `auth/mfa.py`, Fernet keys via `cryptography.fernet.Fernet.generate_key()`
  documented in `compliance/KEY_MANAGEMENT.md`) already meet modern
  strength requirements by construction — each uses a CSPRNG
  (`secrets`/`os.urandom`) at a fixed, adequate length, and Fernet's own
  constructor rejects any key that isn't a valid 32-byte key. Nothing in
  this module needs to re-check those; they're correct by the primitive
  chosen, not by policy enforced after the fact.
- **Externally supplied secrets/keys this module explicitly validates**:
  a caller-supplied webhook HMAC signing secret (`validate_webhook_secret`),
  and an RSA public key fetched from a configured OIDC provider's JWKS
  endpoint (`validate_rsa_key_size`) — the two places this codebase
  accepts a security-relevant key/secret *from someone else* and can
  reasonably enforce a floor on it before trusting it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

# NIST SP 800-107 recommends an HMAC key be at least as long as the
# underlying hash function's output -- 32 bytes (256 bits) for
# HMAC-SHA256, the algorithm `webhooks/manager.py` signs deliveries
# with. A caller-supplied secret is a UTF-8 string, not raw bytes, so
# this floor is stated in characters -- a 32-character secret drawn
# from a reasonable character set (as any generated-and-copy-pasted
# secret is) carries well over 128 bits of real entropy even in the
# worst case (lowercase-only), comfortably past the practical
# brute-force threshold for an HMAC key.
MIN_WEBHOOK_SECRET_LENGTH = 32

# 2048 bits is the NIST/industry-standard floor for RSA in 2026 (NIST SP
# 800-57 Part 1 rates 2048-bit RSA as providing >=112 bits of security
# through 2030; anything smaller no longer meets that bar). This
# codebase never generates its own RSA keys -- it only ever receives
# one from a deployer-configured OIDC provider's JWKS endpoint
# (`auth/oidc.py::OIDCProvider.validate_token()`) -- so this is a floor
# on what WhitePact will *trust*, not a claim about keys it issues.
MIN_RSA_KEY_SIZE_BITS = 2048


def validate_webhook_secret(secret: str) -> None:
    """Raises `ValueError` if *secret* is non-empty and below policy.

    An **empty** secret is deliberately not an error here — it means
    "this webhook delivery is unsigned," a legitimate, explicit choice
    a deployer can make (see `webhooks/manager.py`: `if config.secret:`
    skips signing entirely when empty). What this function exists to
    reject is a *present but weak* secret — someone typing `"secret123"`
    into the field, which would otherwise silently produce a real
    HMAC-SHA256 signature header that carries none of the security
    property a signature is supposed to provide.
    """
    if secret and len(secret) < MIN_WEBHOOK_SECRET_LENGTH:
        raise ValueError(
            f"Webhook signing secret must be either empty (disables "
            f"signing) or at least {MIN_WEBHOOK_SECRET_LENGTH} characters "
            f"long — got {len(secret)}. Generate one with: "
            f'python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )


def validate_rsa_key_size(key: RSAPublicKey) -> None:
    """Raises `ValueError` if *key*'s modulus is below
    `MIN_RSA_KEY_SIZE_BITS`. Called on every RSA key fetched from a
    configured OIDC provider's JWKS endpoint, before it's trusted to
    verify a bearer token's signature — a compromised or misconfigured
    JWKS endpoint serving a deliberately weak key should be rejected
    fail-closed, the same posture `OIDCProvider.validate_token()`
    already takes toward a JWKS endpoint serving a private key instead
    of a public one.
    """
    if key.key_size < MIN_RSA_KEY_SIZE_BITS:
        raise ValueError(
            f"JWKS RSA key size {key.key_size} bits is below the required "
            f"minimum of {MIN_RSA_KEY_SIZE_BITS} bits (NIST SP 800-57 Part 1)."
        )
