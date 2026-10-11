# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""BLK-P0-05 — local wheel install smoke (no PyPI publish)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

import responsibleai

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_whitepact_first_description() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "WhitePact" in text
    assert 'name = "rai-governance-platform"' in text


def test_whitepact_import_alias_matches_responsibleai() -> None:
    import whitepact

    assert whitepact.__version__ == responsibleai.__version__


def test_helm_chart_app_version_aligned() -> None:
    chart = yaml.safe_load((ROOT / "helm/rai-governance/Chart.yaml").read_text(encoding="utf-8"))
    assert chart["appVersion"] == responsibleai.__version__


def test_built_wheel_installs_in_isolated_venv(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(ROOT), "-w", str(wheel_dir), "-q"],
        check=True,
        cwd=ROOT,
    )
    wheels = list(wheel_dir.glob("rai_governance_platform-*.whl"))
    assert wheels, "expected rai_governance_platform wheel artifact"
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    pip = venv / "bin" / "pip"
    subprocess.run([str(pip), "install", str(wheels[0]), "-q"], check=True)
    probe = subprocess.run(
        [
            str(venv / "bin" / "python"),
            "-c",
            "import responsibleai, whitepact; assert whitepact.__version__",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0
