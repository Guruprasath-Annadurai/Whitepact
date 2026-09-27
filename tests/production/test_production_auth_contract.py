# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Production dashboard authentication contract tests."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from responsibleai.dashboard.config import Settings
from responsibleai.operations.auth_contract import (
    ConfigurationCompleteness,
    DashboardAuthMethod,
    OidcTokenExchangeMode,
    configured_dashboard_auth_methods,
    mcp_vc_configuration_state,
    oidc_configuration_state,
    oidc_token_exchange_mode,
    production_viable_dashboard_auth_methods,
    validate_dashboard_auth,
)
from responsibleai.operations.config_validate import validate


def _prod_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    monkeypatch.delenv("RAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("WHITEPACT_DATABASE_URL", raising=False)
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.delenv("RAI_API_KEYS", raising=False)
    monkeypatch.delenv("WHITEPACT_API_KEYS", raising=False)


def test_auth_enabled_api_key_dev_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_API_KEYS", "dev-key")
    settings = Settings()
    assert DashboardAuthMethod.LEGACY_STATIC_API_KEYS in configured_dashboard_auth_methods(settings)
    assert validate_dashboard_auth(settings) == []


def test_auth_enabled_oidc_confidential_production_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_SECRET", "x" * 16)
    settings = Settings()
    assert oidc_token_exchange_mode(settings) == OidcTokenExchangeMode.CONFIDENTIAL
    assert oidc_configuration_state(settings) == ConfigurationCompleteness.COMPLETE
    assert DashboardAuthMethod.OIDC in production_viable_dashboard_auth_methods(settings)
    assert validate_dashboard_auth(settings) == []


def test_auth_enabled_oidc_public_pkce_production_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    monkeypatch.delenv("WHITEPACT_OIDC_CLIENT_SECRET", raising=False)
    settings = Settings()
    assert oidc_token_exchange_mode(settings) == OidcTokenExchangeMode.PUBLIC_PKCE
    assert oidc_configuration_state(settings) == ConfigurationCompleteness.COMPLETE
    assert validate_dashboard_auth(settings) == []


def test_auth_enabled_saml_complete_production_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_SAML_IDP_ENTITY_ID", "https://idp.example/entity")
    monkeypatch.setenv("WHITEPACT_SAML_IDP_SSO_URL", "https://idp.example/sso")
    monkeypatch.setenv(
        "WHITEPACT_SAML_IDP_X509_CERT",
        "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----",
    )
    monkeypatch.setenv("WHITEPACT_SAML_SESSION_SECRET", "x" * 32)
    settings = Settings()
    assert validate_dashboard_auth(settings) == []


def test_vc_only_production_does_not_satisfy_dashboard_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_VC_TRUSTED_ISSUERS", "https://issuer.example")
    settings = Settings()
    assert mcp_vc_configuration_state(settings) == ConfigurationCompleteness.COMPLETE
    assert DashboardAuthMethod.VERIFIED_PRINCIPAL_VC_MCP in configured_dashboard_auth_methods(
        settings
    )
    assert production_viable_dashboard_auth_methods(settings) == frozenset()
    errors = validate()
    assert "production_auth_enabled_without_viable_method" in errors


def test_production_auth_enabled_no_method_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    errors = validate()
    assert "production_auth_enabled_without_viable_method" in errors


def test_production_auth_disabled_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    errors = validate()
    assert "production_auth_disabled_forbidden" in errors


def test_production_static_api_keys_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_API_KEYS", "legacy-key")
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    errors = validate()
    assert "production_static_api_keys_forbidden" in errors


def test_partial_oidc_production_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.delenv("WHITEPACT_OIDC_CLIENT_ID", raising=False)
    settings = Settings()
    assert oidc_configuration_state(settings) == ConfigurationCompleteness.PARTIAL
    errors = validate_dashboard_auth(settings)
    assert "production_oidc_configuration_partial" in errors


def test_partial_confidential_oidc_short_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_SECRET", "short")
    settings = Settings()
    assert oidc_configuration_state(settings) == ConfigurationCompleteness.PARTIAL
    assert "production_oidc_configuration_partial" in validate_dashboard_auth(settings)


def test_partial_saml_production_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_SAML_IDP_ENTITY_ID", "https://idp.example/entity")
    settings = Settings()
    assert "production_saml_configuration_partial" in validate_dashboard_auth(settings)


def test_dev_auth_enabled_without_methods_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.delenv("WHITEPACT_API_KEYS", raising=False)
    errors = validate()
    assert "auth_enabled_without_any_configured_method" in errors
