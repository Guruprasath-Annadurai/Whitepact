# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 integrated RC regression entry points."""

from __future__ import annotations

from pathlib import Path


def test_m5_integrated_rc_anchor_suites_present() -> None:
    root = Path(__file__).resolve().parent
    suites = [
        "test_m5_integrated_regression_campaign.py",
        "test_m4_hostile_regression_campaign.py",
        "test_m4_m123_regression_index.py",
        "test_mcp_ws2_authority_matrix.py",
        "test_totp_matched_counter_security.py",
        "test_siem_audit_export.py",
    ]
    for name in suites:
        assert (root / name).is_file(), name
