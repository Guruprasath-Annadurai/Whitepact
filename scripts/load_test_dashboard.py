# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real, concurrent load test for the hosted WhitePact dashboard
(v2.0.0 roadmap item: "persistent storage proven under real load").

Every number this script prints comes from an actual run against a real
target URL -- not estimated, not simulated. It exercises two things a
sequential/single-request test cannot prove:

1. **Read-path concurrency**: N concurrent "users" hitting the public,
   unauthenticated pages/endpoints a real design partner's dashboard
   traffic would generate (health checks, the public trust/registry/
   leaderboard pages, the status page) for a sustained window --
   proving the Render web service + its DB connection pool hold up
   under concurrent load, not just one request at a time.
2. **A real write surviving concurrent read load**: one real signup
   (org + API key) fired partway through the read-load window, then
   read back afterward using the issued credential -- proving a write
   that happened *during* concurrent traffic is still durably there,
   not just that writes work in isolation.

**Honestly scoped, deliberately**: this does NOT load-test the
`/api/signup` write path itself at concurrency -- that endpoint is
rate-limited to 5/hour per IP and 30/hour site-wide by design (see
`dashboard/signup_guard.py`), specifically to resist the kind of burst
write traffic this script could otherwise generate. Testing that would
mean either defeating the platform's own abuse protection (wrong) or
running from many different IPs (out of scope for a single-machine
script). What this script proves is real: the read path under
concurrency, and one real write's durability across that window -- not
a claim that this deployment can absorb hundreds of concurrent
*writes*, which it was never sized or priced to do on Render's free
instance class.

Test data is tagged with a `loadtest-` slug prefix and a
`+loadtest-<run-id>@` email local-part so it's trivially identifiable
and safe to clean up afterward.

Usage:
    python scripts/load_test_dashboard.py --url https://whitepact.com \
        --concurrency 15 --duration 45
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import uuid
from dataclasses import dataclass, field

import httpx

# Public, unauthenticated, GET-only endpoints -- safe to hit repeatedly,
# representative of real dashboard browsing traffic (health checks the
# app itself would poll, and the public trust/registry/leaderboard/status
# pages a real visitor or design partner would actually load).
READ_PATHS: tuple[str, ...] = (
    "/api/health",
    "/api/support/status",
    "/",
    "/trust",
    "/registry",
    "/leaderboard",
    "/status",
)


@dataclass
class RequestResult:
    path: str
    status_code: int
    elapsed_ms: float
    error: str | None = None


@dataclass
class LoadTestReport:
    results: list[RequestResult] = field(default_factory=list)
    signup_result: dict | None = None
    signup_readback_ok: bool | None = None

    def summary(self) -> str:
        if not self.results:
            return "No requests completed."
        ok = [r for r in self.results if r.error is None and 200 <= r.status_code < 300]
        failed = [r for r in self.results if r not in ok]
        latencies = sorted(r.elapsed_ms for r in ok)

        def pct(p: float) -> float:
            if not latencies:
                return 0.0
            idx = min(int(len(latencies) * p), len(latencies) - 1)
            return latencies[idx]

        lines = [
            f"Total requests:   {len(self.results)}",
            f"Successful (2xx): {len(ok)} ({100 * len(ok) / len(self.results):.1f}%)",
            f"Failed:           {len(failed)}",
        ]
        if latencies:
            lines += [
                f"Latency mean:     {statistics.mean(latencies):.1f} ms",
                f"Latency p50:      {pct(0.50):.1f} ms",
                f"Latency p95:      {pct(0.95):.1f} ms",
                f"Latency p99:      {pct(0.99):.1f} ms",
                f"Latency max:      {max(latencies):.1f} ms",
            ]
        if failed:
            by_path: dict[str, int] = {}
            for r in failed:
                key = f"{r.path} -> {r.status_code}{' (' + r.error + ')' if r.error else ''}"
                by_path[key] = by_path.get(key, 0) + 1
            lines.append("Failures by path/status:")
            for key, count in sorted(by_path.items(), key=lambda kv: -kv[1]):
                lines.append(f"  {count:4d}x  {key}")
        if self.signup_result is not None:
            lines.append("")
            lines.append(f"Signup during load: HTTP {self.signup_result['status_code']}")
            if self.signup_readback_ok is not None:
                lines.append(
                    f"Write survived concurrent read load, read back correctly: "
                    f"{self.signup_readback_ok}"
                )
        return "\n".join(lines)


