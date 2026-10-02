# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 cross-module authority regression campaign (fail-closed matrix index)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Each entry: human theme → pytest node path(s) or file (run whole file).
CAMPAIGN: list[tuple[str, str]] = [
    ("revoked delegation / break-glass", "tests/test_break_glass_runtime_m3.py"),
    (
        "governance API revoke cascade",
        "tests/test_governance_api.py::TestDelegationEndpoints::test_admin_revokes_cascades_to_descendants",
    ),
    (
        "cross-tenant grant refused",
        "tests/test_mcp_ws2_authority_matrix.py::TestGrantBindingAndReplayMatrix::test_cross_tenant_grant_refused",
    ),
    (
        "replayed authorization",
        "tests/test_mcp_ws2_authority_matrix.py::TestGrantBindingAndReplayMatrix::test_replayed_authorization_refused",
    ),
    ("upstream UNKNOWN reconciliation", "tests/test_mcp_ws2_upstream_reconciliation.py"),
    ("web UNKNOWN contract", "tests/test_v1_web_contract_closure.py"),
    ("exactly-one-effect UNKNOWN", "tests/test_v1_exactly_one_effect.py"),
    ("cross-tenant org admin", "tests/test_tenant_isolation_org_admin.py"),
    ("cross-tenant webhooks", "tests/test_tenant_isolation_webhooks.py"),
    ("trust IAM cross-tenant", "tests/test_trust_iam_admission.py::test_cross_tenant_trust_decision_blocked"),
    ("invitation replay", "tests/test_web_invitations_adversarial.py::test_invitation_wrong_email_and_replay"),
    ("role downgrade session", "tests/test_web_invitations_adversarial.py::test_role_downgrade_revokes_member_session"),
    ("SCIM/session lifecycle", "tests/test_scim_and_session_lifecycle.py"),
    ("SIEM export tenant scope", "tests/test_siem_audit_export.py"),
    ("SIEM delivery retries", "tests/test_siem_delivery_m3.py"),
    ("account lifecycle", "tests/test_web_account_lifecycle_m3.py"),
    ("SDK governance contract", "tests/test_sdk_governance_contract_matrix.py"),
    ("Paddle canonical seams", "tests/test_auth_canonical_seams.py"),
    ("package wheel smoke", "tests/test_package_identity_m3.py"),
    ("evidence write fail-closed", "tests/test_mcp_ws2_failclosed_dependency_matrix.py"),
    ("MCP evidence persistence", "tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed"),
    ("runtime isolation evidence", "tests/test_runtime_isolation_hardgate.py"),
]


@pytest.mark.parametrize("theme,node", CAMPAIGN, ids=[c[0] for c in CAMPAIGN])
def test_m5_campaign_slice(theme: str, node: str) -> None:
    """Run one campaign slice; failures must be fixed before M5 exact-head gate."""
    path = ROOT / node.split("::")[0]
    assert path.is_file(), f"missing campaign file: {node}"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "--no-cov", "--tb=line"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, (
        f"M5 campaign [{theme}] failed for {node}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
