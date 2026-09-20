# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed production preflight for Layer 2 identity providers."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from responsibleai.dashboard.config import is_production_environment
from responsibleai.db.encryption import field_encryption_is_configured
from responsibleai.enterprise.preflight import HostedEnterpriseSecurityError

_PLACEHOLDERS = frozenset(
    {
        "changeme",
        "secret",
        "password",
        "test",
        "example",
        "client-secret",
        "google-client-secret",
        "microsoft-client-secret",
        "dev",
        "sample",
        "localhost-secret",
        "session-secret",
    }
)


def _is_placeholder(value: str) -> bool:
    folded = value.strip().lower()
    return not folded or folded in _PLACEHOLDERS or folded.startswith("example")


def assert_layer2_provider_boot_safe(settings: Any) -> None:
    environment = str(getattr(settings, "environment", "development") or "development")
    production = is_production_environment(environment) or bool(
        getattr(settings, "is_production", False)
    )
    google_id = (
        os.environ.get("WHITEPACT_GOOGLE_CLIENT_ID")
        or os.environ.get("RAI_GOOGLE_CLIENT_ID")
        or getattr(settings, "google_client_id", "")
        or ""
    ).strip()
    google_secret = (
        os.environ.get("WHITEPACT_GOOGLE_CLIENT_SECRET")
        or os.environ.get("RAI_GOOGLE_CLIENT_SECRET")
        or ""
    ).strip()
    ms_id = (
        os.environ.get("WHITEPACT_MICROSOFT_CLIENT_ID")
        or os.environ.get("RAI_MICROSOFT_CLIENT_ID")
        or ""
    ).strip()
    ms_secret = (
        os.environ.get("WHITEPACT_MICROSOFT_CLIENT_SECRET")
        or os.environ.get("RAI_MICROSOFT_CLIENT_SECRET")
        or ""
    ).strip()
    skip = os.environ.get("WHITEPACT_OIDC_SKIP_VERIFICATION") or os.environ.get(
        "RAI_OIDC_SKIP_VERIFICATION"
    )
    if production and skip and skip.strip().lower() in {"1", "true", "yes"}:
        raise HostedEnterpriseSecurityError(
            "Production refuses OIDC skip_verification / unsigned-token mode."
        )
    raw_token = os.environ.get("WHITEPACT_OIDC_ALLOW_RAW_ID_TOKEN") or os.environ.get(
        "RAI_OIDC_ALLOW_RAW_ID_TOKEN"
    )
    if production and raw_token and raw_token.strip().lower() in {"1", "true", "yes"}:
        raise HostedEnterpriseSecurityError("Production refuses raw id_token hosted login.")
    if production and google_id:
        if _is_placeholder(google_id) or _is_placeholder(google_secret) or len(google_secret) < 16:
            raise HostedEnterpriseSecurityError(
                "Production Google Sign-In is configured with a placeholder client id/secret."
            )
        callback = (
            os.environ.get("WHITEPACT_OIDC_REDIRECT_URI")
            or getattr(settings, "hosted_oauth_redirect_uri", "")
            or ""
        ).strip()
        if callback:
            parsed = urlparse(callback)
            if parsed.scheme != "https" or not parsed.netloc:
                raise HostedEnterpriseSecurityError(
                    "Production OAuth callback must be an HTTPS URL."
                )
    if production and ms_id:
        if _is_placeholder(ms_id) or _is_placeholder(ms_secret) or len(ms_secret) < 16:
            raise HostedEnterpriseSecurityError(
                "Production Microsoft Sign-In is configured with a placeholder client id/secret."
            )
    origin = str(
        getattr(settings, "webauthn_origin", "")
        or os.environ.get("WHITEPACT_WEBAUTHN_ORIGIN", "")
        or ""
    )
    rp_id = str(
        getattr(settings, "webauthn_rp_id", "")
        or os.environ.get("WHITEPACT_WEBAUTHN_RP_ID", "")
        or ""
    )
    if production:
        if not origin:
            raise HostedEnterpriseSecurityError("Production WebAuthn origin is required.")
        parsed = urlparse(origin)
        if parsed.scheme != "https":
            raise HostedEnterpriseSecurityError("Production WebAuthn origin must be HTTPS.")
        if not rp_id:
            raise HostedEnterpriseSecurityError("Production WebAuthn RP ID is required.")
        if not field_encryption_is_configured():
            raise HostedEnterpriseSecurityError(
                "Production identity security requires WHITEPACT_FIELD_ENCRYPTION_KEY."
            )
        session_secret = (
            os.environ.get("WHITEPACT_SESSION_SECRET")
            or os.environ.get("RAI_SESSION_SECRET")
            or str(
                getattr(settings, "secret_key", "") or getattr(settings, "session_secret", "") or ""
            )
        )
        if session_secret and (_is_placeholder(session_secret) or len(session_secret) < 32):
            raise HostedEnterpriseSecurityError(
                "Production session secret is missing or a known default."
            )
    if production and (google_id or ms_id) and not field_encryption_is_configured():
        raise HostedEnterpriseSecurityError(
            "Production identity providers require WHITEPACT_FIELD_ENCRYPTION_KEY "
            "so OIDC client secrets and TOTP seeds cannot be stored in plaintext."
        )
