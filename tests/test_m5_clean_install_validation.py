# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Clean developer install smoke (no tribal-knowledge paths)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_pyproject_declares_console_scripts() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "whitepact-mcp" in text
    assert "console_scripts" in text or "[project.scripts]" in text


def test_package_import_smoke() -> None:
    import responsibleai  # noqa: F401
    import responsibleai.governance  # noqa: F401
    import responsibleai.mcp  # noqa: F401


@pytest.mark.skipif(shutil.which("npm") is None, reason="npm not available")
def test_web_package_json_exists() -> None:
    pkg = ROOT / "web" / "package.json"
    assert pkg.is_file()


def test_cli_entrypoint_declared() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "whitepact" in text


def test_python_sdk_client_import() -> None:
    from sdk.python.rai_client.governance import GovernanceRuntimeClient  # noqa: F401