async def _hit_random_path(client: httpx.AsyncClient, path: str) -> RequestResult:
    t0 = time.perf_counter()
    try:
        resp = await client.get(path, timeout=15.0)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return RequestResult(path=path, status_code=resp.status_code, elapsed_ms=elapsed_ms)
    except Exception as exc:  # noqa: BLE001 -- a network failure is itself a result to report
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return RequestResult(path=path, status_code=0, elapsed_ms=elapsed_ms, error=str(exc))


async def _worker(
    client: httpx.AsyncClient, stop_at: float, results: list[RequestResult]
) -> None:
    i = 0
    while time.monotonic() < stop_at:
        path = READ_PATHS[i % len(READ_PATHS)]
        i += 1
        results.append(await _hit_random_path(client, path))


async def _run_one_signup(client: httpx.AsyncClient, run_id: str) -> dict:
    payload = {
        "name": f"Load Test Org {run_id[:8]}",
        "slug": f"loadtest-{run_id[:8]}",
        "email": f"loadtest+{run_id[:8]}@example.com",
        "website": "",
        "page_loaded_at_ms": int(time.time() * 1000) - 3000,
    }
    try:
        resp = await client.post("/api/signup", json=payload, timeout=15.0)
    except Exception as exc:  # noqa: BLE001 -- a network failure is a result to report, not a crash
        return {"status_code": 0, "body": {}, "error": str(exc)}
    body: dict = {}
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        pass
    return {"status_code": resp.status_code, "body": body}


async def run_load_test(base_url: str, concurrency: int, duration_seconds: float) -> LoadTestReport:
    report = LoadTestReport()
    run_id = str(uuid.uuid4())

    async with httpx.AsyncClient(base_url=base_url, follow_redirects=True) as client:
        stop_at = time.monotonic() + duration_seconds
        results: list[RequestResult] = []
        workers = [asyncio.create_task(_worker(client, stop_at, results)) for _ in range(concurrency)]

        # Fire the one real write partway through the read-load window,
        # concurrently with the read workers above -- proving a write
        # that happens *during* load survives it, not just in isolation.
        await asyncio.sleep(duration_seconds / 3)
        report.signup_result = await _run_one_signup(client, run_id)

        await asyncio.gather(*workers)
        report.results = results

        if report.signup_result["status_code"] == 201:
            api_key = report.signup_result["body"].get("api_key")
            org_id = report.signup_result["body"].get("org", {}).get("id")
            if api_key and org_id:
                try:
                    readback = await client.get(
                        f"/api/orgs/{org_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=15.0,
                    )
                    report.signup_readback_ok = (
                        readback.status_code == 200 and readback.json().get("id") == org_id
                    )
                except Exception:  # noqa: BLE001
                    report.signup_readback_ok = False
            else:
                report.signup_readback_ok = False

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Base URL of the deployment to load-test.")
    parser.add_argument("--concurrency", type=int, default=15, help="Concurrent read workers.")
    parser.add_argument("--duration", type=float, default=45.0, help="Test duration in seconds.")
    args = parser.parse_args()

    print(f"Load-testing {args.url} — concurrency={args.concurrency}, duration={args.duration}s")
    print(f"Read paths exercised: {', '.join(READ_PATHS)}")
    print("One real signup fired partway through the window to prove write durability under load.")
    print()

    report = asyncio.run(run_load_test(args.url, args.concurrency, args.duration))
    print(report.summary())


if __name__ == "__main__":
    main()
