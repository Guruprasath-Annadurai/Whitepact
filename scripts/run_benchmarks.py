"""Real, locally-executed performance benchmarks for BENCHMARKS.md.

Not a synthetic/theoretical estimate — every number in BENCHMARKS.md is
copy-pasted from an actual run of this script. Re-run and update both files
together if a change in this repo could plausibly move these numbers.

Usage: python scripts/run_benchmarks.py
"""

from __future__ import annotations

import platform
import statistics
import sys
import time

sys.path.insert(0, "src")

from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
)
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.mcp.tools import TOOL_DEFS
from responsibleai.trust.score import TrustScoreEngine


def bench(name: str, fn, n: int) -> None:
    # Warm up (import caches, any lazy compilation) before timing.
    for _ in range(min(50, n)):
        fn()

    samples = []
    start_all = time.perf_counter()
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)  # ms
    total = time.perf_counter() - start_all

    samples.sort()
    p50 = samples[len(samples) // 2]
    p95 = samples[int(len(samples) * 0.95)]
    p99 = samples[int(len(samples) * 0.99)]
    mean = statistics.mean(samples)
    print(f"| `{name}` | {n} | {mean:.4f} | {p50:.4f} | {p95:.4f} | {p99:.4f} | {n / total:.0f} |")


def main() -> None:
    print(f"Python: {sys.version.split()[0]}  Platform: {platform.platform()}")
    print()
    print("| Operation | N | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | ops/sec |")
    print("|---|---|---|---|---|---|---|")

    guardrails = GuardrailsEngine()
    clean_text = "The quarterly report shows revenue grew 12% year over year."
    pii_text = "Customer SSN is 123-45-6789, email alice@example.com, call 555-123-4567."
    bench("GuardrailsEngine.scan (clean text)", lambda: guardrails.scan(clean_text), 2000)
    bench("GuardrailsEngine.scan (PII text)", lambda: guardrails.scan(pii_text), 2000)

    trust_engine = TrustScoreEngine()
    bench(
        "TrustScoreEngine.compute (6 dimensions)",
        lambda: trust_engine.compute(
            fairness=0.80, privacy=0.85, security=0.82,
            robustness=0.78, compliance=0.90, authenticity=0.88,
        ),
        5000,
    )

    gateway = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="bench-org", kind="api_key")
    agent = AgentContext(identity=identity, organization_id="bench-org")
    authority = AuthorityContext(
        delegated_by="bench-org",
        granted_action_types=frozenset({"rai_scan"}),
    )
    action = ActionRequest(
        agent=agent,
        action_type="rai_scan",
        target="rai_scan",
        arguments={"text": clean_text},
    )
    bench(
        "WhitePactRuntimeGateway.evaluate (LOW-risk, allowed)",
        lambda: gateway.evaluate(action=action, authority=authority),
        2000,
    )

    action_pii = ActionRequest(
        agent=agent,
        action_type="rai_scan",
        target="rai_scan",
        arguments={"text": pii_text},
    )
    bench(
        "WhitePactRuntimeGateway.evaluate (LOW-risk, PII redaction path)",
        lambda: gateway.evaluate(action=action_pii, authority=authority),
        2000,
    )

    denied_authority = AuthorityContext(
        delegated_by="bench-org",
        granted_action_types=frozenset(),
    )
    bench(
        "WhitePactRuntimeGateway.evaluate (authority DENY, short-circuit)",
        lambda: gateway.evaluate(action=action, authority=denied_authority),
        2000,
    )

    bench("MCP TOOL_DEFS lookup by name (27 tools)", lambda: next(t for t in TOOL_DEFS if t.name == "rai_check_trust"), 5000)


if __name__ == "__main__":
    main()
