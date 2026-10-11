# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 hostile regression — dynamic surface across qualified M1–M3 + M4 hardening."""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

M4_CAMPAIGN_MODULES: tuple[str, ...] = (
    "tests.test_m4_engineering_gates",
    "tests.test_m4_audit_export_batch_smoke",
    "tests.test_m4_audit_index_performance_guard",
    "tests.test_m4_telemetry_fail_closed",
    "tests.test_m4_otel_correlation",
    "tests.test_m4_cloud_origin_static",
    "tests.test_m4_postgres_assault_campaign",
    "tests.test_m4_scim_adversarial_extension",
    "tests.test_m4_chaos_fail_closed",
    "tests.test_m4_revocation_under_failure",
    "tests.test_m4_restore_drill_evidence",
    "tests.test_m4_m123_regression_index",
    "tests.test_restore_admission_chokepoint",
    "tests.test_scim_and_session_lifecycle",
    "tests.test_iam_adversarial_matrix",
    "tests.test_totp_matched_counter_security",
    "tests.test_m3_adversarial_security_campaign",
    "tests.test_mcp_ws2_authority_matrix",
)

M4_REQUIRED_FILES: tuple[str, ...] = (
    "test_auth_real_postgres.py",
    "test_phase5_postgres_concurrency.py",
    "test_phase7a_authority_kernel.py",
    "test_pg_security_preservation.py",
    "test_iam_adversarial_matrix.py",
    "test_totp_matched_counter_security.py",
    "test_terraform_m4_validate.py",
)


@pytest.mark.parametrize("module_name", M4_CAMPAIGN_MODULES)
def test_m4_campaign_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)


@pytest.mark.parametrize("filename", M4_REQUIRED_FILES)
def test_m4_required_regression_file_present(filename: str) -> None:
    assert (ROOT / filename).is_file(), f"missing M4 regression anchor: {filename}"


def test_m4_terraform_tree_blocks_provision_without_apply_marker() -> None:
    readme = ROOT.parent / "infra" / "terraform" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8").lower()
    assert "apply" in text or "provision" in text
    assert "blocked" in text or "validate" in text or "plan-only" in text


@pytest.mark.m4_hostile_smoke
def test_m4_hostile_smoke_subprocess() -> None:
    """Fast in-process campaign slice (no PG battery)."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_m4_telemetry_fail_closed.py",
        "tests/test_m4_otel_correlation.py",
        "tests/test_m4_cloud_origin_static.py",
        "tests/test_m4_scim_adversarial_extension.py",
        "tests/test_m4_chaos_fail_closed.py",
        "tests/test_m4_revocation_under_failure.py",
        "tests/test_m4_restore_drill_evidence.py",
        "tests/test_m4_audit_index_performance_guard.py",
        "tests/test_m4_m123_regression_index.py",
        "tests/test_totp_matched_counter_security.py::test_m3_p1_reproduce_cross_window_verify_replay",
        "-q",
        "--no-cov",
    ]
    proc = subprocess.run(cmd, cwd=ROOT.parent, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
