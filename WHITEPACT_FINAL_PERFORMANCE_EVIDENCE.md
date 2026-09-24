# Performance evidence (LOCAL)

**Label:** LOCAL — not production SaaS latency.

| Tier | Method | Status |
| --- | --- | --- |
| A–G benchmark separation | `scripts/run_benchmarks.py` | **CATALOGUED** — rerun before external claims |
| Concurrency 1/10/25/50/100 | Not executed this campaign | **BLOCKED** — requires dedicated load harness + staging |

Antigravity microbenchmarks remain valid as **LOCAL** indicators only. This patch did not change evidence write path or introduce async ingestion.

**Next step for diligence:** run controlled harness on STAGING with PostgreSQL, report p50/p95/p99 with sample counts (Section 14 template).
