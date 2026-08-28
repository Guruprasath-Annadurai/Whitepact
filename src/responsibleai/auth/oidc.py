"""OIDC / OAuth2 JWT validation — async JWKS caching, claims extraction."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from responsibleai.auth.crypto_policy import validate_rsa_key_size


@dataclass(frozen=True)
class JWTClaims:
    sub: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = field(default_factory=list)
    org_id: str | None = None
    scopes: frozenset[str] = frozenset()
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> JWTClaims:
        roles_raw = payload.get("roles") or payload.get("groups") or []
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]
        scope_raw = payload.get("scope") or payload.get("scp") or []
        if isinstance(scope_raw, str):
            scope_raw = scope_raw.replace(",", " ").split()
        return cls(
            sub=payload.get("sub", ""),
            email=payload.get("email"),
            name=payload.get("name"),
            roles=list(roles_raw),
            org_id=payload.get("org_id") or payload.get("tenant_id"),
            scopes=frozenset(str(scope) for scope in scope_raw),
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
        audience: str | None = None,
        required_scopes: tuple[str, ...] = (),
        validate_unverified_claims: bool = False,
    ) -> None:
        self.issuer = issuer
        self.client_id = client_id
        self.skip_verification = skip_verification
        self.audience = audience if audience is not None else client_id
        self.required_scopes = frozenset(required_scopes)
        self.validate_unverified_claims = validate_unverified_claims
        self._explicit_jwks_uri = jwks_uri is not None
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
        discovered_jwks = self._discovery_doc.get("jwks_uri")
        if discovered_jwks and not self._explicit_jwks_uri:
            self._jwks = AsyncJWKSClient(discovered_jwks)
        return self._discovery_doc

    async def validate_token(self, token: str) -> JWTClaims:
        """Validate a JWT and return its claims.

        Raises ``ValueError`` if the token is invalid or expired.
        """
        if self.skip_verification:
            payload = self._decode_unverified_payload(token)
            if self.validate_unverified_claims:
                self._validate_security_claims(payload)
            return JWTClaims.from_payload(payload)

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
        # Reject a weak RSA key fail-closed, the same posture as the
        # private-key check above -- a compromised or misconfigured JWKS
        # endpoint serving e.g. a 512-bit key should never be trusted to
        # verify a bearer token's signature. See crypto_policy.py.
        validate_rsa_key_size(public_key)
        try:
            payload = pyjwt.decode(
                token,
                public_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as e:
            raise ValueError("Token has expired") from e
        except pyjwt.InvalidTokenError as e:
            raise ValueError(f"Invalid token: {e}") from e

        claims = JWTClaims.from_payload(payload)
        self._validate_claim_shape(claims)
        return claims

    @staticmethod
    def _decode_unverified_payload(token: str) -> dict[str, Any]:
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
        if not isinstance(payload, dict):
            raise ValueError("JWT payload must be a JSON object")
        return payload

    @staticmethod
    def _decode_unverified(token: str) -> JWTClaims:
        """Backward-compatible development helper; never verifies a signature."""
        return JWTClaims.from_payload(OIDCProvider._decode_unverified_payload(token))

    def _validate_security_claims(self, payload: dict[str, Any]) -> None:
        if payload.get("iss") != self.issuer:
            raise ValueError("Token issuer does not match the configured issuer")
        audience = payload.get("aud")
        audiences = {audience} if isinstance(audience, str) else set(audience or [])
        if not self.audience or self.audience not in audiences:
            raise ValueError("Token audience does not include the configured resource")
        expires_at = payload.get("exp")
        if not isinstance(expires_at, int | float) or expires_at <= time.time():
            raise ValueError("Token has expired or has no valid expiration")
        not_before = payload.get("nbf")
        if isinstance(not_before, int | float) and not_before > time.time():
            raise ValueError("Token is not yet valid")
        self._validate_claim_shape(JWTClaims.from_payload(payload))

    def _validate_claim_shape(self, claims: JWTClaims) -> None:
        if not claims.sub:
            raise ValueError("Token subject is required")
        missing = self.required_scopes - claims.scopes
        if missing:
            raise ValueError(f"Token is missing required scopes: {', '.join(sorted(missing))}")

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


def validate_mcp_authorization_server_metadata(
    metadata: dict[str, Any], *, expected_issuer: str
) -> None:
    """Validate the OAuth 2.1 discovery fields required by MCP hosts."""
    problems: list[str] = []
    if metadata.get("issuer") != expected_issuer:
        problems.append("issuer must exactly match the configured authorization server")
    for field_name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
        value = metadata.get(field_name)
        if not isinstance(value, str) or not value.startswith("https://"):
            problems.append(f"{field_name} must be an HTTPS URL")
    methods = metadata.get("code_challenge_methods_supported") or []
    if "S256" not in methods:
        problems.append("code_challenge_methods_supported must include S256")
    auth_methods = metadata.get("token_endpoint_auth_methods_supported") or []
    if not auth_methods:
        problems.append("token_endpoint_auth_methods_supported must be published")
    if problems:
        raise ValueError("Unsafe MCP authorization-server metadata: " + "; ".join(problems))
