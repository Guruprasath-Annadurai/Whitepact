# Authoritative MCP performance (v1.3.1 9.5 closure)

Environment: LOCAL in-process (script `run_v131_production_tool_benchmarks.py`)

Exit code: 0

```
ENV: LOCAL in-process  Python=3.12.3  Platform=Linux-6.12.94+-x86_64-with-glibc2.39
TOOLS: 30 production tools from PRODUCTION_TOOL_DEFS
| tool | n | mean | p50 | p95 | p99 | max | external |
|---|---:|---:|---:|---:|---:|---:|---|
| rai_audit_summary | 300 | 0.004 | 0.004 | 0.005 | 0.005 | 0.006 | no |
| rai_benchmark | 300 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | no |
| rai_benchmark_prompts | 300 | 0.003 | 0.003 | 0.003 | 0.003 | 0.004 | no |
| rai_bias_evaluate | 300 | 0.016 | 0.016 | 0.016 | 0.017 | 0.024 | no |
| rai_budget_check | 300 | 0.004 | 0.004 | 0.005 | 0.005 | 0.005 | no |
| rai_causal_influence_check | 300 | 0.004 | 0.004 | 0.004 | 0.005 | 0.013 | no |
| rai_check_trust | 150 | 54.614 | 53.520 | 67.756 | 85.509 | 97.786 | yes |
| rai_compare_models | 300 | 0.019 | 0.019 | 0.020 | 0.028 | 0.041 | no |
| rai_compliance | 300 | 0.033 | 0.033 | 0.034 | 0.039 | 0.042 | no |
| rai_cost_estimate | 300 | 0.005 | 0.005 | 0.005 | 0.005 | 0.011 | no |
| rai_drift_check | 300 | 0.009 | 0.009 | 0.009 | 0.009 | 0.014 | no |
| rai_eu_ai_act_classify | 300 | 0.001 | 0.001 | 0.001 | 0.001 | 0.001 | no |
| rai_executive_summary | 300 | 0.006 | 0.006 | 0.006 | 0.006 | 0.006 | no |
| rai_hallucination | 300 | 0.016 | 0.016 | 0.017 | 0.018 | 0.031 | no |
| rai_health | 300 | 0.001 | 0.001 | 0.002 | 0.002 | 0.008 | no |
| rai_incident_log | 300 | 0.010 | 0.010 | 0.010 | 0.011 | 0.028 | no |
| rai_iso42001_gap | 300 | 0.006 | 0.006 | 0.007 | 0.007 | 0.024 | no |
| rai_memory_read_check | 300 | 0.002 | 0.002 | 0.002 | 0.002 | 0.002 | no |
| rai_memory_write_check | 300 | 0.004 | 0.004 | 0.004 | 0.005 | 0.010 | no |
| rai_model_route | 300 | 0.001 | 0.001 | 0.001 | 0.002 | 0.002 | no |
| rai_org_status | 150 | 0.004 | 0.004 | 0.005 | 0.005 | 0.005 | yes |
| rai_passport_generate | 300 | 0.026 | 0.026 | 0.027 | 0.029 | 0.036 | no |
| rai_pii_report | 300 | 0.010 | 0.010 | 0.010 | 0.011 | 0.017 | no |
| rai_policy_check | 300 | 0.008 | 0.008 | 0.009 | 0.009 | 0.015 | no |
| rai_redteam_analyze | 300 | 0.007 | 0.007 | 0.008 | 0.008 | 0.015 | no |
| rai_redteam_payloads | 300 | 0.004 | 0.004 | 0.004 | 0.004 | 0.004 | no |
| rai_scan | 300 | 0.008 | 0.008 | 0.009 | 0.009 | 0.015 | no |
| rai_stream_scan | 300 | 0.003 | 0.003 | 0.004 | 0.004 | 0.004 | no |
| rai_trust_score | 300 | 0.008 | 0.008 | 0.008 | 0.009 | 0.015 | no |
| rai_webhook_status | 150 | 0.003 | 0.003 | 0.003 | 0.003 | 0.003 | yes |

Summary: 29/30 tools p95 < 0.5 ms (in-process LOCAL; not production SLA)

```
