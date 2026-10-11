# Capacity, throttling and degraded-mode behaviour (measurement, not an SLO)

Status: **engineering measurements on one development machine. Not an availability, latency or capacity commitment.
1,000 concurrent clients is NOT supported and must not be advertised.** Raw data:
`docs/launch/evidence/bench-http-admission-2026-10-11-{A..E}.json` (source commit and hardware inside). Harness:
`scripts/bench_http_authorization.py --replicas N --max-inflight M`.

## Conditions (read before the numbers)
Apple M4 (10 cores), Docker Desktop PostgreSQL 16 on the same machine, uvicorn processes on loopback, **client load
generator on the same machine** (Python asyncio/httpx, which itself consumes CPU and inflates latencies), no TLS, no
proxy, client-side round robin for multi-process runs, route limiter off, plan limiter on, API-key authenticated.
Workloads: authenticated read; DENY with durable evidence write; REQUIRE_APPROVAL with evidence + approval row.
Unauthorized effects at every run: **0**. Approval rows equalled approval responses wherever measured.

## Results (requests that completed with 200; 503 = shed by admission control)
| Run | Config | Conc. | Workload | OK/sent | 503 | req/s | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|---|
| A | 1 process, admission OFF | 10 | authenticated | 400/400 | 0 | 170.2 | 50.3 | 111.4 |
| A | 1 process, admission OFF | 10 | DENY / | 400/400 | 0 | 77.9 | 111.3 | 185.6 |
| A | 1 process, admission OFF | 10 | REQUIR | 400/400 | 0 | 49.5 | 195.4 | 261.7 |
| A | 1 process, admission OFF | 50 | authenticated | 400/400 | 0 | 124.1 | 365.0 | 827.4 |
| A | 1 process, admission OFF | 50 | DENY / | 400/400 | 0 | 56.4 | 621.0 | 2063.0 |
| A | 1 process, admission OFF | 50 | REQUIR | 400/400 | 0 | 42.6 | 1002.9 | 2498.3 |
| A | 1 process, admission OFF | 100 | authenticated | 400/400 | 0 | 146.2 | 584.7 | 1065.7 |
| A | 1 process, admission OFF | 100 | DENY / | 400/400 | 0 | 44.5 | 1432.1 | 6042.8 |
| A | 1 process, admission OFF | 100 | REQUIR | 397/400 | 0 | 33.9 | 2075.9 | 7700.6 |
| A | 1 process, admission OFF | 300 | authenticated | 205/900 | 0 | 65.9 | 1911.6 | 2959.0 |
| A | 1 process, admission OFF | 300 | DENY / | 242/900 | 0 | 25.9 | 6125.3 | 8101.6 |
| A | 1 process, admission OFF | 300 | REQUIR | 232/900 | 0 | 22.5 | 6694.2 | 8627.8 |
| B | 1 process, limit 32 | 10 | authenticated | 400/400 | 0 | 127.2 | 70.6 | 136.1 |
| B | 1 process, limit 32 | 10 | DENY / | 400/400 | 0 | 73.9 | 117.9 | 183.9 |
| B | 1 process, limit 32 | 10 | REQUIR | 400/400 | 0 | 43.6 | 231.4 | 314.1 |
| B | 1 process, limit 32 | 50 | authenticated | 324/400 | 76 | 63.9 | 623.8 | 1894.2 |
| B | 1 process, limit 32 | 50 | DENY / | 163/400 | 237 | 51.5 | 559.4 | 1527.4 |
| B | 1 process, limit 32 | 50 | REQUIR | 118/400 | 282 | 33.2 | 854.4 | 1844.2 |
| B | 1 process, limit 32 | 100 | authenticated | 212/400 | 188 | 32.2 | 1296.0 | 5170.9 |
| B | 1 process, limit 32 | 100 | DENY / | 321/400 | 79 | 27.8 | 2119.6 | 5749.9 |
| B | 1 process, limit 32 | 100 | REQUIR | 217/400 | 183 | 23.2 | 1810.2 | 5221.3 |
| B | 1 process, limit 32 | 300 | authenticated | 171/900 | 254 | 24.0 | 3567.4 | 6518.8 |
| B | 1 process, limit 32 | 300 | DENY / | 454/900 | 256 | 26.5 | 4248.4 | 11493.6 |
| B | 1 process, limit 32 | 300 | REQUIR | 367/900 | 422 | 20.7 | 3389.9 | 12062.2 |
| C | 4 processes, limit 32 | 10 | authenticated | 400/400 | 0 | 215.0 | 37.4 | 104.2 |
| C | 4 processes, limit 32 | 10 | DENY / | 400/400 | 0 | 106.7 | 70.9 | 91.9 |
| C | 4 processes, limit 32 | 10 | REQUIR | 400/400 | 0 | 66.5 | 141.1 | 184.5 |
| C | 4 processes, limit 32 | 50 | authenticated | 390/400 | 10 | 195.6 | 149.0 | 621.9 |
| C | 4 processes, limit 32 | 50 | DENY / | 400/400 | 0 | 106.1 | 436.7 | 777.2 |
| C | 4 processes, limit 32 | 50 | REQUIR | 400/400 | 0 | 71.2 | 670.6 | 985.1 |
| C | 4 processes, limit 32 | 100 | authenticated | 400/400 | 0 | 98.2 | 867.5 | 1788.2 |
| C | 4 processes, limit 32 | 100 | DENY / | 399/400 | 0 | 89.2 | 788.2 | 2521.4 |
| C | 4 processes, limit 32 | 100 | REQUIR | 400/400 | 0 | 67.5 | 1259.9 | 2605.9 |
| C | 4 processes, limit 32 | 300 | authenticated | 497/900 | 403 | 58.9 | 2491.3 | 6157.6 |
| C | 4 processes, limit 32 | 300 | DENY / | 620/900 | 279 | 46.3 | 3618.3 | 7477.6 |
| C | 4 processes, limit 32 | 300 | REQUIR | 631/900 | 259 | 40.9 | 4039.6 | 8358.2 |
| D | 1 process, limit 16 | 50 | authenticated | 306/400 | 94 | 58.6 | 481.0 | 2224.3 |
| D | 1 process, limit 16 | 50 | DENY / | 299/400 | 100 | 38.5 | 834.5 | 2186.0 |
| D | 1 process, limit 16 | 50 | REQUIR | 125/400 | 275 | 31.1 | 773.4 | 1601.0 |
| D | 1 process, limit 16 | 100 | authenticated | 215/400 | 184 | 32.0 | 1067.8 | 4618.2 |
| D | 1 process, limit 16 | 100 | DENY / | 269/400 | 129 | 26.5 | 1814.9 | 4962.4 |
| D | 1 process, limit 16 | 100 | REQUIR | 241/400 | 159 | 24.6 | 1716.3 | 5141.8 |
| E | 4 processes, limit 16 | 100 | authenticated | 244/400 | 156 | 99.5 | 779.8 | 1453.7 |
| E | 4 processes, limit 16 | 100 | DENY / | 198/400 | 202 | 68.9 | 795.5 | 1657.2 |
| E | 4 processes, limit 16 | 100 | REQUIR | 171/400 | 229 | 58.7 | 1043.6 | 1938.8 |
| E | 4 processes, limit 16 | 300 | authenticated | 701/900 | 199 | 94.6 | 1641.0 | 5912.0 |
| E | 4 processes, limit 16 | 300 | DENY / | 812/900 | 88 | 70.3 | 2630.1 | 7644.0 |
| E | 4 processes, limit 16 | 300 | REQUIR | 577/900 | 320 | 47.1 | 2799.9 | 7435.7 |

