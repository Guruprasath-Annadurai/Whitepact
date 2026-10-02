# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 — integrated RC regression entry points (no SHA claim without green CI)."""

from __future__ import annotations

from pathlib import Path


def test_m5_attack_and_authority_regression_suites_present() -> None:
    root = Path(__file__).resolve().parent
    suites = [
        "test_governance_api.py",
        "test_mcp_ws2_upstream_reconciliation.py",
        "test_v1_exactly_one_effect.py",
        "test_web_invitations_adversarial.py",
        "test_siem_audit_export.py",
    ]
    for name in suites:
        assert (root / name).is_file(), name
