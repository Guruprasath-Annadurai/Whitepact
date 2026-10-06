# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-3 M2 — legacy ResponsibleAI HTML shell retirement (BLK-P0-06)."""

from __future__ import annotations

from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app
from responsibleai.dashboard.legacy_frontend import (
    RETIRED_LEGACY_STATIC_INVENTORY,
    canonicalize_http_path,
    is_retired_legacy_governance_path,
    unified_saas_legacy_retirement_enforced,
)

_LEGACY_HTML_FILENAMES: tuple[str, ...] = tuple(
    sorted(
        path.removeprefix("/static/")
        for path in RETIRED_LEGACY_STATIC_INVENTORY
        if path.endswith(".html")
    )
)


@pytest.fixture
def unified_saas_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_UNIFIED_SAAS", "1")
    return TestClient(app)


def _retired_namespace_bypass_aliases(html_filename: str) -> list[str]:
    """BLK-P0-06-BYPASS-02: retired dir must never be servable under /static."""
    rel = f"_retired_legacy_governance/{html_filename}"
    return sorted(
        {
            f"/static/{rel}",
            f"/static//{rel}",
            f"/static///{rel}",
            f"/static//_retired_legacy_governance//{html_filename}",
            f"/static/./{rel}",
            f"/static/_retired_legacy_governance/../_retired_legacy_governance/{html_filename}",
            f"/static/{quote(rel, safe='/')}",
        }
    )


def _static_path_aliases(canonical_static_path: str) -> list[str]:
    """Generate normalized alias spellings for regression (BLK-P0-06-BYPASS-01)."""
    assert canonical_static_path.startswith("/static/")
    rel = canonical_static_path.removeprefix("/static/")
    aliases = {
        canonical_static_path,
        canonical_static_path.replace("/static/", "/static//"),
        canonical_static_path.replace("/static/", "/static///"),
        f"/static//{rel}",
        f"/static///{rel}",
        f"/static/./{rel}",
        f"/static/{rel.split('/')[0]}//{'/'.join(rel.split('/')[1:])}"
        if "/" in rel
        else f"/static//{rel}",
    }
    if "/" in rel:
        parent, leaf = rel.rsplit("/", 1)
        aliases.add(f"/static/{parent}/../{leaf}")
    aliases.add(f"/static/{quote(rel, safe='/')}")
    return sorted(aliases)


def _page_path_aliases(canonical_path: str) -> list[str]:
    return [
        canonical_path,
        canonical_path + "/",
        canonical_path + "//",
    ]


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


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/static//index.html", "/static/index.html"),
        ("/static///audit.html", "/static/audit.html"),
        ("/static/./settings.html", "/static/settings.html"),
        ("/static/js/../index.html", "/static/index.html"),
        ("/audit//", "/audit"),
    ],
)
def test_canonicalize_http_path_collapses_bypass_forms(raw: str, expected: str) -> None:
    assert canonicalize_http_path(raw) == expected


def test_legacy_settings_page_returns_404_when_unified_saas(
    unified_saas_client: TestClient,
) -> None:
    response = unified_saas_client.get("/settings")
    assert response.status_code == 404
    assert "retired" in response.text.lower()
    assert response.headers.get("X-WhitePact-Legacy-Frontend") == "retired"


@pytest.mark.parametrize("path", _page_path_aliases("/audit"))
def test_legacy_page_aliases_blocked(unified_saas_client: TestClient, path: str) -> None:
    response = unified_saas_client.get(path)
    assert response.status_code == 404
    assert response.headers.get("X-WhitePact-Legacy-Frontend") == "retired"


def test_legacy_static_index_not_served_when_unified_saas(
    unified_saas_client: TestClient,
) -> None:
    response = unified_saas_client.get("/static/index.html")
    assert response.status_code == 404
    assert "rai_api_key" not in response.text


@pytest.mark.parametrize("path", _static_path_aliases("/static/index.html"))
def test_retired_static_inventory_index_aliases_404(
    unified_saas_client: TestClient, path: str
) -> None:
    response = unified_saas_client.get(path)
    assert response.status_code == 404
    assert "rai_api_key" not in response.text.lower()
    assert response.headers.get("X-WhitePact-Legacy-Frontend") == "retired"


@pytest.mark.parametrize("canonical", sorted(RETIRED_LEGACY_STATIC_INVENTORY))
def test_every_retired_static_asset_class_blocked(
    unified_saas_client: TestClient, canonical: str
) -> None:
    for alias in _static_path_aliases(canonical):
        response = unified_saas_client.get(alias)
        assert response.status_code == 404, alias
        assert "rai_api_key" not in response.text.lower()


def test_legacy_app_js_not_served_when_unified_saas(unified_saas_client: TestClient) -> None:
    for path in _static_path_aliases("/static/js/app.js"):
        response = unified_saas_client.get(path)
        assert response.status_code == 404
        assert "rai_api_key" not in response.text


@pytest.mark.parametrize("html_name", sorted(_LEGACY_HTML_FILENAMES))
def test_retired_namespace_paths_never_served_bypass_02(
    unified_saas_client: TestClient, html_name: str
) -> None:
    for path in _retired_namespace_bypass_aliases(html_name):
        response = unified_saas_client.get(path)
        assert response.status_code == 404, path
        assert "rai_api_key" not in response.text.lower()
        assert response.headers.get("X-WhitePact-Legacy-Frontend") == "retired"


@pytest.mark.parametrize("html_name", sorted(_LEGACY_HTML_FILENAMES))
def test_retired_html_not_on_static_mount_disk(html_name: str) -> None:
    from pathlib import Path

    static_root = Path(__file__).resolve().parents[1] / "src/responsibleai/dashboard/static"
    assert not (static_root / html_name).is_file()
    assert not (static_root / "_retired_legacy_governance" / html_name).is_file()


def test_modern_whitepact_static_still_served(unified_saas_client: TestClient) -> None:
    for path in ("/static/whitepact/index.html", "/static//whitepact//index.html"):
        response = unified_saas_client.get(path)
        assert response.status_code == 200
        assert "rai_api_key" not in response.text


def test_unified_saas_flag_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import Settings

    monkeypatch.setenv("WHITEPACT_UNIFIED_SAAS", "true")
    settings = Settings(environment="development")
    assert unified_saas_legacy_retirement_enforced(settings)


def test_community_mode_can_still_load_legacy_shell_static(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("WHITEPACT_UNIFIED_SAAS", raising=False)
    monkeypatch.setenv("WHITEPACT_ENVIRONMENT", "development")
    monkeypatch.setenv("WHITEPACT_MCP_TRUST_DOMAIN", "community")
    client = TestClient(app)
    response = client.get("/static/index.html")
    assert response.status_code == 200
    assert "/static/js/app.js" in response.text
    js = client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "rai_api_key" in js.text
