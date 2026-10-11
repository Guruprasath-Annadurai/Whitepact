# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Measure the in-process authorization kernel. This is not an HTTP SLO.

The script keeps guardrails, authority checks, and decision assertions
enabled. It does not start a database, HTTP server, or MCP transport.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import time
from pathlib import Path

from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
)


def _percentile(samples: list[float], pct: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index] * 1000.0


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=2000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gateway = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="bench", kind="api_key", org_id="org-bench")
    agent = AgentContext(identity=identity, framework="bench")
    allowed = AuthorityContext(
        delegated_by="org-bench",
        granted_action_types=frozenset({"mcp_tool_call"}),
    )
    allow_samples: list[float] = []
    deny_samples: list[float] = []
    allow_ok = 0
    deny_ok = 0
    started = time.perf_counter()
    for _ in range(args.iterations):
        action = ActionRequest(
            agent=agent,
            action_type="mcp_tool_call",
            target="rai_health",
            arguments={"query": "hello"},
        )
        t0 = time.perf_counter()
        result = gateway.evaluate(action, allowed)
        allow_samples.append(time.perf_counter() - t0)
        if result.decision == GovernanceDecision.ALLOW:
            allow_ok += 1
        denied = ActionRequest(agent=agent, action_type="payment", target="stripe")
        t1 = time.perf_counter()
        denied_result = gateway.evaluate(denied, allowed)
        deny_samples.append(time.perf_counter() - t1)
        if denied_result.decision == GovernanceDecision.DENY:
            deny_ok += 1
    elapsed = time.perf_counter() - started
    usage = resource.getrusage(resource.RUSAGE_SELF)
    calls = args.iterations * 2
    report = {
        "workload": "in-process WhitePactRuntimeGateway.evaluate",
        "not_an_http_slo": True,
        "not_an_mcp_slo": True,
        "security_checks_disabled": False,
        "iterations_per_decision": args.iterations,
        "allow_decisions_correct": allow_ok,
        "deny_decisions_correct": deny_ok,
        "decision_errors": calls - allow_ok - deny_ok,
        "allow_p50_ms": round(_percentile(allow_samples, 50), 4),
        "allow_p95_ms": round(_percentile(allow_samples, 95), 4),
        "allow_p99_ms": round(_percentile(allow_samples, 99), 4),
        "deny_p50_ms": round(_percentile(deny_samples, 50), 4),
        "deny_p95_ms": round(_percentile(deny_samples, 95), 4),
        "deny_p99_ms": round(_percentile(deny_samples, 99), 4),
        "calls": calls,
        "elapsed_seconds": round(elapsed, 4),
        "calls_per_second": round(calls / elapsed, 1) if elapsed else 0,
        "concurrent_users": 1,
        "tenants": 1,
        "database": "none",
        "replicas": 1,
        "cpu_user_seconds": round(usage.ru_utime, 4),
        "cpu_system_seconds": round(usage.ru_stime, 4),
        "max_rss_kb": usage.ru_maxrss,
        "error_rate": 0 if allow_ok + deny_ok == calls else 1,
        "source_commit": _git(["rev-parse", "HEAD"]),
        "source_tree": _git(["rev-parse", "HEAD^{tree}"]),
        "reproduction": "python scripts/bench_authorization_layers.py --output <path>",
        "slo_status": "NOT_APPROVED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if allow_ok != args.iterations or deny_ok != args.iterations:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
