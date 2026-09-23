# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical identity-provider namespaces.

Email is never the identity key. Provider aliases must collapse into one
canonical enum so ``google`` and ``Google`` cannot become distinct subjects.
"""

from __future__ import annotations

from enum import StrEnum


class CanonicalProvider(StrEnum):
    GOOGLE = "GOOGLE"
    GOOGLE_WORKSPACE = "GOOGLE_WORKSPACE"
    MICROSOFT = "MICROSOFT"
    MICROSOFT_ENTRA = "MICROSOFT_ENTRA"
    ENTERPRISE_SSO = "ENTERPRISE_SSO"


_ALIASES: dict[str, CanonicalProvider] = {
    "google": CanonicalProvider.GOOGLE,
    "google_oidc": CanonicalProvider.GOOGLE,
    "google-oidc": CanonicalProvider.GOOGLE,
    "google sign-in": CanonicalProvider.GOOGLE,
    "workspace-google": CanonicalProvider.GOOGLE_WORKSPACE,
    "google_workspace": CanonicalProvider.GOOGLE_WORKSPACE,
    "google-workspace": CanonicalProvider.GOOGLE_WORKSPACE,
    "gws": CanonicalProvider.GOOGLE_WORKSPACE,
    "microsoft": CanonicalProvider.MICROSOFT,
    "microsoft_oidc": CanonicalProvider.MICROSOFT,
    "microsoft-oidc": CanonicalProvider.MICROSOFT,
    "msa": CanonicalProvider.MICROSOFT,
    "entra": CanonicalProvider.MICROSOFT_ENTRA,
    "azuread": CanonicalProvider.MICROSOFT_ENTRA,
    "azure_ad": CanonicalProvider.MICROSOFT_ENTRA,
    "azure-ad": CanonicalProvider.MICROSOFT_ENTRA,
    "microsoft_entra": CanonicalProvider.MICROSOFT_ENTRA,
    "microsoft-entra": CanonicalProvider.MICROSOFT_ENTRA,
    "enterprise_sso": CanonicalProvider.ENTERPRISE_SSO,
    "enterprise-sso": CanonicalProvider.ENTERPRISE_SSO,
    "saml": CanonicalProvider.ENTERPRISE_SSO,
    "oidc_sso": CanonicalProvider.ENTERPRISE_SSO,
}


def canonicalize_provider(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Provider identifier is required.")
    folded = raw.casefold().replace(" ", "_")
    if folded in _ALIASES:
        return _ALIASES[folded].value
    try:
        return CanonicalProvider(raw.upper().replace("-", "_")).value
    except ValueError as exc:
        raise ValueError(f"Unknown identity provider {value!r}.") from exc


def provider_account_key(
    *, provider: str, subject: str, tenant_id: str | None
) -> tuple[str, str, str]:
    """Canonical lookup tuple: provider + signed sub + tenant (hd/tid)."""
    if not subject or not str(subject).strip():
        raise ValueError("Provider subject is required.")
    return canonicalize_provider(provider), str(subject).strip(), (tenant_id or "")
