# Authorization latency over real HTTP + PostgreSQL (measurement, not an SLO)

Harness: `scripts/bench_http_authorization.py`. Raw data: `docs/launch/evidence/bench-http-authorization-2026-10-10.json`
(includes source commit and hardware). One run, one machine, 2026-10-10.

## Conditions (read these before the numbers)

* Server: one `uvicorn` worker (separate process) serving the dashboard application over loopback TCP, API-key
  authenticated, against a disposable migrated PostgreSQL 16 in Docker Desktop on the same Mac. Apple M4, Python 3.12.
* The load generator (asyncio + httpx) ran on the **same machine**; client and server compete for cores.
* **Not included:** TLS, reverse proxy, more than one worker or replica, a database on another host, governed execution
  in a container (the workloads stop before execution), MCP transport, a Python 3.11 run.
* The per-route slowapi limit was switched off for these runs. With it on, one organization is capped at **30
  governed calls per minute per route regardless of plan** (observed: 80 of 100 sequential reads returned 429).
  That contradicts the plan table (ENTERPRISE "unlimited") and is recorded as register finding REC-28, not fixed here.
* Workloads: `authenticated read` (API key → tenant → counter read); `DENY` (no delegated authority → decision +
  durable evidence write); `REQUIRE_APPROVAL` (policy match → decision + evidence + approval row).
* Request count per workload per level: 400 (levels 1, 10, 100), 3000 (level 1000).

## Correctness, measured with the latency

* **Unauthorized effects: 0** (the consequential counter never moved).
* Approval rows created equalled the number of REQUIRE_APPROVAL responses at every level that completed
  (400/400 at 1, 10 and 100; 970/970 at 1000 where the other requests never connected).
* 3,990 evidence rows were written for the organization, with no 5xx response at any level.

## Results

| Concurrency | Workload | OK / sent | Throughput (req/s) | p50 ms | p95 ms | p99 ms |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | read | 400/400 | 57 | 16 | 25 | 34 |
| 1 | DENY | 400/400 | 35 | 27 | 37 | 54 |
| 1 | REQUIRE_APPROVAL | 400/400 | 17 | 56 | 69 | 82 |
| 10 | read | 400/400 | 167 | 51 | 133 | 204 |
| 10 | DENY | 400/400 | 86 | 101 | 207 | 359 |
| 10 | REQUIRE_APPROVAL | 400/400 | 45 | 213 | 328 | 353 |
| 100 | read | 400/400 | 77 | 916 | 2,017 | 2,477 |
| 100 | DENY | 400/400 | 60 | 1,254 | 3,925 | 4,275 |
| 100 | REQUIRE_APPROVAL | 400/400 | 37 | 1,908 | 7,139 | 7,979 |
| 1000 | read | **1,318/3,000** | 83 | 11,404 | 14,511 | 14,609 |
| 1000 | DENY | **620/3,000** | 36 | 11,196 | 16,248 | 17,017 |
| 1000 | REQUIRE_APPROVAL | **970/3,000** | 30 | 28,503 | 31,541 | 31,905 |

## What it shows, and does not

* A single worker saturates at roughly 80–170 requests/s for reads and 30–90 for decisions that write evidence. Throughput
  at 100 concurrent connections is **lower** than at 10 (77 vs 167 read req/s): contention, not capacity growth.
* **1,000 concurrent connections is not supported by this configuration.** 56–77 % of connection attempts failed
  (`ConnectError`), and the successful ones waited 11–28 s at p50. The directive treats 1,000 as a qualification
  objective, not a capacity claim; this run does not meet it. Failing closed (no unauthorized effect, no 5xx) is the only
  good news at that level.
* Server memory 144 → 243 MB RSS; CPU 89 s consumed during the run.
* Latencies measured here are far above the in-process figure reported earlier (14–56 ms). Both are real; they
  measure different things, and the in-process figure must not be quoted as an API latency.

## Not yet done

Multi-worker and multi-replica runs; a separate load generator host; MCP transport; governed execution in a container;
Python 3.11; profiling of the evidence-write path (decision + evidence costs about 10 ms at concurrency 1 above reads);
a repeat on Linux x86_64. No SLO is proposed from one run.
