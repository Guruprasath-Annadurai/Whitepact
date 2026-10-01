# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-3 M2 — legacy ResponsibleAI HTML shell retirement (BLK-P0-06)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app
from responsibleai.dashboard.legacy_frontend import (
    is_retired_legacy_governance_path,
    unified_saas_legacy_retirement_enforced,
)


@pytest.fixture
def unified_saas_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_UNIFIED_SAAS", "1")
    return TestClient(app)


@pytest.mark.parametrize(
    "path",
    [
        "/settings",
        "/audit",
        "/organizations",
        "/static/index.html",
        "/static/js/app.js",
    ],
)
def test_legacy_governance_paths_classified(path: str) -> None:
    assert is_retired_legacy_governance_path(path)


@pytest.mark.parametrize(
    "path",
    ["/assess", "/leaderboard", "/static/whitepact/index.html", "/dashboard"],
)
def test_public_and_spa_paths_not_classified_as_legacy_shell(path: str) -> None:
    assert not is_retired_legacy_governance_path(path)


def test_legacy_settings_page_returns_404_when_unified_saas(
    unified_saas_client: TestClient,
) -> None:
    response = unified_saas_client.get("/settings")
    assert response.status_code == 404
    assert "retired" in response.text.lower()
    assert response.headers.get("X-WhitePact-Legacy-Frontend") == "retired"


def test_legacy_static_index_not_served_when_unified_saas(
    unified_saas_client: TestClient,
) -> None:
    response = unified_saas_client.get("/static/index.html")
    assert response.status_code == 404
    assert "rai_api_key" not in response.text


def test_legacy_app_js_not_served_when_unified_saas(unified_saas_client: TestClient) -> None:
    response = unified_saas_client.get("/static/js/app.js")
    assert response.status_code == 404


def test_unified_saas_flag_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import Settings

    monkeypatch.setenv("WHITEPACT_UNIFIED_SAAS", "true")
    settings = Settings(environment="development")
    assert unified_saas_legacy_retirement_enforced(settings)
