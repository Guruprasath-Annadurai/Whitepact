"""Tests for auth.verifiable_credential and governance.principal --
Verified Principal (Authority Everywhere Phase 3). Mirrors test_oidc.py
and test_crypto_policy.py's TestOIDCProviderRejectsWeakJWKSKey patterns
for VC-JWT verification, since VerifiableCredentialProvider reuses the
same AsyncJWKSClient / weak-key-rejection / private-key-rejection
machinery OIDCProvider already established."""

from __future__ import annotations

import json

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from responsibleai.auth.verifiable_credential import (
    VerifiableCredentialProvider,
    looks_like_vc_jwt,
)
from responsibleai.governance.principal import PrincipalClaim, build_principal_claim


def _vc_payload(
    *,
    sub: str = "service-account-1",
    iss: str = "https://issuer.example.com",
    credential_type: str = "AuthorityEverywherePrincipal",
    holder_kind: str = "service_account",
    org_id: str | None = "org-1",
    roles: list[str] | None = None,
) -> dict:
    return {
        "sub": sub,
        "iss": iss,
        "vc": {
            "type": ["VerifiableCredential", credential_type],
            "credentialSubject": {
                "holderKind": holder_kind,
                "orgId": org_id,
                "roles": roles or [],
            },
        },
    }


def _sign(payload: dict, private_key, kid: str, algorithm: str = "RS256") -> str:
    return pyjwt.encode(payload, private_key, algorithm=algorithm, headers={"kid": kid})


class TestLooksLikeVcJwt:
    def test_true_for_token_with_vc_claim(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign(_vc_payload(), private, "k1")
        assert looks_like_vc_jwt(token) is True

    def test_false_for_plain_oidc_token(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign({"sub": "u1", "iss": "https://idp.example.com"}, private, "k1")
        assert looks_like_vc_jwt(token) is False

    def test_false_for_malformed_token(self):
        assert looks_like_vc_jwt("not-a-jwt") is False

    def test_false_for_static_api_key(self):
        assert looks_like_vc_jwt("rai_abc123") is False


class TestVerifiableCredentialProviderValidatePresentation:
    async def test_valid_presentation_is_accepted(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "vc-key-1"
        token = _sign(_vc_payload(), private, "vc-key-1")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        claims = await provider.validate_presentation(token)
        assert claims.sub == "service-account-1"
        assert claims.issuer == "https://issuer.example.com"
        assert claims.credential_type == "AuthorityEverywherePrincipal"
        assert claims.holder_kind == "service_account"
        assert claims.org_id == "org-1"

    async def test_untrusted_issuer_rejected_before_any_verification(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign(_vc_payload(iss="https://untrusted.example.com"), private, "k1")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        with pytest.raises(ValueError, match="Untrusted"):
            await provider.validate_presentation(token)

    async def test_missing_issuer_claim_rejected(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload = _vc_payload()
        del payload["iss"]
        token = pyjwt.encode(payload, private, algorithm="RS256", headers={"kid": "k1"})

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        with pytest.raises(ValueError, match="Untrusted"):
            await provider.validate_presentation(token)

    async def test_missing_vc_claim_rejected(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "k1"
        token = _sign({"sub": "u1", "iss": "https://issuer.example.com"}, private, "k1")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        with pytest.raises(ValueError, match="vc"):
            await provider.validate_presentation(token)

    async def test_invalid_holder_kind_rejected(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "k1"
        token = _sign(_vc_payload(holder_kind="human"), private, "k1")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        with pytest.raises(ValueError, match="holderKind"):
            await provider.validate_presentation(token)

    async def test_expired_credential_rejected(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "k1"
        payload = _vc_payload()
        payload["exp"] = 1  # long expired
        token = _sign(payload, private, "k1")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        with pytest.raises(ValueError, match="expired"):
            await provider.validate_presentation(token)

    async def test_weak_rsa_key_rejected_during_real_verification(self, monkeypatch):
        weak_private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                weak_private.public_key()
            )
        )
        jwk_dict["kid"] = "weak-vc-key"
        token = _sign(_vc_payload(), weak_private, "weak-vc-key")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        with pytest.raises(ValueError, match="below the required minimum"):
            await provider.validate_presentation(token)

    async def test_missing_signing_key_raises(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign(_vc_payload(), private, "unknown-kid")

        provider = VerifiableCredentialProvider(trusted_issuers=["https://issuer.example.com"])

        async def _fake_get_signing_key(kid):
            return None

        monkeypatch.setattr(
            provider._jwks_for("https://issuer.example.com"),
            "get_signing_key",
            _fake_get_signing_key,
        )

        with pytest.raises(ValueError, match="Unable to retrieve signing key"):
            await provider.validate_presentation(token)

    async def test_skip_verification_mode_bypasses_signature_check(self):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = _sign(_vc_payload(), private, "k1")

        provider = VerifiableCredentialProvider(
            trusted_issuers=["https://issuer.example.com"], skip_verification=True
        )
        claims = await provider.validate_presentation(token)
        assert claims.sub == "service-account-1"


class TestBuildPrincipalClaim:
    def test_builds_claim_with_field_names_only(self):
        payload = _vc_payload()

        from responsibleai.auth.verifiable_credential import VerifiableCredentialClaims

        vc_claims = VerifiableCredentialClaims(
            sub="service-account-1",
            issuer="https://issuer.example.com",
            credential_type="AuthorityEverywherePrincipal",
            holder_kind="service_account",
            org_id="org-1",
            raw=payload,
        )

        claim = build_principal_claim(vc_claims)
        assert isinstance(claim, PrincipalClaim)
        assert claim.principal_id == "service-account-1"
        assert claim.org_id == "org-1"
        assert claim.issuer == "https://issuer.example.com"
        assert claim.credential_type == "AuthorityEverywherePrincipal"
        assert claim.holder_kind == "service_account"
        assert set(claim.claim_keys) == {"holderKind", "orgId", "roles"}
        d = claim.to_dict()
        assert "claim_keys" in d
        assert "roles" not in d  # never the raw role values, only that the key existed


class TestIdentityContextFromPrincipalClaim:
    def test_produces_vc_kind_identity(self):
        from responsibleai.governance.models import IdentityContext

        claim = PrincipalClaim(
            principal_id="agent-42",
            org_id="org-1",
            issuer="https://issuer.example.com",
            credential_type="AuthorityEverywherePrincipal",
            holder_kind="external_agent",
        )
        identity = IdentityContext.from_principal_claim(claim)
        assert identity.identity_id == "vc:agent-42"
        assert identity.kind == "vc"
        assert identity.org_id == "org-1"
        assert identity.org_context is None
