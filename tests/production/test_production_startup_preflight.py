# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""CLI and startup preflight must share the same production contract."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from responsibleai.dashboard.config import Settings
from responsibleai.enterprise.preflight import (
    HostedEnterpriseSecurityError,
    assert_hosted_enterprise_boot_safe,
)
from responsibleai.operations.config_validate import main as config_validate_main
from responsibleai.operations.production_config import collect_production_configuration_errors


def _prod_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    monkeypatch.delenv("RAI_DATABASE_URL", raising=False)
    monkeypatch.delenv("WHITEPACT_DATABASE_URL", raising=False)
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.setenv(
        "WHITEPACT_IDENTITY_WEBHOOK_SECRET",
        "production-identity-webhook-secret-32chars-min",
    )
    monkeypatch.delenv("RAI_API_KEYS", raising=False)
    monkeypatch.delenv("WHITEPACT_API_KEYS", raising=False)
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_RP_ID", "app.example.com")
    monkeypatch.setenv(
        "WHITEPACT_SESSION_SECRET",
        "production-session-secret-32chars-minimum-length",
    )


def test_cli_and_startup_reject_same_invalid_production_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _prod_base(monkeypatch)
    assert config_validate_main([]) == 1
    settings = Settings()
    cli_errors = collect_production_configuration_errors(settings)
    assert "production_auth_enabled_without_viable_method" in cli_errors
    with pytest.raises(
        HostedEnterpriseSecurityError, match="production_auth_enabled_without_viable_method"
    ):
        assert_hosted_enterprise_boot_safe(settings)


def test_cli_and_startup_accept_oidc_production_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_SECRET", "x" * 16)
    assert config_validate_main([]) == 0
    settings = Settings()
    assert collect_production_configuration_errors(settings) == []
    assert_hosted_enterprise_boot_safe(settings)


def test_mcp_unauthenticated_demo_rejected_by_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    _prod_base(monkeypatch)
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://accounts.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "client-id")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_SECRET", "x" * 16)
    monkeypatch.setenv("WHITEPACT_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO", "true")
    settings = Settings()
    with pytest.raises(
        HostedEnterpriseSecurityError, match="production_mcp_unauthenticated_demo_forbidden"
    ):
        assert_hosted_enterprise_boot_safe(settings)
