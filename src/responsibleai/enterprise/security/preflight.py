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
    }
)


def _is_placeholder(value: str) -> bool:
    folded = value.strip().lower()
    return not folded or folded in _PLACEHOLDERS or folded.startswith("example")


def assert_layer2_provider_boot_safe(settings: Any) -> None:
    environment = str(getattr(settings, "environment", "development") or "development")
    production = is_production_environment(environment) or bool(getattr(settings, "is_production", False))
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
    skip = os.environ.get("WHITEPACT_OIDC_SKIP_VERIFICATION") or os.environ.get("RAI_OIDC_SKIP_VERIFICATION")
    if production and skip and skip.strip().lower() in {"1", "true", "yes"}:
        raise HostedEnterpriseSecurityError(
            "Production refuses OIDC skip_verification / unsigned-token mode."
        )
    if production and google_id:
        if _is_placeholder(google_id) or _is_placeholder(google_secret) or len(google_secret) < 16:
            raise HostedEnterpriseSecurityError(
                "Production Google Sign-In is configured with a placeholder client id/secret."
            )
    if production and ms_id:
        if _is_placeholder(ms_id) or _is_placeholder(ms_secret) or len(ms_secret) < 16:
            raise HostedEnterpriseSecurityError(
                "Production Microsoft Sign-In is configured with a placeholder client id/secret."
            )
    origin = str(getattr(settings, "webauthn_origin", "") or os.environ.get("WHITEPACT_WEBAUTHN_ORIGIN", "") or "")
    if production and origin:
        parsed = urlparse(origin)
        if parsed.scheme != "https":
            raise HostedEnterpriseSecurityError("Production WebAuthn origin must be HTTPS.")
    if production and (google_id or ms_id) and not field_encryption_is_configured():
        raise HostedEnterpriseSecurityError(
            "Production identity providers require WHITEPACT_FIELD_ENCRYPTION_KEY "
            "so OIDC client secrets and TOTP seeds cannot be stored in plaintext."
        )
