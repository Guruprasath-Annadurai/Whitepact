# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Dashboard authentication configuration contract (Launch Cell B).

Grounded in runtime behavior in ``dashboard/app.py`` and enterprise preflight.
Does not grant authority.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from responsibleai.enterprise.preflight import (
    HostedEnterpriseSecurityError,
    assert_legacy_api_keys_boot_safe,
)

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings


class DashboardAuthMethod(StrEnum):
    LEGACY_STATIC_API_KEYS = "legacy_static_api_keys"
    OIDC = "oidc"
    SAML = "saml"
    VERIFIED_PRINCIPAL_VC = "verified_principal_vc"


class ConfigurationCompleteness(StrEnum):
    ABSENT = "absent"
    PARTIAL = "partial"
    COMPLETE = "complete"


def _strip(value: str | None) -> str:
    return (value or "").strip()


def oidc_configuration_state(settings: Settings) -> ConfigurationCompleteness:
    issuer = _strip(settings.oidc_issuer)
    if not issuer:
        return ConfigurationCompleteness.ABSENT
    client_id = _strip(settings.oidc_client_id)
    if not client_id:
        return ConfigurationCompleteness.PARTIAL
    return ConfigurationCompleteness.COMPLETE


def saml_configuration_state(settings: Settings) -> ConfigurationCompleteness:
    entity_id = _strip(settings.saml_idp_entity_id)
    if not entity_id:
        return ConfigurationCompleteness.ABSENT
    if not (
        _strip(settings.saml_idp_sso_url)
        and _strip(settings.saml_idp_x509_cert)
        and _strip(settings.saml_session_secret)
    ):
        return ConfigurationCompleteness.PARTIAL
    return ConfigurationCompleteness.COMPLETE


def vc_configuration_state(settings: Settings) -> ConfigurationCompleteness:
    if not settings.vc_trusted_issuers:
        return ConfigurationCompleteness.ABSENT
    if not all(_strip(i) for i in settings.vc_trusted_issuers):
        return ConfigurationCompleteness.PARTIAL
    return ConfigurationCompleteness.COMPLETE


def configured_dashboard_auth_methods(settings: Settings) -> frozenset[DashboardAuthMethod]:
    methods: set[DashboardAuthMethod] = set()
    if settings.api_keys:
        methods.add(DashboardAuthMethod.LEGACY_STATIC_API_KEYS)
    if oidc_configuration_state(settings) != ConfigurationCompleteness.ABSENT:
        methods.add(DashboardAuthMethod.OIDC)
    if saml_configuration_state(settings) != ConfigurationCompleteness.ABSENT:
        methods.add(DashboardAuthMethod.SAML)
    if vc_configuration_state(settings) != ConfigurationCompleteness.ABSENT:
        methods.add(DashboardAuthMethod.VERIFIED_PRINCIPAL_VC)
    return frozenset(methods)


def production_viable_dashboard_auth_methods(settings: Settings) -> frozenset[DashboardAuthMethod]:
    """Methods that can satisfy production dashboard authentication when auth is enabled.

    Legacy static API keys are never viable in production (boot + request path fail closed).
    Partial OIDC/SAML/VC configurations are not viable.
    """
    viable: set[DashboardAuthMethod] = set()
    if oidc_configuration_state(settings) == ConfigurationCompleteness.COMPLETE:
        if not settings.oidc_skip_verification:
            viable.add(DashboardAuthMethod.OIDC)
    if saml_configuration_state(settings) == ConfigurationCompleteness.COMPLETE:
        viable.add(DashboardAuthMethod.SAML)
    if vc_configuration_state(settings) == ConfigurationCompleteness.COMPLETE:
        if not settings.vc_skip_verification:
            viable.add(DashboardAuthMethod.VERIFIED_PRINCIPAL_VC)
    return frozenset(viable)


def validate_dashboard_auth(settings: Settings) -> list[str]:
    """Return machine-readable auth configuration errors (secret-safe)."""
    errors: list[str] = []

    if settings.is_production:
        if not settings.auth_enabled:
            errors.append("production_auth_disabled_forbidden")
        if settings.oidc_skip_verification:
            errors.append("production_oidc_skip_verification_forbidden")
        if settings.vc_skip_verification:
            errors.append("production_vc_skip_verification_forbidden")
        try:
            assert_legacy_api_keys_boot_safe(settings)
        except HostedEnterpriseSecurityError:
            errors.append("production_static_api_keys_forbidden")

        if settings.auth_enabled:
            viable = production_viable_dashboard_auth_methods(settings)
            if not viable:
                errors.append("production_auth_enabled_without_viable_method")
            for state, label in (
                (oidc_configuration_state(settings), "oidc"),
                (saml_configuration_state(settings), "saml"),
                (vc_configuration_state(settings), "vc"),
            ):
                if state == ConfigurationCompleteness.PARTIAL:
                    errors.append(f"production_{label}_configuration_partial")

    elif settings.auth_enabled:
        if not configured_dashboard_auth_methods(settings):
            errors.append("auth_enabled_without_any_configured_method")

    return errors
