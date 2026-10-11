#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Authority Challenge: twelve scenarios, each mapped to the real tests that observe the effect.

This runner does not fake anything. For each scenario it runs the named pytest nodes (real HTTP app,
real PostgreSQL where the node needs it, real containers where the node needs them) and reports:

* PASS     every node passed and none was skipped;
* FAIL     any node failed or errored;
* BLOCKED  a node was skipped (for example no Docker/Linux for the container scenario) or the environment
           it needs is missing. A skip is never a pass.

Each node asserts the *absence of the unauthorized side effect* (the effect counter, the approval/evidence
rows, the container's network), not just a refusal status.

    WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:55433/postgres \
        python scripts/authority_challenge.py --out authority-challenge.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

SCENARIOS: list[tuple[int, str, list[str]]] = [
    (
        1,
        "Authorized execution: a granted, approved action runs exactly once",
        [
            "tests/test_v1_exactly_one_effect.py::test_exactly_one_effect_approve_replay_deny_unknown"
        ],
    ),
    (
        2,
        "Unauthorized action is denied before any side effect",
        [
            "tests/test_transport_credential_negatives.py::test_a_read_only_key_cannot_request_a_consequential_action",
            "tests/test_agentic_adversarial.py::test_arguments_cannot_name_a_different_tenant_or_grant_themselves_authority",
        ],
    ),
    (
        3,
        "High-risk action is held until an authenticated, authorized human approves",
        [
            "tests/test_approval_adversarial.py::test_a_non_admin_cannot_resolve_or_execute",
            "tests/test_step_up_forged_proofs_http.py::test_a_genuine_enrolled_code_authorizes_the_action",
        ],
    ),
    (
        4,
        "Forged or altered approval cannot release execution",
        [
            "tests/test_approval_adversarial.py::test_an_approval_whose_bound_action_digest_was_altered_is_refused",
            "tests/test_step_up_forged_proofs_http.py::test_the_old_mock_totp_codes_do_not_authorize_an_unenrolled_user",
            "tests/test_executor_bypass_invariant.py::TestExecutorRefusesInvalidAuthorization::test_forged_authorization_with_correct_digest_still_bound_to_org",
        ],
    ),
    (
        5,
        "A consumed execution authorization cannot authorize a second execution",
        [
            "tests/test_executor_bypass_invariant.py::TestExecutorRefusesInvalidAuthorization::test_replay_is_refused",
            "tests/test_approval_adversarial.py::test_concurrent_execution_of_one_approval_runs_exactly_once",
        ],
    ),
    (
        6,
        "A revoked credential or authority cannot admit new execution",
        [
            "tests/test_transport_credential_negatives.py::test_revoking_the_requesting_key_while_an_approval_is_pending_blocks_the_effect",
            "tests/test_mcp_http_credential_negatives.py::test_revoking_the_key_mid_session_stops_the_next_tool_call",
        ],
    ),
    (
        7,
        "An approved action cannot execute under invalidated policy authority",
        [
            "tests/test_approval_adversarial.py::test_a_policy_change_after_approval_blocks_the_execution"
        ],
    ),
    (
        8,
        "One organization's identity or grant cannot authorize another organization's action",
        [
            "tests/test_transport_credential_negatives.py::test_another_tenant_cannot_resolve_or_execute_this_tenants_approval",
            "tests/test_transport_credential_negatives.py::test_another_tenant_cannot_read_or_annotate_this_tenants_evidence",
        ],
    ),
    (
        9,
        "Malicious agent text cannot expand independently enforced authority",
        ["tests/test_agentic_adversarial.py"],
    ),
    (
        10,
        "An agent cannot send data over a prohibited network path (real container, Linux)",
        [
            "tests/test_runtime_isolation_docker.py::TestProductionContainerAdversarial::test_container_network_containment"
        ],
    ),
    (
        11,
        "A retained trust reference detects an evidence/history rewrite or rollback",
        [
            "tests/test_policy_history.py::test_a_retained_checkpoint_defeats_a_complete_rewrite_that_recomputes_every_digest",
            "tests/test_policy_history_pg.py::test_version_rollback_is_caught_only_by_the_checkpoint_when_everything_is_reset",
            "tests/test_evidence_publication.py::test_rollback_rewrite_gap_and_missing_publication_are_detected",
        ],
    ),
    (
        12,
        "Protected execution fails closed when an enforcement dependency fails",
        [
            "tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed",
            "tests/test_mcp_ws2_authority_matrix.py::TestApplyGovernanceInfrastructureFailClosed",
        ],
    ),
]


def run(nodes: list[str]) -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-q",
        "-p",
        "no:cacheprovider",
        "-rsx",
        *nodes,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
    tail = proc.stdout + proc.stderr
    counts = {
        k: int(v)
        for v, k in re.findall(r"(\d+) (passed|failed|skipped|error|errors|deselected)", tail)
    }
    ran = counts.get("passed", 0)
    verdict = "PASS"
    if proc.returncode == 5 or "not found" in tail.lower() and ran == 0:
        verdict = "FAIL"  # a node that does not exist proves nothing
    if counts.get("failed") or counts.get("error") or counts.get("errors"):
        verdict = "FAIL"
    elif counts.get("skipped"):
        verdict = "BLOCKED"
    elif ran == 0:
        verdict = "FAIL"
    elif proc.returncode != 0:
        verdict = "FAIL"
    skips = [line for line in tail.splitlines() if line.startswith("SKIPPED")]
    return {"verdict": verdict, "counts": counts, "skips": skips[:3], "exit": proc.returncode}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", default="authority-challenge.json")
    parser.add_argument("--only", type=int, nargs="*")
    args = parser.parse_args()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()  # noqa: S603, S607
    results = []
    for number, title, nodes in SCENARIOS:
        if args.only and number not in args.only:
            continue
        outcome = run(nodes)
        results.append({"scenario": number, "title": title, "nodes": nodes, **outcome})
        print(f"[{outcome['verdict']:7}] {number:>2}. {title}  {outcome['counts']}", flush=True)
    report = {
        "source_commit": commit,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "pg_admin_url_set": bool(os.environ.get("WHITEPACT_TEST_PG_ADMIN_URL")),
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    bad = [r for r in results if r["verdict"] != "PASS"]
    print(
        f"{len(results) - len(bad)}/{len(results)} PASS; {len(bad)} not PASS (FAIL or BLOCKED stay visible)"
    )
    return 1 if any(r["verdict"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
