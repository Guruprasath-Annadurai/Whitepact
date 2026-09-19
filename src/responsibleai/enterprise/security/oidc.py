# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""OIDC token validation (RFC 9700). Never trust claims before signature verification.

Unknown kid: refresh trusted JWKS once, then DENY. Algorithm is taken from an
allowlist, never from an attacker-controlled header alone. Discovery/JWKS
fetches go through SafeNetwork and must match the configured issuer host.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from responsibleai.auth.crypto_policy import validate_rsa_key_size
from responsibleai.enterprise.errors import EnterpriseError, PROVIDER_TOKEN_INVALID
from responsibleai.net.egress import DestinationPolicy, create_safe_async_client, validate_outbound_url

ALLOWED_ALGS = ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512")
GOOGLE_ISSUERS = frozenset({"https://accounts.google.com", "accounts.google.com"})
MSA_TENANT = "9188040d-6c67-4c5b-b112-36a304b66dad"


def _deny(message: str) -> EnterpriseError:
    return EnterpriseError(PROVIDER_TOKEN_INVALID, message, 401)


def issuer_host(issuer: str) -> str:
    parsed = urlparse(issuer if "://" in issuer else f"https://{issuer}")
    return (parsed.hostname or "").lower()


def assert_https_issuer(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise _deny("OIDC issuer and metadata URLs must be HTTPS with a host.")


# Provider-owned JWKS hosts that are not the token issuer host.
_TRUSTED_JWKS_HOSTS = {
    "accounts.google.com": frozenset({"www.googleapis.com"}),
    "login.microsoftonline.com": frozenset({"login.microsoftonline.com"}),
}


class TrustedJWKS:
    def __init__(self, jwks_url: str, *, issuer: str) -> None:
        assert_https_issuer(jwks_url)
        assert_https_issuer(issuer if "://" in issuer else f"https://{issuer}")
        jwks_h = issuer_host(jwks_url)
        iss_h = issuer_host(issuer)
        extra: set[str] = set()
        for host, allowed in _TRUSTED_JWKS_HOSTS.items():
            if iss_h == host or iss_h.endswith("." + host):
                extra |= set(allowed)
                extra.add(host)
        if jwks_h != iss_h and jwks_h not in extra:
            raise _deny("JWKS host must match the configured issuer host.")
        validate_outbound_url(jwks_url, DestinationPolicy.PUBLIC_ONLY)
        self._url = jwks_url
        self._keys: list[dict[str, Any]] = []
        self._fetched_at = 0.0

    async def get(self, kid: str | None, *, allow_refresh: bool) -> dict[str, Any] | None:
        if not self._keys or (time.monotonic() - self._fetched_at) > 3600:
            await self.refresh()
        key = self._by_kid(kid)
        if key is None and allow_refresh:
            await self.refresh()
            key = self._by_kid(kid)
        return key

    def _by_kid(self, kid: str | None) -> dict[str, Any] | None:
        if kid:
            for key in self._keys:
                if key.get("kid") == kid:
                    return key
            return None
        return self._keys[0] if len(self._keys) == 1 else None

    async def refresh(self) -> None:
        async with create_safe_async_client(timeout=5.0, policy=DestinationPolicy.PUBLIC_ONLY) as client:
            response = await client.get(self._url)
            response.raise_for_status()
            if len(response.content) > 256_000:
                raise _deny("JWKS document exceeded size bound.")
            data = response.json()
        keys = data.get("keys") if isinstance(data, dict) else None
        if not isinstance(keys, list):
            raise _deny("JWKS document is malformed.")
        self._keys = [k for k in keys if isinstance(k, dict)]
        self._fetched_at = time.monotonic()


@dataclass(frozen=True)
class VerifiedIDToken:
    issuer: str
    subject: str
    audience: str
    email: str | None
    hosted_domain: str | None
    tenant_id: str | None
    nonce: str | None
    expires_at: int
    raw: dict[str, Any]


class OIDCTokenValidator:
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks_url: str | None = None,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.audience = audience
        jwks = jwks_url or f"{self.issuer}/.well-known/jwks.json"
        self._jwks = TrustedJWKS(jwks, issuer=self.issuer)

    async def validate(
        self,
        token: str,
        *,
        expected_nonce: str | None = None,
        expected_tenant: str | None = None,
    ) -> VerifiedIDToken:
        try:
            import jwt as pyjwt
        except ImportError as exc:
            raise _deny("PyJWT is required for OIDC validation.") from exc
        try:
            header = pyjwt.get_unverified_header(token)
        except Exception as exc:
            raise _deny("Malformed JWT header.") from exc
        alg = header.get("alg")
        if alg not in ALLOWED_ALGS:
            raise _deny("JWT algorithm is not allowed.")
        if alg == "none" or str(alg).lower() == "none":
            raise _deny("JWT algorithm none is rejected.")
        kid = header.get("kid")
        try:
            jwk = await self._jwks.get(kid, allow_refresh=True)
        except Exception as exc:
            raise _deny("JWKS refresh failed closed.") from exc
        if jwk is None:
            raise _deny("Unknown JWT kid after trusted JWKS refresh.")
        try:
            public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

            if not isinstance(public_key, RSAPublicKey):
                raise _deny("JWKS key is not an RSA public key.")
            validate_rsa_key_size(public_key)
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=list(ALLOWED_ALGS),
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except EnterpriseError:
            raise
        except Exception as exc:
            raise _deny("JWT signature or claims validation failed.") from exc
        if expected_nonce is not None and payload.get("nonce") != expected_nonce:
            raise _deny("OIDC nonce mismatch.")
        tenant = payload.get("tid") or payload.get("tenant_id")
        if expected_tenant is not None and tenant != expected_tenant:
            raise _deny("Token tenant does not match the bound organization tenant.")
        aud = payload.get("aud")
        if isinstance(aud, list):
            aud = aud[0] if aud else ""
        return VerifiedIDToken(
            issuer=str(payload.get("iss", "")),
            subject=str(payload.get("sub", "")),
            audience=str(aud),
            email=payload.get("email"),
            hosted_domain=payload.get("hd"),
            tenant_id=str(tenant) if tenant else None,
            nonce=payload.get("nonce"),
            expires_at=int(payload["exp"]),
            raw=payload,
        )


async def fetch_discovery(issuer: str) -> dict[str, Any]:
    assert_https_issuer(issuer)
    url = f"{issuer.rstrip('/')}/.well-known/openid-configuration"
    if issuer_host(url) != issuer_host(issuer):
        raise _deny("Discovery host must match issuer.")
    validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
    async with create_safe_async_client(timeout=5.0, policy=DestinationPolicy.PUBLIC_ONLY) as client:
        response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > 256_000:
            raise _deny("Discovery document exceeded size bound.")
        data = response.json()
    if not isinstance(data, dict) or data.get("issuer", "").rstrip("/") != issuer.rstrip("/"):
        raise _deny("Discovery issuer mismatch.")
    jwks = str(data.get("jwks_uri", ""))
    if issuer_host(jwks) != issuer_host(issuer):
        raise _deny("Discovery JWKS host is not the issuer host.")
    return data
