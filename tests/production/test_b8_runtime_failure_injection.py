# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B8 — runtime dependency failure must fail closed (no auth bypass)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app


@pytest.fixture
def authed_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_API_KEYS", "cell-b-test-key")
    monkeypatch.setenv("WHITEPACT_DB_PATH", ":memory:")
    monkeypatch.setenv("WHITEPACT_AUTO_MIGRATE", "true")
    return TestClient(app)


def test_readiness_fails_closed_on_db_ping_failure(
    authed_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenEngine:
        async def ping(self, timeout_seconds: float = 2.0) -> bool:
            return False

    monkeypatch.setattr(app_module, "_db_engine", _BrokenEngine())
    assert authed_client.get("/readyz").status_code == 503


def test_production_validator_still_blocks_auth_bypass_when_db_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime DB loss must not weaken production auth contract (fail-closed config)."""
    from cryptography.fernet import Fernet

    from responsibleai.operations.config_validate import validate

    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    errors = validate()
    assert "production_auth_disabled_forbidden" in errors
