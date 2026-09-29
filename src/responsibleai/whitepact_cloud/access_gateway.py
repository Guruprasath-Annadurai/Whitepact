# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cloudflare Access JWT validation — exact issuer, JWKS, no trusted headers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import jwt

from responsibleai.auth.oidc import AsyncJWKSClient


@dataclass(frozen=True)
class AccessGatewayConfig:
    """Cloudflare Access application settings (no wildcard issuer matching)."""

    trusted_issuer: str
    audience: str
    jwks_uri: str
    allowed_algorithms: tuple[str, ...] = ("RS256",)


@dataclass(frozen=True)
class AccessValidationResult:
    ok: bool
    reason: str | None = None
    employee_sub: str | None = None
    claims: dict[str, Any] | None = None
    detail: str | None = None


class CloudflareAccessValidator:
    """Validates Access JWTs using cached JWKS (rotation via periodic refresh)."""

    def __init__(
        self, config: AccessGatewayConfig, jwks_client: AsyncJWKSClient | None = None
    ) -> None:
        self._config = config
        self._jwks = jwks_client or AsyncJWKSClient(config.jwks_uri)

    async def validate(
        self,
        token: str,
        *,
        now: datetime | None = None,
        leeway_seconds: int = 0,
    ) -> AccessValidationResult:
        now = now or datetime.now(UTC)
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            return AccessValidationResult(ok=False, reason="jwt_invalid", detail=str(exc))

        alg = header.get("alg")
        if alg not in self._config.allowed_algorithms:
            return AccessValidationResult(ok=False, reason="algorithm_rejected", detail=str(alg))

        kid = header.get("kid")
        jwk = await self._jwks.get_signing_key(kid)
        if not jwk:
            return AccessValidationResult(ok=False, reason="signing_key_unavailable")

        try:
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=list(self._config.allowed_algorithms),
                audience=self._config.audience,
                issuer=self._config.trusted_issuer,
                options={"require": ["exp", "sub", "iss", "aud", "iat"]},
                leeway=leeway_seconds,
            )
        except jwt.ExpiredSignatureError:
            return AccessValidationResult(ok=False, reason="expired")
        except jwt.ImmatureSignatureError:
            return AccessValidationResult(ok=False, reason="not_yet_valid")
        except jwt.PyJWTError as exc:
            return AccessValidationResult(ok=False, reason="jwt_invalid", detail=str(exc))

        nbf = claims.get("nbf")
        if nbf is not None:
            nbf_dt = datetime.fromtimestamp(int(nbf), tz=UTC)
            if now < nbf_dt:
                return AccessValidationResult(ok=False, reason="not_yet_valid")

        if claims.get("iss") != self._config.trusted_issuer:
            return AccessValidationResult(ok=False, reason="issuer_mismatch")

        sub = claims.get("sub")
        if not sub:
            return AccessValidationResult(ok=False, reason="missing_sub")

        return AccessValidationResult(ok=True, employee_sub=str(sub), claims=dict(claims))


def validate_access_jwt_with_key(
    token: str,
    *,
    config: AccessGatewayConfig,
    signing_key: Any,
    now: datetime | None = None,
) -> AccessValidationResult:
    """Test and staging helper: validate with an injected static public key."""
    now = now or datetime.now(UTC)
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=list(config.allowed_algorithms),
            audience=config.audience,
            issuer=config.trusted_issuer,
            options={"require": ["exp", "sub", "iss", "aud", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        return AccessValidationResult(ok=False, reason="expired")
    except jwt.PyJWTError as exc:
        return AccessValidationResult(ok=False, reason="jwt_invalid", detail=str(exc))

    if claims.get("iss") != config.trusted_issuer:
        return AccessValidationResult(ok=False, reason="issuer_mismatch")
    nbf = claims.get("nbf")
    if nbf is not None and now < datetime.fromtimestamp(int(nbf), tz=UTC):
        return AccessValidationResult(ok=False, reason="not_yet_valid")
    sub = claims.get("sub")
    if not sub:
        return AccessValidationResult(ok=False, reason="missing_sub")
    return AccessValidationResult(ok=True, employee_sub=str(sub), claims=dict(claims))


def reject_unverified_identity_header(forwarded_header: str | None) -> AccessValidationResult:
    if forwarded_header:
        return AccessValidationResult(ok=False, reason="header_not_trusted")
    return AccessValidationResult(ok=False, reason="missing_credentials")
