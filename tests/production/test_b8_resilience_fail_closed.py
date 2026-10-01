# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — fail-closed resilience checks (B8)."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from responsibleai.operations.config_validate import validate


def test_production_config_never_passes_with_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    errors = validate()
    assert "production_auth_disabled_forbidden" in errors


def test_production_config_never_passes_with_oidc_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_OIDC_SKIP_VERIFICATION", "true")
    monkeypatch.setenv("WHITEPACT_OIDC_ISSUER", "https://idp.example.com")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_ID", "cid")
    monkeypatch.setenv("WHITEPACT_OIDC_CLIENT_SECRET", "x" * 16)
    errors = validate()
    assert "production_oidc_skip_verification_forbidden" in errors
