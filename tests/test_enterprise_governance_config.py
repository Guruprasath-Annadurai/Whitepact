# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression test suite for enterprise four-eyes governance configuration.

Proves:
1. In staging and production, missing policy_governance_mode defaults to "tiered".
2. In staging and production, explicit policy_governance_mode="tiered" succeeds.
3. In staging and production, explicit policy_governance_mode="single_admin" raises ValueError.
4. Environment variables (WHITEPACT_POLICY_GOVERNANCE_MODE, RAI_POLICY_GOVERNANCE_MODE)
   cannot bypass four-eyes enforcement in staging or production.
5. In development/test environments, weaker modes remain permitted for local development.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from responsibleai.dashboard.config import Settings


def test_staging_defaults_to_tiered_governance(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_POLICY_GOVERNANCE_MODE", raising=False)
    monkeypatch.delenv("RAI_POLICY_GOVERNANCE_MODE", raising=False)

    s = Settings(environment="staging")
    assert s.policy_governance_mode == "tiered"


def test_production_defaults_to_tiered_governance(monkeypatch) -> None:
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("WHITEPACT_POLICY_GOVERNANCE_MODE", raising=False)
    monkeypatch.delenv("RAI_POLICY_GOVERNANCE_MODE", raising=False)

    s = Settings(
        environment="production",
        mcp_trust_domain="enterprise",
        database_url="postgresql+asyncpg://user:pass@localhost:5432/whitepact",
    )
    assert s.policy_governance_mode == "tiered"


def test_staging_allows_explicit_tiered_governance(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    s = Settings(environment="staging", policy_governance_mode="tiered")
    assert s.policy_governance_mode == "tiered"


def test_staging_rejects_single_admin_governance(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    with pytest.raises(ValidationError) as excinfo:
        Settings(environment="staging", policy_governance_mode="single_admin")
    assert "four-eyes governance" in str(excinfo.value)
    assert "single_admin" in str(excinfo.value)


def test_production_rejects_single_admin_governance(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    with pytest.raises(ValidationError) as excinfo:
        Settings(
            environment="production",
            policy_governance_mode="single_admin",
            mcp_trust_domain="enterprise",
        )
    assert "four-eyes governance" in str(excinfo.value)
    assert "single_admin" in str(excinfo.value)


def test_env_var_bypass_attempt_is_rejected_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.setenv("WHITEPACT_POLICY_GOVERNANCE_MODE", "single_admin")

    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "four-eyes governance" in str(excinfo.value)
    assert "single_admin" in str(excinfo.value)


def test_legacy_env_var_bypass_attempt_is_rejected_in_staging(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_POLICY_GOVERNANCE_MODE", raising=False)
    monkeypatch.setenv("RAI_POLICY_GOVERNANCE_MODE", "single_admin")

    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "four-eyes governance" in str(excinfo.value)
    assert "single_admin" in str(excinfo.value)


def test_development_allows_single_admin_governance(monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    s = Settings(environment="development", policy_governance_mode="single_admin")
    assert s.policy_governance_mode == "single_admin"
