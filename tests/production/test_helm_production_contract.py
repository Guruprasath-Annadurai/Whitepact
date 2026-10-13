# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — Helm production values contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from responsibleai.operations.helm_contract import collect_helm_profile_errors
from responsibleai.operations.helm_validate import validate_file

REPO = Path(__file__).resolve().parents[2]
CHART = REPO / "helm" / "rai-governance"
PROD_VALUES = CHART / "values-production.yaml"
DEV_VALUES = CHART / "values-development.yaml"


def test_production_values_file_passes_validator() -> None:
    assert validate_file(PROD_VALUES) == []


def test_development_profile_allows_permissive_cors() -> None:
    values = yaml.safe_load(DEV_VALUES.read_text(encoding="utf-8"))
    assert collect_helm_profile_errors(values) == []


def test_production_rejects_auth_disabled() -> None:
    values = yaml.safe_load(PROD_VALUES.read_text(encoding="utf-8"))
    values["config"]["authEnabled"] = False
    errors = collect_helm_profile_errors(values)
    assert "helm_production_auth_disabled_forbidden" in errors


def test_production_rejects_mcp_demo_mode() -> None:
    values = yaml.safe_load(PROD_VALUES.read_text(encoding="utf-8"))
    values["config"]["mcpHttpAllowUnauthenticatedDemo"] = True
    errors = collect_helm_profile_errors(values)
    assert "helm_production_mcp_unauthenticated_demo_forbidden" in errors


def test_production_rejects_static_api_keys() -> None:
    values = yaml.safe_load(PROD_VALUES.read_text(encoding="utf-8"))
    values["config"]["apiKeys"] = "live-key"
    errors = collect_helm_profile_errors(values)
    assert "helm_production_static_api_keys_forbidden" in errors


def test_helm_lint_with_production_overlay() -> None:
    result = subprocess.run(
        ["helm", "lint", str(CHART), "-f", str(PROD_VALUES)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_helm_template_production_renders() -> None:
    result = subprocess.run(
        [
            "helm",
            "template",
            "rai-governance",
            str(CHART),
            "-f",
            str(PROD_VALUES),
            "--set",
            "image.tag=cell-b-test",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    rendered = result.stdout
    assert "readOnlyRootFilesystem: true" in rendered
    assert "runAsNonRoot: true" in rendered
    assert "terminationGracePeriodSeconds: 30" in rendered
    assert "WHITEPACT_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO" in rendered


def test_dockerfile_pins_base_images_and_runs_non_root() -> None:
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim@sha256:" in dockerfile
    assert "USER appuser" in dockerfile
    assert "HEALTHCHECK" in dockerfile
