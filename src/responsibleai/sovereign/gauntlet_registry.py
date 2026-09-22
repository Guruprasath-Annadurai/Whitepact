# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Registered adversarial probes — pytest node ids only (no copied test logic)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProbeRuntime(StrEnum):
    IN_MEMORY = "in_memory"
    POSTGRES = "postgres"
    MCP_LIVE = "mcp_live"


@dataclass(frozen=True)
class GauntletProbe:
    test_id: str
    attack_family: str
    pytest_nodeid: str
    expected_control: str
    runtime: ProbeRuntime = ProbeRuntime.IN_MEMORY
    diagnostic_hint: str = ""


GAUNTLET_PROBES: tuple[GauntletProbe, ...] = (
    GauntletProbe(
        test_id="matrix_cross_tenant_trace",
        attack_family="cross-tenant access",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_cross_tenant_trace_denied",
        expected_control="tenant isolation on trace",
    ),
    GauntletProbe(
        test_id="matrix_cross_tenant_simulation",
        attack_family="cross-tenant access",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_cross_tenant_blast_radius_denied",
        expected_control="tenant isolation on simulation",
    ),
    GauntletProbe(
        test_id="matrix_simulation_no_grant_mint",
        attack_family="capability escalation",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_simulation_cannot_mint_grant",
        expected_control="simulation does not create execution grants",
    ),
    GauntletProbe(
        test_id="matrix_simulation_no_consequential_counter",
        attack_family="duplicate consequential execution",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_simulation_no_consequential_counter",
        expected_control="simulation does not increment consequential boundary",
    ),
    GauntletProbe(
        test_id="matrix_capsule_reproduce_zero_effect",
        attack_family="replay",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_capsule_reproduce_zero_effect",
        expected_control="capsule reproduce is zero-effect",
    ),
    GauntletProbe(
        test_id="matrix_manifest_no_grant",
        attack_family="policy drift",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_manifest_cannot_grant_authority",
        expected_control="manifest compare does not widen authority",
    ),
    GauntletProbe(
        test_id="matrix_graph_budget",
        attack_family="transitive authority escalation",
        pytest_nodeid="tests/sovereign/test_security_matrix.py::test_graph_depth_budget_enforced",
        expected_control="graph traversal respects depth budget",
    ),
    GauntletProbe(
        test_id="tenant_guard",
        attack_family="wrong organization",
        pytest_nodeid="tests/sovereign/test_tenant.py::test_cross_tenant_denied_without_disclosure",
        expected_control="cross-tenant resource access denied",
    ),
    GauntletProbe(
        test_id="p7a_cross_tenant",
        attack_family="cross-tenant access",
        pytest_nodeid="tests/test_phase7a_authority_kernel.py::test_cross_tenant_forbidden",
        expected_control="authority kernel rejects cross-tenant caller",
        runtime=ProbeRuntime.POSTGRES,
    ),
    GauntletProbe(
        test_id="p7a_duplicate_effect",
        attack_family="duplicate consequential execution",
        pytest_nodeid=(
            "tests/test_phase7a_authority_kernel.py::test_duplicate_queue_tickets_do_not_duplicate_effects"
        ),
        expected_control="duplicate queue tickets do not duplicate effects",
        runtime=ProbeRuntime.POSTGRES,
    ),
    GauntletProbe(
        test_id="p7a_stale_worker",
        attack_family="stale grant",
        pytest_nodeid="tests/test_phase7a_authority_kernel.py::test_stale_worker_and_fence",
        expected_control="stale worker rejected at pre-effect CAS",
        runtime=ProbeRuntime.POSTGRES,
    ),
    GauntletProbe(
        test_id="p7a_wrong_fingerprint",
        attack_family="target drift",
        pytest_nodeid="tests/test_phase7a_authority_kernel.py::test_wrong_digest_and_fingerprint",
        expected_control="target fingerprint mismatch rejected",
        runtime=ProbeRuntime.POSTGRES,
    ),
    GauntletProbe(
        test_id="whitepact_live_gauntlet",
        attack_family="governance epoch drift",
        pytest_nodeid="tests/test_whitepact_gauntlet.py::TestWhitePactGauntlet::test_full_gauntlet",
        expected_control="live governed MCP gauntlet invariants",
        runtime=ProbeRuntime.MCP_LIVE,
        diagnostic_hint="Requires MCP governance app fixture",
    ),
)
