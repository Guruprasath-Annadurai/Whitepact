# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — health and log contract smoke (B5)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app
from responsibleai.operations.production_contract import STRUCTURED_LOG_CORE_FIELDS


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    monkeypatch.setenv("WHITEPACT_DB_PATH", ":memory:")
    monkeypatch.setenv("WHITEPACT_AUTO_MIGRATE", "true")
    return TestClient(app)


def test_livez_and_readyz_do_not_leak_secrets(client: TestClient) -> None:
    for path in ("/livez", "/readyz"):
        resp = client.get(path)
        assert resp.status_code in {200, 503}
        body = resp.text.lower()
        assert "password=" not in body
        assert "bearer " not in body


def test_structured_log_field_contract_includes_correlation_ids() -> None:
    assert "request_id" in STRUCTURED_LOG_CORE_FIELDS
    assert "correlation_id" in STRUCTURED_LOG_CORE_FIELDS
    assert "tenant_id" in STRUCTURED_LOG_CORE_FIELDS
