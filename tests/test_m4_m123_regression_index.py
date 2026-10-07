# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 gate — critical M1/M2/M3 regression anchors must remain present."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent

M1_M2_M3_ANCHORS: tuple[str, ...] = (
    "test_mcp_ws2_authority_matrix.py",
    "test_m3_adversarial_security_campaign.py",
    "test_totp_matched_counter_security.py",
    "test_web_invitations_adversarial.py",
    "test_sdk_governance_contract_matrix.py",
    "test_break_glass_runtime_m3.py",
    "test_siem_delivery_m3.py",
    "test_web_account_lifecycle_m3.py",
    "test_package_identity_m3.py",
)


def test_m123_regression_anchors_present() -> None:
    for name in M1_M2_M3_ANCHORS:
        assert (ROOT / name).is_file(), f"missing M1-M3 anchor: {name}"
