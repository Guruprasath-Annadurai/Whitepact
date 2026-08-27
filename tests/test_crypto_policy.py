"""Tests for `auth/crypto_policy.py` (OpenSSF `crypto_keylength`):
webhook signing secret entropy floor, and RSA JWKS key-size rejection,
including an end-to-end check that a weak key served by a JWKS endpoint
is actually rejected by `OIDCProvider.validate_token()`, not just by
the standalone policy function in isolation.
"""

from __future__ import annotations

import json
import time

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from responsibleai.auth.crypto_policy import (
    MIN_RSA_KEY_SIZE_BITS,
    MIN_WEBHOOK_SECRET_LENGTH,
    validate_rsa_key_size,
    validate_webhook_secret,
)
from responsibleai.auth.oidc import OIDCProvider


class TestWebhookSecretPolicy:
    def test_empty_secret_accepted(self) -> None:
        validate_webhook_secret("")  # no raise -- unsigned deliveries are legitimate

    def test_secret_at_minimum_length_accepted(self) -> None:
        validate_webhook_secret("a" * MIN_WEBHOOK_SECRET_LENGTH)

    def test_secret_above_minimum_accepted(self) -> None:
        validate_webhook_secret("a" * (MIN_WEBHOOK_SECRET_LENGTH + 10))

    def test_short_secret_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            validate_webhook_secret("short")

    def test_one_char_below_minimum_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_webhook_secret("a" * (MIN_WEBHOOK_SECRET_LENGTH - 1))


def _rsa_public_key(bits: int) -> rsa.RSAPublicKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=bits).public_key()


class TestRSAKeySizePolicy:
    def test_2048_bit_key_accepted(self) -> None:
        validate_rsa_key_size(_rsa_public_key(2048))

    def test_4096_bit_key_accepted(self) -> None:
        validate_rsa_key_size(_rsa_public_key(4096))

    def test_1024_bit_key_rejected(self) -> None:
        with pytest.raises(ValueError, match="below the required minimum"):
            validate_rsa_key_size(_rsa_public_key(1024))

    def test_512_bit_key_rejected(self) -> None:
        with pytest.raises(ValueError):
            validate_rsa_key_size(_rsa_public_key(512))

    def test_boundary_matches_documented_minimum(self) -> None:
        assert MIN_RSA_KEY_SIZE_BITS == 2048


class TestOIDCProviderRejectsWeakJWKSKey:
    """End-to-end: a token signed with (and a JWKS endpoint serving) a
    genuinely weak RSA key is rejected by validate_token() itself, not
    just by the standalone policy function -- proving the two are
    actually wired together, not merely both existing in the codebase.
    """

    async def test_weak_key_rejected_during_real_verification(self, monkeypatch) -> None:
        weak_private = rsa.generate_private_key(public_exponent=65537, key_size=1024)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                weak_private.public_key()
            )
        )
        jwk_dict["kid"] = "weak-test-key"

        token = pyjwt.encode(
            {
                "sub": "user-1",
                "aud": "test-client",
                "iss": "https://issuer.example.com",
                "exp": int(time.time()) + 300,
            },
            weak_private,
            algorithm="RS256",
            headers={"kid": "weak-test-key"},
        )

        provider = OIDCProvider(
            issuer="https://issuer.example.com", client_id="test-client", skip_verification=False
        )

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)

        with pytest.raises(ValueError, match="below the required minimum"):
            await provider.validate_token(token)

    async def test_strong_key_passes_the_key_size_check(self, monkeypatch) -> None:
        strong_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                strong_private.public_key()
            )
        )
        jwk_dict["kid"] = "strong-test-key"

        token = pyjwt.encode(
            {
                "sub": "user-1",
                "aud": "test-client",
                "iss": "https://issuer.example.com",
                "exp": int(time.time()) + 300,
            },
            strong_private,
            algorithm="RS256",
            headers={"kid": "strong-test-key"},
        )

        provider = OIDCProvider(
            issuer="https://issuer.example.com", client_id="test-client", skip_verification=False
        )

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)

        # Should pass the key-size check and proceed to real signature
        # verification -- a valid token, correct audience/issuer, so
        # this should succeed all the way through, not just skip the
        # size check.
        claims = await provider.validate_token(token)
        assert claims.sub == "user-1"
