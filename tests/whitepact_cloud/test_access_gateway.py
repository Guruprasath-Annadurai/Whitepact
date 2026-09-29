# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import jwt

from responsibleai.whitepact_cloud.access_gateway import (
    AccessGatewayConfig,
    reject_unverified_identity_header,
    validate_access_jwt,
)


def test_rejects_forwarded_identity_header() -> None:
    assert reject_unverified_identity_header("employee@example.com")["reason"] == "header_not_trusted"


def test_validates_signed_jwt() -> None:
    key = "test-signing-key-32-bytes-min!!!"
    token = jwt.encode(
        {
            "sub": "employee-123",
            "iss": "https://whitepact.cloudflareaccess.com",
            "aud": "whitepact-cloud-admin",
            "exp": 9_999_999_999,
        },
        key,
        algorithm="HS256",
    )
    cfg = AccessGatewayConfig(
        team_domain="cloudflareaccess.com",
        audience="whitepact-cloud-admin",
        allowed_algorithms=("HS256",),
    )
    result = validate_access_jwt(token, config=cfg, signing_key=key)
    assert result["ok"] is True
