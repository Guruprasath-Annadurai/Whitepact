# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M3 focused adversarial security matrix (P1-02..P1-07, BLK-P0-05)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

M3_CAMPAIGN: list[tuple[str, str]] = [
    ("invitation replay / wrong tenant", "tests/test_web_invitations_adversarial.py"),
    ("SDK governance contract matrix", "tests/test_sdk_governance_contract_matrix.py"),
    ("SDK reconciliation UNKNOWN", "tests/test_sdk_governance_reconciliation_m3.py"),
    ("Paddle sandbox matrix", "tests/test_paddle_sandbox_matrix_m3.py"),
    ("package identity BLK-P0-05", "tests/test_package_identity_m3.py"),
    ("break-glass runtime", "tests/test_break_glass_runtime_m3.py"),
    ("SIEM export", "tests/test_siem_audit_export.py"),
    ("SIEM delivery outage", "tests/test_siem_delivery_m3.py"),
    ("account lifecycle P1-07", "tests/test_web_account_lifecycle_m3.py"),
    ("legacy static BYPASS regression", "tests/test_ws3_unified_saas_legacy_frontend.py"),
    ("static surface inventory", "tests/test_ws3_static_surface_inventory.py"),
    (
        "forged grant / replay (M1 guard)",
        "tests/test_mcp_ws2_authority_matrix.py::TestGrantBindingAndReplayMatrix::test_replayed_authorization_refused",
    ),
    (
        "cross-tenant grant refused",
        "tests/test_mcp_ws2_authority_matrix.py::TestGrantBindingAndReplayMatrix::test_cross_tenant_grant_refused",
    ),
    ("web policy P1-01 guard", "tests/test_web_policy_management.py"),
]


@pytest.mark.parametrize("theme,node", M3_CAMPAIGN, ids=[c[0] for c in M3_CAMPAIGN])
def test_m3_adversarial_campaign_slice(theme: str, node: str) -> None:
    path = ROOT / node.split("::")[0]
    assert path.is_file(), f"missing M3 campaign file: {node}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-cov", "--tb=line"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, (
        f"M3 campaign [{theme}] failed for {node}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
