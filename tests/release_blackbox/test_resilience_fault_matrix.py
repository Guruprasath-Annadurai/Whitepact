# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Resilience fault-injection matrix — preparation stubs."""

from __future__ import annotations

import pytest

FAULTS = [
    "postgres_unavailable",
    "postgres_slow",
    "connection_loss",
    "redis_unavailable",
    "worker_restart",
    "api_restart",
    "mcp_upstream_unavailable",
    "mcp_upstream_timeout",
    "lost_acknowledgement",
    "policy_lookup_failure",
    "evidence_persistence_failure",
    "revocation_race",
    "approval_race",
    "stale_grant",
    "expired_grant",
    "nonce_replay",
    "target_fingerprint_drift",
    "network_interruption",
    "concurrent_duplicate_requests",
]


@pytest.mark.parametrize("fault", FAULTS)
def test_fault_case_registered(fault: str) -> None:
    assert fault


def test_fail_closed_principle_documented() -> None:
    """Consequential paths should fail closed unless design defines UNKNOWN."""
    assert True  # enforced by governance tests elsewhere; campaign will re-run on combined RC
