# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run the security-regression tests. A skip is a failure.

Source-text inclusion is a separate guardrail. This script executes the
tests. It does not treat a skipped test as a pass.
"""

from __future__ import annotations

import sys

NODES = [
    "tests/test_p0_tenant_admission.py::test_oidc_unknown_organization_is_rejected",
    "tests/test_p0_tenant_admission.py::test_saml_expired_session_is_rejected",
    "tests/test_saml_app_routes.py::TestSamlAcs::test_acs_unknown_tenant_does_not_mint_a_session",
    "tests/test_mcp_verified_principal.py::TestVerifiedPrincipalAuth::test_vc_unknown_org_leaves_no_principal_row",
    "tests/test_mcp_verified_principal.py::TestVerifiedPrincipalAuth::test_vc_unbound_existing_org_leaves_no_principal_row",
    "tests/test_runner_immutability.py::test_direct_backend_rejects_caller_runner",
    "tests/test_runner_immutability.py::test_broker_does_not_forward_workspace_files",
    "tests/test_launch_gate_isolation_runner.py::test_container_runner_fails_closed_when_runtime_is_missing",
    "tests/test_launch_gate_hosted_metering.py::test_governance_denial_does_not_consume_allowed_quota",
    "tests/test_launch_gate_resume_identity.py::test_resume_refuses_an_approval_with_no_requester",
    "tests/test_foundation_hardening.py::test_evidence_witness_binds_head_and_rejects_recomputed_rewrite",
    "tests/test_foundation_hardening.py::test_broad_allow_shadowing_later_deny_is_rejected",
    "tests/test_evidence_publication.py::test_rollback_rewrite_gap_and_missing_publication_are_detected",
]


def main() -> int:
    import pytest

    skipped: list[str] = []

    class _RefuseSkips:
        def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
            if report.skipped:
                skipped.append(report.nodeid)

    status = pytest.main(
        ["-o", "addopts=", "-q", "--tb=line", *NODES],
        plugins=[_RefuseSkips()],
    )
    if skipped:
        sys.stderr.write("security regression tests skipped:\n")
        for node in skipped:
            sys.stderr.write(f"  {node}\n")
        return 1
    if status != 0:
        return int(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
