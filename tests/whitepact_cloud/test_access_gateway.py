# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from responsibleai.whitepact_cloud.access_gateway import (
    AccessGatewayConfig,
    reject_unverified_identity_header,
    validate_access_jwt_with_key,
)

ISSUER = "https://whitepact.cloudflareaccess.com"
AUD = "whitepact-cloud-admin"


def _rsa_keypair():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key()
    return private, public


def _token(private_key, **overrides) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": "employee-123",
        "iss": ISSUER,
        "aud": AUD,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    payload.update(overrides)
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test"},
    )


def test_rejects_forwarded_identity_header() -> None:
    assert reject_unverified_identity_header("employee@example.com").reason == "header_not_trusted"


def test_validates_exact_issuer_and_audience() -> None:
    private, public = _rsa_keypair()
    pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    cfg = AccessGatewayConfig(trusted_issuer=ISSUER, audience=AUD, jwks_uri="https://example/certs")
    token = _token(private)
    assert validate_access_jwt_with_key(token, config=cfg, signing_key=pem).ok is True


def test_rejects_wrong_issuer() -> None:
    private, public = _rsa_keypair()
    pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    cfg = AccessGatewayConfig(trusted_issuer=ISSUER, audience=AUD, jwks_uri="https://example/certs")
    token = _token(private, iss="https://evil.example")
    result = validate_access_jwt_with_key(token, config=cfg, signing_key=pem)
    assert result.reason in {"issuer_mismatch", "jwt_invalid"}


def test_rejects_expired_token() -> None:
    private, public = _rsa_keypair()
    pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    cfg = AccessGatewayConfig(trusted_issuer=ISSUER, audience=AUD, jwks_uri="https://example/certs")
    past = int((datetime.now(UTC) - timedelta(hours=2)).timestamp())
    token = _token(private, exp=past)
    assert validate_access_jwt_with_key(token, config=cfg, signing_key=pem).reason == "expired"


def test_rejects_bad_signature() -> None:
    private, _ = _rsa_keypair()
    other_private, other_public = _rsa_keypair()
    pem = other_public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    cfg = AccessGatewayConfig(trusted_issuer=ISSUER, audience=AUD, jwks_uri="https://example/certs")
    token = _token(private)
    assert validate_access_jwt_with_key(token, config=cfg, signing_key=pem).reason == "jwt_invalid"
