# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Static tree inventory — no unknown files reachable in unified mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app
from responsibleai.dashboard.static_surface_inventory import (
    StaticAssetClass,
    classify_static_relpath,
    iter_static_files,
    unknown_static_files,
)


def test_static_tree_has_no_unknown_assets() -> None:
    unknown = unknown_static_files()
    assert unknown == [], f"unclassified static files: {unknown}"


def test_legacy_js_not_under_public_static_mount() -> None:
    static_root = Path(__file__).resolve().parents[1] / "src/responsibleai/dashboard/static"
    assert not (static_root / "js" / "app.js").is_file()
    legacy_app = (
        Path(__file__).resolve().parents[1]
        / "src/responsibleai/dashboard/legacy_templates/assets/js/app.js"
    )
    assert legacy_app.is_file()


@pytest.mark.parametrize(
    "relpath,expected", [("whitepact/index.html", StaticAssetClass.MODERN_WHITEPACT)]
)
def test_classify_samples(relpath: str, expected: StaticAssetClass) -> None:
    assert classify_static_relpath(relpath) is expected


def test_unified_mode_unknown_static_paths_return_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_UNIFIED_SAAS", "1")
    client = TestClient(app)
    for relpath, _cls in iter_static_files():
        if _cls is not StaticAssetClass.UNKNOWN:
            continue
        response = client.get(f"/static/{relpath}")
        assert response.status_code == 404
