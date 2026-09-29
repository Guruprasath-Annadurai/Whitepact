# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cloudflare Access (or compatible) JWT validation — never trust forwarded headers alone."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import jwt


@dataclass(frozen=True)
class AccessGatewayConfig:
    team_domain: str
    audience: str
    allowed_algorithms: tuple[str, ...] = ("RS256",)


def validate_access_jwt(
    token: str,
    *,
    config: AccessGatewayConfig,
    signing_key: Any,
    now_leeway_seconds: int = 0,
) -> dict[str, Any]:
    """Cryptographically validate issuer, audience, expiry, and required claims."""
    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=list(config.allowed_algorithms),
            audience=config.audience,
            options={"require": ["exp", "sub", "iss"]},
            leeway=now_leeway_seconds,
        )
    except jwt.PyJWTError as exc:
        return {"ok": False, "reason": "jwt_invalid", "detail": str(exc)}

    issuer = str(claims.get("iss", ""))
    if not issuer.endswith(config.team_domain) and config.team_domain not in issuer:
        return {"ok": False, "reason": "issuer_mismatch"}

    return {"ok": True, "employee_sub": claims.get("sub"), "claims": claims}


def reject_unverified_identity_header(forwarded_header: str | None) -> dict[str, Any]:
    if forwarded_header:
        return {"ok": False, "reason": "header_not_trusted"}
    return {"ok": False, "reason": "missing_credentials"}
