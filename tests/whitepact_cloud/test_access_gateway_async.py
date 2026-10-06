# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from responsibleai.whitepact_cloud.access_gateway import (
    AccessGatewayConfig,
    CloudflareAccessValidator,
)

ISSUER = "https://whitepact.cloudflareaccess.com"
AUD = "whitepact-cloud-admin"


def _rsa_keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


class _StaticJwks:
    def __init__(self, jwk: dict) -> None:
        self._jwk = jwk

    async def get_signing_key(self, kid: str | None) -> dict | None:
        if kid == "test":
            return self._jwk
        return None


def _config() -> AccessGatewayConfig:
    return AccessGatewayConfig(
        trusted_issuer=ISSUER, audience=AUD, jwks_uri="https://example/certs"
    )


@pytest.mark.asyncio
async def test_async_validator_accepts_valid_token() -> None:
    private, public = _rsa_keypair()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks(jwk))
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "emp-async",
            "iss": ISSUER,
            "aud": AUD,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        private,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    result = await validator.validate(token)
    assert result.ok is True
    assert result.employee_sub == "emp-async"


@pytest.mark.asyncio
async def test_async_validator_rejects_unsupported_algorithm() -> None:
    jwk = {"kty": "RSA", "kid": "test"}
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks(jwk))
    token = jwt.encode({"sub": "x"}, "hmac-secret", algorithm="HS256", headers={"kid": "test"})
    result = await validator.validate(token)
    assert result.reason == "algorithm_rejected"


@pytest.mark.asyncio
async def test_async_validator_missing_signing_key() -> None:
    private, public = _rsa_keypair()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks(jwk))
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "emp",
            "iss": ISSUER,
            "aud": AUD,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        private,
        algorithm="RS256",
        headers={"kid": "unknown"},
    )
    result = await validator.validate(token)
    assert result.reason == "signing_key_unavailable"


@pytest.mark.asyncio
async def test_async_validator_rejects_garbage_token() -> None:
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks({}))
    result = await validator.validate("not.a.jwt")
    assert result.reason == "jwt_invalid"


@pytest.mark.asyncio
async def test_async_validator_rejects_expired() -> None:
    private, public = _rsa_keypair()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks(jwk))
    past = int((datetime.now(UTC) - timedelta(hours=2)).timestamp())
    token = jwt.encode(
        {
            "sub": "emp",
            "iss": ISSUER,
            "aud": AUD,
            "iat": past - 3600,
            "exp": past,
        },
        private,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    result = await validator.validate(token)
    assert result.reason == "expired"


@pytest.mark.asyncio
async def test_async_validator_rejects_missing_sub_after_decode() -> None:
    private, public = _rsa_keypair()
    jwk = json.loads(RSAAlgorithm.to_jwk(public))
    validator = CloudflareAccessValidator(_config(), jwks_client=_StaticJwks(jwk))
    now = datetime.now(UTC)
    # sub present for jwt library require but empty string fails our check
    token = jwt.encode(
        {
            "sub": "",
            "iss": ISSUER,
            "aud": AUD,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        private,
        algorithm="RS256",
        headers={"kid": "test"},
    )
    result = await validator.validate(token)
    assert result.reason == "missing_sub"
