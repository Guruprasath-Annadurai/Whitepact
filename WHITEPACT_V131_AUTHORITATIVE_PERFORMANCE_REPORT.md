# Authoritative performance report (v1.3.1 RC)

**Environment label:** LOCAL in-process (Linux cloud agent VM, Python 3.12.3)  
**Not:** production, staging, or enterprise-scale throughput.

**Tool source:** `PRODUCTION_TOOL_DEFS` via `scripts/run_v131_production_tool_benchmarks.py`  
**Date:** 2026-09-24 (agent run)

## Tier A — local in-process MCP `dispatch_tool` (all 30 production tools)

| tool | n | mean (ms) | p50 | p95 | p99 | max | external HTTP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rai_audit_summary | 300 | 0.004 | 0.004 | 0.005 | 0.012 | 0.017 | no |
| rai_benchmark | 300 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | no |
| rai_benchmark_prompts | 300 | 0.003 | 0.003 | 0.003 | 0.005 | 0.010 | no |
| rai_bias_evaluate | 300 | 0.017 | 0.016 | 0.022 | 0.036 | 0.037 | no |
| rai_budget_check | 300 | 0.005 | 0.005 | 0.005 | 0.005 | 0.011 | no |
| rai_causal_influence_check | 300 | 0.004 | 0.004 | 0.004 | 0.004 | 0.004 | no |
| **rai_check_trust** | 150 | **71.403** | **66.837** | **100.590** | **110.365** | **119.652** | **yes** |
| rai_compare_models | 300 | 0.019 | 0.019 | 0.020 | 0.024 | 0.028 | no |
| rai_compliance | 300 | 0.034 | 0.034 | 0.039 | 0.050 | 0.052 | no |
| rai_cost_estimate | 300 | 0.005 | 0.005 | 0.005 | 0.005 | 0.006 | no |
| rai_drift_check | 300 | 0.009 | 0.009 | 0.009 | 0.010 | 0.019 | no |
| rai_eu_ai_act_classify | 300 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | no |
| rai_executive_summary | 300 | 0.006 | 0.006 | 0.006 | 0.006 | 0.012 | no |
| **rai_hallucination** | 300 | 0.017 | 0.016 | 0.022 | 0.027 | 0.033 | no |
| rai_health | 300 | 0.001 | 0.001 | 0.002 | 0.002 | 0.002 | no |
| rai_incident_log | 300 | 0.010 | 0.010 | 0.010 | 0.010 | 0.072 | no |
| rai_iso42001_gap | 300 | 0.006 | 0.006 | 0.007 | 0.007 | 0.007 | no |
| rai_memory_read_check | 300 | 0.002 | 0.002 | 0.002 | 0.002 | 0.002 | no |
| rai_memory_write_check | 300 | 0.004 | 0.004 | 0.004 | 0.004 | 0.011 | no |
| rai_model_route | 300 | 0.001 | 0.001 | 0.002 | 0.002 | 0.013 | no |
| **rai_org_status** | 150 | 0.005 | 0.005 | 0.005 | 0.005 | 0.005 | yes |
| rai_passport_generate | 300 | 0.028 | 0.027 | 0.034 | 0.038 | 0.049 | no |
| rai_pii_report | 300 | 0.009 | 0.009 | 0.010 | 0.010 | 0.018 | no |
| rai_policy_check | 300 | 0.008 | 0.008 | 0.009 | 0.011 | 0.012 | no |
| rai_redteam_analyze | 300 | 0.007 | 0.007 | 0.009 | 0.011 | 0.016 | no |
| rai_redteam_payloads | 300 | 0.004 | 0.004 | 0.004 | 0.004 | 0.004 | no |
| rai_scan | 300 | 0.008 | 0.008 | 0.009 | 0.009 | 0.021 | no |
| rai_stream_scan | 300 | 0.003 | 0.003 | 0.004 | 0.004 | 0.004 | no |
| rai_trust_score | 300 | 0.008 | 0.008 | 0.008 | 0.009 | 0.014 | no |
| rai_webhook_status | 150 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 | yes |

**Summary (measured):** 29/30 tools have p95 &lt; 0.5 ms in this LOCAL in-process harness.  
**Exception:** `rai_check_trust` is network-bound (~100 ms p95) to the configured Trust Index HTTP endpoint.

## Tiers B–D

| Tier | Status |
| --- | --- |
| B DB-backed governance | Not re-benchmarked in this closure pass (see `scripts/run_benchmarks.py` for SQLite audit write baseline) |
| C External network (trust) | Measured only via `rai_check_trust` row above |
| D HTTP governance path | **STAGING PERFORMANCE NOT YET PROVEN** |

## Expensive tools (by measurement)

1. **`rai_check_trust`** — dominant latency (external HTTP).  
2. **`rai_hallucination`** — higher than median in-process (~0.02 ms p95) but not network-tier.  
3. **`rai_org_status`** — flagged external-capable; measured fast in-process (no live org backend in harness).