## What this shows
* **Per-process sweet spot is about 10 concurrent requests**: roughly 120-170 reads/s, 55-80 DENY decisions/s and
  40-50 approval-creating decisions/s per process on this hardware. More concurrency does not add throughput; it adds
  queueing (p95 of seconds).
* **Scaling out helps less than linearly here (run C vs A: about 1.3x reads, 1.3-1.4x writes at 4 processes)** because
  client, PostgreSQL and servers share one 10-core machine. A real scale factor needs separate hosts and was not measured.
* **Admission control (new) bounds the failure mode, it does not create capacity.** Beyond the in-flight limit a request
  gets an immediate 503 with `Retry-After` and no work started, instead of waiting 10-28 s or failing to connect. It did
  **not** improve p95 latency of the requests that were served in this single-host setup (compare A, B, D at 50-100), and
  at 300 connections the *client* still saw `ConnectError` (the loopback listen queue / OS limits, not WhitePact). The
  default is 32 per process; 16 shed far more traffic for no clear latency gain here.
* Latency figures include the load generator's own CPU use; treat them as upper bounds on server latency, not as
  server latency.

## Layers, in the order a request meets them
| Layer | Trigger | Response | Scope |
|---|---|---|---|
| Admission control | in-flight > `WHITEPACT_MAX_INFLIGHT_REQUESTS` (default 32; 0 disables) | **503** + `Retry-After: 1`, nothing executed | per process; `/health`, `/ready`, `/sse` exempt |
| Plan rate limit | org requests/minute above plan budget (FREE 60, PRO 300; ENTERPRISE none) | **429** | per organization (shared via Redis) |
| Route limit | scaled `max(base, plan budget)`; ENTERPRISE bounded by `WHITEPACT_ENTERPRISE_ROUTE_CEILING_PER_MINUTE` (default 1,200) | **429** | per organization and route |
| Abuse controls below 30/min (login, MFA, key issuance, billing) | fixed | **429** | never scaled |
| Redis unavailable | store errors | limiters **degrade to per-replica in-memory** windows; logged `plan_rate_limiter_degraded`; requests keep flowing | weaker while degraded |
| Database unavailable | ping fails | `/ready` **503**; governed calls **fail closed** (no tool runs); no evidence is fabricated | per process |
| Restore quarantine | restore reconciliation pending | governed execution blocked | global |

## About the 1,200 requests/minute Enterprise ceiling
It is an **abuse bound per route per organization (20 req/s)**, not a capacity guarantee. One approval-creating route at
that rate would need about 40 % of one process's measured 50 decisions/s; several organizations at their ceilings would
exceed a single process by a wide margin. Real capacity is *replicas x measured per-process throughput* and must be
re-measured on production-shaped infrastructure before any figure is promised to a customer. The ceiling is configurable
so the operator can lower it to what the deployed fleet can sustain.

## Not done / blockers
Multi-host load, TLS and proxy overhead, PostgreSQL on a separate host, a pooled/replica DB, profiling of the evidence
write path, an x86_64 Linux run, MCP-transport load, sustained (soak) runs, and any run at 1,000 clients. These need
infrastructure that is not provisioned (and spending that is not authorized).
