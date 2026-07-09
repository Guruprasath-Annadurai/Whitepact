"""OIDC / OAuth2 JWT validation — async JWKS caching, claims extraction."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass(frozen=True)
class JWTClaims:
    sub: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = field(default_factory=list)
    org_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JWTClaims:
        roles_raw = payload.get("roles") or payload.get("groups") or []
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        return cls(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            roles=list(roles_raw),
            org_id=payload.get("org_id") or payload.get("tenant_id"),
            raw=payload,
        )


class AsyncJWKSClient:
    """Fetches and caches a JWKS from an OIDC provider endpoint."""

    _TTL = 3600  # re-fetch after 1 hour

    def __init__(self, jwks_uri: str) -> None:
        self._uri = jwks_uri
        self._keys: list[dict[str, Any]] = []
        self._fetched_at: float = 0.0

    async def get_signing_key(self, kid: str | None) -> dict[str, Any] | None:
        if time.monotonic() - self._fetched_at > self._TTL or not self._keys:
            await self._refresh()
        if kid:
            for k in self._keys:
                if k.get("kid") == kid:
                    return k
        return self._keys[0] if self._keys else None

    async def _refresh(self) -> None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(self._uri)
            resp.raise_for_status()
            data = resp.json()
            self._keys = data.get("keys", [])
            self._fetched_at = time.monotonic()


class OIDCProvider:
    """Validates OIDC JWT bearer tokens issued by a trusted issuer.

    Uses PyJWT when available (optional dep). Falls back to unsigned
    token introspection in test mode when ``skip_verification=True``.
    """

    def __init__(
        self,
        issuer: str,
        client_id: str,
        jwks_uri: str | None = None,
        skip_verification: bool = False,
    ) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.skip_verification = skip_verification
        _uri = jwks_uri or f"{issuer.rstrip('/')}/.well-known/jwks.json"
        self._jwks = AsyncJWKSClient(_uri)
        self._discovery_doc: dict[str, Any] | None = None

    async def discover(self) -> dict[str, Any]:
        """Fetch and cache the OIDC discovery document."""
        if self._discovery_doc:
            return self._discovery_doc
        url = f"{self.issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            self._discovery_doc = resp.json()
        return self._discovery_doc

    async def validate_token(self, token: str) -> JWTClaims:
        """Validate a JWT and return its claims.

        Raises ``ValueError`` if the token is invalid or expired.
        """
        if self.skip_verification:
            return self._decode_unverified(token)

        try:
            import jwt as pyjwt
        except ImportError as err:
            raise ImportError(
                "PyJWT[crypto] is required for OIDC token validation. "
                "Install with: pip install PyJWT[crypto]"
            ) from err

        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid")
        jwk = await self._jwks.get_signing_key(kid)
        if not jwk:
            raise ValueError("Unable to retrieve signing key from JWKS endpoint")

        from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

        public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)
        if not isinstance(public_key, RSAPublicKey):
            # A JWKS endpoint must never serve a private key; from_jwk's stub
            # allows both, so guard against a malicious/misconfigured endpoint.
            raise ValueError("JWKS signing key resolved to a private key, expected public")
        try:
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=self.client_id,
                issuer=self.issuer,
            )
        except pyjwt.ExpiredSignatureError as e:
            raise ValueError("Token has expired") from e
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}") from e

        return JWTClaims.from_payload(payload)

    @staticmethod
    def _decode_unverified(token: str) -> JWTClaims:
        import base64
        import json

        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Malformed JWT: expected 3 parts")
        padding = 4 - len(parts[1]) % 4
        padded = parts[1] + "=" * padding
        try:
            payload = json.loads(base64.urlsafe_b64decode(padded))
        except Exception as e:
            raise ValueError(f"Failed to decode JWT payload: {e}") from e
        return JWTClaims.from_payload(payload)

    def authorization_url(self, redirect_uri: str, state: str, scopes: list[str]) -> str:
        """Build the OAuth2 authorization redirect URL."""
        disc = self._discovery_doc
        if not disc:
            base = f"{self.issuer.rstrip('/')}/authorize"
        else:
            base = disc.get("authorization_endpoint", f"{self.issuer.rstrip('/')}/authorize")

        from urllib.parse import urlencode
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
        }
        return f"{base}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        client_secret: str,
    ) -> dict[str, Any]:
        """Exchange an authorization code for tokens."""
        disc = await self.discover()
        token_endpoint = disc.get("token_endpoint", f"{self.issuer.rstrip('/')}/token")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": client_secret,
                },
            )
            if resp.status_code != 200:
                raise ValueError(f"Token exchange failed: {resp.text}")
            return resp.json()
