"""Real, locally-executed concurrent-load + soak test — Enterprise
Readiness Phase 13. Complements scripts/run_benchmarks.py's single-
process, single-threaded microbenchmarks (which BENCHMARKS.md's own
"what this does not measure" section already admits don't cover
concurrency) with actual concurrent request handling against the real
FastAPI app, in-process via httpx's ASGITransport.

Scoping, stated honestly up front:
- ASGITransport drives the exact same app/middleware/DB code path a
  real deployment runs, in the same process, without a real OS TCP
  socket or network stack in between. This proves the application code
  handles real concurrency correctly (no deadlocks, no shared-state
  corruption, bounded latency growth) -- it does NOT measure network-
  stack, reverse-proxy, or multi-worker-process behavior, which no
  single-process harness can.
- SQLite (`:memory:`) is the backend here for reproducibility without
  external infrastructure. Concurrent-load numbers against a real
  Postgres deployment (connection-pool contention behaves differently)
  are a natural follow-up, not claimed here.
- The soak test's duration is bounded by what's practical to run in
  one sitting (see --soak-seconds); it detects gross, fast-growing
  leaks, not slow multi-day leaks a real production soak would need
  days to surface.

Usage:
    python scripts/run_load_test.py                  # default: load + short soak
    python scripts/run_load_test.py --soak-seconds 300  # longer soak
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import resource
import statistics
import sys
import time

sys.path.insert(0, "src")

import httpx
from asgi_lifespan import LifespanManager


def _rss_mb() -> float:
    # ru_maxrss is bytes on macOS, KB on Linux -- normalize via a
    # platform check rather than guessing wrong on one of them.
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / (1024 * 1024) if sys.platform == "darwin" else raw / 1024


async def _one_request(client: httpx.AsyncClient, path: str) -> tuple[float, int]:
    t0 = time.perf_counter()
    r = await client.get(path)
    return (time.perf_counter() - t0) * 1000, r.status_code


async def _run_concurrency_level(
    client: httpx.AsyncClient, path: str, concurrency: int, total_requests: int
) -> dict:
    latencies: list[float] = []
    errors = 0
    sem = asyncio.Semaphore(concurrency)

    async def _bounded():
        nonlocal errors
        async with sem:
            ms, status = await _one_request(client, path)
            latencies.append(ms)
            if status != 200:
                errors += 1

    start = time.perf_counter()
    await asyncio.gather(*[_bounded() for _ in range(total_requests)])
    wall = time.perf_counter() - start

    latencies.sort()

    def pct(p: float) -> float:
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "wall_seconds": round(wall, 3),
        "throughput_rps": round(total_requests / wall, 1),
        "p50_ms": round(pct(0.50), 2),
        "p95_ms": round(pct(0.95), 2),
        "p99_ms": round(pct(0.99), 2),
        "max_ms": round(max(latencies), 2),
        "errors": errors,
    }


async def _run_soak(client: httpx.AsyncClient, path: str, seconds: int, concurrency: int) -> dict:
    samples: list[tuple[float, float]] = []  # (elapsed_s, rss_mb)
    errors = 0
    total = 0
    start = time.perf_counter()
    next_sample = start

    async def _worker():
        nonlocal errors, total
        while time.perf_counter() - start < seconds:
            r = await client.get(path)
            total += 1
            if r.status_code != 200:
                errors += 1

    tasks = [asyncio.create_task(_worker()) for _ in range(concurrency)]

    while time.perf_counter() - start < seconds:
        now = time.perf_counter()
        if now >= next_sample:
            gc.collect()
            samples.append((round(now - start, 1), round(_rss_mb(), 1)))
            next_sample = now + max(1.0, seconds / 20)
        await asyncio.sleep(0.1)

    for t in tasks:
        await t

    rss_values = [s[1] for s in samples]
    first_half = rss_values[: len(rss_values) // 2] or rss_values
    second_half = rss_values[len(rss_values) // 2 :] or rss_values
    drift_mb = statistics.mean(second_half) - statistics.mean(first_half)

    return {
        "duration_seconds": seconds,
        "concurrency": concurrency,
        "total_requests": total,
        "errors": errors,
        "rss_samples_mb": samples,
        "rss_drift_mb_second_half_minus_first_half": round(drift_mb, 1),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--soak-seconds", type=int, default=60)
    parser.add_argument("--soak-concurrency", type=int, default=20)
    args = parser.parse_args()

    from responsibleai.dashboard.app import app, settings

    settings.db_path = ":memory:"
    settings.database_url = None
    settings.auto_migrate = False
    settings.auth_enabled = False

    async with LifespanManager(app) as manager:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=manager.app), base_url="http://loadtest"
        ) as client:
            print("=== Concurrent load: GET /api/health ===")
            results = []
            for concurrency in (1, 10, 100, 500, 1000):
                r = await _run_concurrency_level(
                    client, "/api/health", concurrency, total_requests=max(concurrency, 200)
                )
                results.append(r)
                print(
                    f"concurrency={r['concurrency']:>5}  "
                    f"requests={r['total_requests']:>5}  "
                    f"throughput={r['throughput_rps']:>8} req/s  "
                    f"p50={r['p50_ms']:>7}ms  p95={r['p95_ms']:>7}ms  "
                    f"p99={r['p99_ms']:>7}ms  max={r['max_ms']:>8}ms  "
                    f"errors={r['errors']}"
                )

            print(f"\n=== Soak: {args.soak_seconds}s at concurrency={args.soak_concurrency} ===")
            soak = await _run_soak(client, "/api/health", args.soak_seconds, args.soak_concurrency)
            print(f"total_requests={soak['total_requests']}  errors={soak['errors']}")
            print("RSS samples (elapsed_s, rss_mb):", soak["rss_samples_mb"])
            print(
                "RSS drift (2nd half mean - 1st half mean):",
                f"{soak['rss_drift_mb_second_half_minus_first_half']} MB",
            )


if __name__ == "__main__":
    asyncio.run(main())
