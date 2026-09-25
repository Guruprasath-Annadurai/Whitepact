# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Release metadata: V1 application version must agree across shipped surfaces."""

from __future__ import annotations

import json
import re
from pathlib import Path

import responsibleai

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"
WEB_PACKAGE = REPO_ROOT / "web" / "package.json"


def _pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"(?P<v>[^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml project.version is required"
    return match.group("v")


def test_v1_application_version_surfaces_agree() -> None:
    pyproject_version = _pyproject_version()
    web_version = json.loads(WEB_PACKAGE.read_text(encoding="utf-8"))["version"]
    assert responsibleai.__version__ == pyproject_version
    assert web_version == pyproject_version


def test_dockerfile_oci_version_matches_package() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    version = _pyproject_version()
    assert f"WHITEPACT_VERSION={version}" in dockerfile
    chart = (REPO_ROOT / "helm" / "rai-governance" / "Chart.yaml").read_text(encoding="utf-8")
    assert f'appVersion: "{version}"' in chart
