# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authoritative LOCAL in-process MCP handler benchmarks for all production tools.

Derives tool names from PRODUCTION_TOOL_DEFS — no hard-coded obsolete lists.
"""

from __future__ import annotations

import asyncio
import platform
import statistics
import sys
import time
from typing import Any

sys.path.insert(0, "src")

from responsibleai.mcp.tools import PRODUCTION_TOOL_DEFS, TEST_TOOL_NAME, dispatch_tool

# Minimal valid payloads for dispatch (in-process; external HTTP may still occur).
_MINIMAL: dict[str, dict[str, Any]] = {
    "rai_scan": {"text": "benchmark sample text"},
    "rai_trust_score": {},
    "rai_compliance": {},
    "rai_hallucination": {"text": "The capital of France is Paris."},
    "rai_cost_estimate": {
        "model": "gpt-4o",
        "provider": "openai",
        "input_tokens": 100,
        "output_tokens": 50,
    },
    "rai_redteam_payloads": {},
    "rai_redteam_analyze": {
        "model_name": "bench",
        "provider": "bench",
        "responses": {"prompt_injection": "I cannot help with that."},
    },
    "rai_compare_models": {
        "model_a": "a",
        "provider_a": "openai",
        "model_b": "b",
        "provider_b": "openai",
    },
    "rai_audit_summary": {},
    "rai_health": {},
    "rai_bias_evaluate": {
        "model_name": "m",
        "provider": "p",
        "probe_responses": {"gender": ["yes", "yes"]},
    },
    "rai_drift_check": {
        "model_name": "m",
        "provider": "p",
        "baseline_score": {"overall": 0.8},
        "current_score": {"overall": 0.75},
    },
    "rai_passport_generate": {
        "model_name": "m",
        "provider": "p",
        "trust_dimensions": {
            "fairness": 0.8,
            "privacy": 0.8,
            "security": 0.8,
            "robustness": 0.8,
            "compliance": 0.8,
            "authenticity": 0.8,
        },
    },
    "rai_budget_check": {"total_spent_usd": 100.0},
    "rai_policy_check": {"text": "hello world", "policy": {}},
    "rai_stream_scan": {"chunks": ["hello"]},
    "rai_benchmark": {"suite": "quick"},
    "rai_benchmark_prompts": {},
    "rai_model_route": {"task": "general", "budget_usd": 1.0},
    "rai_pii_report": {"texts": ["no pii here"]},
    "rai_incident_log": {
        "incident_type": "other",
        "severity": "low",
        "model_name": "m",
        "provider": "p",
        "description": "bench",
    },
    "rai_eu_ai_act_classify": {"system_description": "general assistant"},
    "rai_iso42001_gap": {},
    "rai_executive_summary": {},
    "rai_org_status": {},
    "rai_webhook_status": {},
    "rai_check_trust": {"model_name": "gpt-4o", "provider": "openai"},
    "rai_memory_write_check": {"content": "remember this"},
    "rai_memory_read_check": {"memory_scope": "session"},
    "rai_causal_influence_check": {
        "provenance": [{"kind": "human", "source_id": "user-1"}],
    },
}

_EXTERNAL = frozenset({"rai_check_trust", "rai_org_status", "rai_webhook_status"})


async def _bench_tool(name: str, n: int = 200) -> dict[str, Any]:
    args = _MINIMAL.get(name, {})

    async def once() -> None:
        await dispatch_tool(name, args)

    for _ in range(min(20, n)):
        await once()
    samples: list[float] = []
    for _ in range(n):
        s = time.perf_counter()
        await once()
        samples.append((time.perf_counter() - s) * 1000)
    samples.sort()
    return {
        "tool": name,
        "n": n,
        "mean_ms": statistics.mean(samples),
        "p50_ms": samples[len(samples) // 2],
        "p95_ms": samples[int(len(samples) * 0.95)],
        "p99_ms": samples[int(len(samples) * 0.99)],
        "max_ms": max(samples),
        "external_dependency": name in _EXTERNAL,
    }


async def main() -> None:
    names = [t.name for t in PRODUCTION_TOOL_DEFS if t.name != TEST_TOOL_NAME]
    print(f"ENV: LOCAL in-process  Python={sys.version.split()[0]}  Platform={platform.platform()}")
    print(f"TOOLS: {len(names)} production tools from PRODUCTION_TOOL_DEFS")
    print("| tool | n | mean | p50 | p95 | p99 | max | external |")
    print("|---|---:|---:|---:|---:|---:|---:|---|")
    rows = []
    for name in sorted(names):
        try:
            row = await _bench_tool(name, n=150 if name in _EXTERNAL else 300)
            rows.append(row)
            print(
                f"| {row['tool']} | {row['n']} | {row['mean_ms']:.3f} | {row['p50_ms']:.3f} | "
                f"{row['p95_ms']:.3f} | {row['p99_ms']:.3f} | {row['max_ms']:.3f} | "
                f"{'yes' if row['external_dependency'] else 'no'} |"
            )
        except Exception as exc:
            print(f"| {name} | — | ERROR | — | — | — | — | — | ({exc})")
    under_half = sum(1 for r in rows if r["p95_ms"] < 0.5)
    print(
        f"\nSummary: {under_half}/{len(rows)} tools p95 < 0.5 ms (in-process LOCAL; not production SLA)"
    )


if __name__ == "__main__":
    asyncio.run(main())
