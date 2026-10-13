# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — operator diagnostics CLI (B11)."""

from __future__ import annotations

import pytest

from responsibleai.operations.operator_status import main as operator_main


def test_operator_status_dev_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert operator_main([]) == 0


def test_operator_status_production_invalid_without_auth_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db.example:5432/wp")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WHITEPACT_ALLOW_ALL_ORIGINS", "false")
    monkeypatch.delenv("RAI_ALLOW_ALL_ORIGINS", raising=False)
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "true")
    assert operator_main([]) == 1
