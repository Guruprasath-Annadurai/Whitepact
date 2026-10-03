# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 engineering gate index — plan-only cloud + enterprise hardening suites."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

M4_SUITE_FILES: tuple[str, ...] = (
    "test_auth_real_postgres.py",
    "test_scim_and_session_lifecycle.py",
    "test_restore_admission_chokepoint.py",
    "test_siem_audit_export.py",
    "test_siem_delivery_m3.py",
    "test_m4_audit_export_batch_smoke.py",
)

M4_SUITE_FILES_WS5: tuple[str, ...] = M4_SUITE_FILES + ("test_terraform_m4_validate.py",)


def test_m4_required_suites_present() -> None:
    for name in M4_SUITE_FILES:
        assert (ROOT / name).is_file(), f"missing M4 suite: {name}"


def test_m4_terraform_validate_suite_present() -> None:
    """Plan-only terraform validate ships on the qualified M4 successor stack."""
    assert (ROOT / "test_terraform_m4_validate.py").is_file()
