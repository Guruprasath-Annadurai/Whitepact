# Local denial-only authorization benchmark

Harness: `scripts/evaluation/local_authorization_benchmark.py`. Validation:
`tests/test_evaluation_benchmark_safety.py` (**20 passed**, no failures/skips in
the development safety test run). This is a small reproducible baseline, not an
enterprise SLO or a successful execution/containment throughput qualification.

## Run safely

From the repository clone with actual dashboard/PostgreSQL dependencies:

```sh
PYTHONPATH=src:. python scripts/evaluation/local_authorization_benchmark.py --run-local
```

Defaults: 24 measured requests, four maximum concurrent requests, one warmup
denial and one unauthenticated rejection probe. Maximum accepted workload is
200 requests and concurrency 100. There is **no user-supplied target URL** or
API key option. The harness binds its own ephemeral `127.0.0.1` socket and
creates/migrates/drops only a randomly named `wp_bench_denial_*` PostgreSQL test
database on local `127.0.0.1:55432` using existing public local-fixture credentials.
It ignores production/test-admin environment URLs and refuses ambient Redis
configuration. HTTP proxy environment and redirects are disabled. No provider
API or global service is a load target. Missing local infrastructure is an
explicit blocked run, never a SQLite or mocked success fallback.

The original backend HTTP admission cap and auth/rate limits remain enabled.
This is development-mode Core with fixture organization/key creation, but **no
root, consent or delegation is seeded**. It calls the actual governed synthetic
counter endpoint over real TCP; each successful request returns canonical
missing-authority denial. Final counter and downstream dispatch count must remain
zero; tenant-scoped durable denial evidence must cover the warmup and every
measured denial. No ALLOW workloads,
external effects, root issuance, Linux containment or production hosted
preflight are qualified. The local memory limiter is not Redis qualification.

## Interpretation and reporting

JSON output reports attempted requests, denial count, rate-limit rejection
count, recognized admission-cap rejection count, errors, zero-effect counter,
nearest-rank p50/p95/p99 and attempted requests per wall-clock second. Errors
include protective 503 admission rejections: they must not be silently counted
as successful governed throughput. Queue wait before a measured task acquires
the bounded semaphore is excluded from per-request latency; total batch wall
time includes it. Percentiles cover all measured attempts, including rejection
responses. At 24 samples p99 is the observed maximum, not a well-estimated
long-term tail.

CPU is process CPU delta during the measured batch, expressed against one
logical core; peak RSS is process lifetime high-water mark. Client and Uvicorn
share one Python process, so neither resource statistic isolates the server.
External PostgreSQL/container/host peers are excluded. Hardware reports OS,
architecture and logical CPU count, not an invented memory inventory. Output
includes source HEAD and exact harness SHA-256; retain both when the harness is
uncommitted. An integration owner must rerun on its exact combined candidate.

An initial bounded run on Darwin arm64, ten logical CPUs, Python 3.11 against
the preserved Core baseline measured 24/24 denials, zero errors/effects, p50
232.54 ms, p95 631.72 ms, p99 698.73 ms, 12.43 attempted requests/s. A subsequent
100-request/concurrency-100 burst returned 32 denials and 68 HTTP 503 responses,
zero effects, p50 1320.51 ms, p95 2639.35 ms, p99 2713.62 ms and 36.41 attempted
requests/s. **The latter is not a 100-concurrency capacity PASS.** The configured
32-in-flight protective cap in `responsibleai.ops.admission` rejects excess
requests with `error=overloaded`; it was not raised or disabled. The harness
now explicitly counts that state separately while retaining it in error totals.
These initial measurements preceded the final output-provenance addition;
final exact-code reruns must be recorded by the integration report.

No 1,000 or 10,000 concurrency workload was run here. No cloud, TLS, multi-worker,
multi-replica, long-duration, failover or isolated successful-execution capacity
claim follows. Runtime CPU/RSS measurements are not cloud cost estimates.
The existing startup log's `auth=disabled` label depends on flat-key presence;
auth was actually enabled and the unauthenticated probe returned 401. This
instrumentation discrepancy was not fixed in shared runtime code.

Security checks are deliberately not disabled to chase throughput. A saturated
or closed boundary is honest evidence, not permission to weaken it. Production
remains **NO-GO**.
