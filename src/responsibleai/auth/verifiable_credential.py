"""Verified Principal (Authority Everywhere Phase 3) — W3C Verifiable
Credential (JWT-VC) bearer verification, additive to the existing
human-IdP path in ``auth/oidc.py`` and ``auth/saml.py``.

**What this closes**: `docs/architecture/AUTHORITY_EVERYWHERE.md`'s
lifecycle table (row 1, "Verified Principal") states the gap plainly —
`auth/oidc.py`/`auth/saml.py` verify *human* identities via an
enterprise IdP, but there is no path for a *non-human* principal (a
service account, or another organization's attested agent) to present
a cryptographically verifiable credential of its own and be recognized
as the actor behind a governed action. This module is that path.

**Deliberately scoped to JWT-VC over a JWKS-publishing issuer, not the
full VC/OpenID4VP stack**:

- A credential here is a JWT whose payload carries a top-level ``vc``
  claim per the W3C VC-JWT convention (``vc.type``, ``vc.credentialSubject``).
  Verification reuses exactly the same JWKS-fetch, `kid`-resolution,
  private-key-rejection, and weak-RSA-key-rejection posture
  `auth/oidc.py`'s `OIDCProvider.validate_token()` already established
  — the credential's issuer is just another entity that publishes a
  JWKS at ``<issuer>/.well-known/jwks.json``, exactly like an OIDC IdP.
- **Not built**: DID resolution (`did:key`, `did:web`), JSON-LD proof
  formats (`Ed25519Signature2020` etc.), or the full OpenID4VP
  authorization-request/response presentation-exchange protocol. None
  of the libraries those would need (`didkit`, `pyld`, ...) are
  dependencies of this codebase today, and adding them is real,
  separate work this phase doesn't attempt. A credential presented as
  a JSON-LD proof or resolved via a DID document is rejected, not
  silently accepted with weaker checks.
- **Trust is allowlist-based, not automatic**: unlike OIDC (one
  configured issuer, matched exactly), a Verified Principal deployment
  may need to trust multiple credential issuers (this org's own
  service-account issuer, a partner org's attestation issuer, ...).
  `VerifiableCredentialProvider` only ever verifies a credential whose
  ``iss`` claim is in the deployment's admin-configured trusted-issuer
  allowlist (`Settings.vc_trusted_issuers`) — an unlisted issuer is
  rejected before any network call or crypto verification happens.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from responsibleai.auth.crypto_policy import validate_rsa_key_size
from responsibleai.auth.oidc import AsyncJWKSClient


@dataclass(frozen=True)
class VerifiableCredentialClaims:
    """Mirrors `JWTClaims`/`SAMLAssertionClaims`'s shape on purpose —
    same "sub/email/name/roles/org_id/raw" vocabulary the rest of
    `auth/*` already uses, plus the two fields a VC-JWT adds that a
    plain OIDC token doesn't carry: which credential type was
    presented, and what kind of non-human holder it describes."""

    sub: str
    issuer: str
    credential_type: str
    holder_kind: str  # "service_account" | "external_agent"
    org_id: str | None = None
    roles: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def looks_like_vc_jwt(token: str) -> bool:
    """Unverified peek at a bearer token's payload to decide *which*
    verifier to try — never trusted for anything beyond routing. Full
    signature/issuer/expiry verification always happens afterward in
    whichever verifier is chosen, exactly the same posture
    `OIDCProvider.validate_token()` already uses when it peeks the
    unverified header for `kid` before verifying anything."""
    try:
        import jwt as pyjwt
    except ImportError:
        return False
    parts = token.split(".")
    if len(parts) != 3:
        return False
    try:
        payload = pyjwt.decode(token, options={"verify_signature": False})
    except Exception:
        return False
    return isinstance(payload.get("vc"), dict)


class VerifiableCredentialProvider:
    """Validates a JWT-VC bearer presentation from one of a set of
    trusted issuers. One `AsyncJWKSClient` per issuer, lazily created
    and cached for the life of the provider — mirrors `OIDCProvider`'s
    single-issuer JWKS cache, generalized to many issuers."""

    def __init__(
        self,
        trusted_issuers: list[str],
        skip_verification: bool = False,
    ) -> None:
        self.trusted_issuers = frozenset(trusted_issuers)
        self.skip_verification = skip_verification
        self._jwks_clients: dict[str, AsyncJWKSClient] = {}

    def _jwks_for(self, issuer: str) -> AsyncJWKSClient:
        client = self._jwks_clients.get(issuer)
        if client is None:
            client = AsyncJWKSClient(f"{issuer.rstrip('/')}/.well-known/jwks.json")
            self._jwks_clients[issuer] = client
        return client

    async def validate_presentation(self, vp_token: str) -> VerifiableCredentialClaims:
        """Validate a VC-JWT and return its claims.

        Raises ``ValueError`` if the token is invalid, expired, from an
        untrusted issuer, or not shaped like a VC-JWT.
        """
        try:
            import jwt as pyjwt
        except ImportError as err:
            raise ImportError(
                "PyJWT[crypto] is required for Verifiable Credential validation. "
                "Install with: pip install PyJWT[crypto]"
            ) from err

        unverified_payload = pyjwt.decode(vp_token, options={"verify_signature": False})
        issuer = unverified_payload.get("iss")
        if not issuer or issuer not in self.trusted_issuers:
            raise ValueError(f"Untrusted or missing credential issuer: {issuer!r}")

        if self.skip_verification:
            payload = unverified_payload
        else:
            header = pyjwt.get_unverified_header(vp_token)
            kid = header.get("kid")
            jwk = await self._jwks_for(issuer).get_signing_key(kid)
            if not jwk:
                raise ValueError("Unable to retrieve signing key from issuer JWKS endpoint")

            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

            public_key = pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)
            if not isinstance(public_key, RSAPublicKey):
                raise ValueError("JWKS signing key resolved to a private key, expected public")
            validate_rsa_key_size(public_key)
            try:
                payload = pyjwt.decode(
                    vp_token,
                    public_key,
                    algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                    issuer=issuer,
                    options={"verify_aud": False},
                )
            except pyjwt.ExpiredSignatureError as e:
                raise ValueError("Credential has expired") from e
            except pyjwt.InvalidTokenError as e:
                raise ValueError(f"Invalid credential: {e}") from e

        return self._claims_from_payload(issuer, payload)

    @staticmethod
    def _claims_from_payload(issuer: str, payload: dict[str, Any]) -> VerifiableCredentialClaims:
        vc = payload.get("vc")
        if not isinstance(vc, dict):
            raise ValueError("Credential is missing a 'vc' claim")
        vc_types = vc.get("type")
        if not isinstance(vc_types, list) or not vc_types:
            raise ValueError("Credential 'vc.type' must be a non-empty list")
        credential_type = next((t for t in vc_types if t != "VerifiableCredential"), None)
        if not credential_type:
            raise ValueError("Credential 'vc.type' has no specific credential type")

        subject = vc.get("credentialSubject")
        if not isinstance(subject, dict):
            raise ValueError("Credential is missing 'vc.credentialSubject'")
        holder_kind = subject.get("holderKind")
        if holder_kind not in ("service_account", "external_agent"):
            raise ValueError(
                "Credential 'vc.credentialSubject.holderKind' must be "
                "'service_account' or 'external_agent'"
            )

        roles_raw = subject.get("roles") or []
        if isinstance(roles_raw, str):
            roles_raw = [roles_raw]

        return VerifiableCredentialClaims(
            sub=payload.get("sub", ""),
            issuer=issuer,
            credential_type=credential_type,
            holder_kind=holder_kind,
            org_id=subject.get("orgId") or payload.get("org_id"),
            roles=list(roles_raw),
            raw=payload,
        )
