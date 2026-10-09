# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Package identity guards. These tests do not publish."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "package" / "dual_ownership.py"


def _load_dual_ownership():
    spec = importlib.util.spec_from_file_location("dual_ownership", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dashboard_extra_installs_doctor_dependencies() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extra = data["project"]["optional-dependencies"]["dashboard"]
    assert "PyYAML>=6.0.3" in extra
    assert "greenlet>=3.0.3" in extra
    assert data["project"]["name"] == "rai-governance-platform"


def test_deployment_install_lines_use_the_published_name() -> None:
    text = (ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "pip install biasbuster" not in text
    assert 'pip install "biasbuster' not in text
    assert "pip install whitepact" not in text
    assert 'pip install "whitepact' not in text
    assert 'pip install "rai-governance-platform[dashboard]"' in text
    assert "pip install rai-governance-platform" in text


def test_migration_plan_lists_options_without_choosing() -> None:
    text = (ROOT / "PACKAGE_IDENTITY_MIGRATION_PLAN.md").read_text(encoding="utf-8")
    assert "Option A: retain `rai-governance-platform`" in text
    assert "Option B: canonical `whitepact`" in text
    assert "Option C: `whitepact-governance` or `whitepact-platform`" in text
    assert "This matrix is not a decision." in text
    assert "None is approved" in text or "None is approved here." in text


def test_two_code_wheels_are_rejected_and_a_shim_is_not(tmp_path: Path) -> None:
    dual = _load_dual_ownership()
    legacy = tmp_path / "rai_governance_platform-1.3.1-py3-none-any.whl"
    renamed = tmp_path / "whitepact-1.4.0-py3-none-any.whl"
    shim = tmp_path / "rai_governance_platform-1.4.0-py3-none-any.whl"
    payload = {"responsibleai/__init__.py": b"__version__ = '0'\n"}
    dual.write_wheel(legacy, distribution="rai-governance-platform", version="1.3.1", files=payload)
    dual.write_wheel(renamed, distribution="whitepact", version="1.4.0", files=payload)
    dual.write_wheel(
        shim,
        distribution="rai-governance-platform",
        version="1.4.0",
        files={},
        requires=["whitepact==1.4.0"],
    )
    with pytest.raises(dual.DualOwnershipError):
        dual.assert_exclusive_code_ownership([legacy, renamed])
    dual.assert_exclusive_code_ownership([renamed, shim])
    assert dual.code_packages_in_wheel(shim) == set()
