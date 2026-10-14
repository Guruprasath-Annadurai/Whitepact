# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Opt-in denial-only Core benchmark; owns its TCP server and disposable local DB.

Run from a development clone with PYTHONPATH=src:.; no arbitrary URL/credential
argument is accepted. Auth, rate limits, canonical checks and closed gates remain
enabled. This is NOT successful execution/containment throughput qualification.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import platform
import resource
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit


def validate_local_origin(origin: str) -> None:
    """Reject names, redirects, credentials and non-loopback origin components."""
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is None
        or not 1 <= parsed.port <= 65535
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid local benchmark origin")


def checked_workload(requests: int, concurrency: int) -> None:
    if not 1 <= requests <= 200 or not 1 <= concurrency <= 100:
        raise ValueError("Workload must be 1..200 requests and 1..100 concurrency")


def percentile(values: list[float], percent: int) -> float:
    """Nearest-rank percentile; no interpolation or unmeasured tail estimate."""
    if not values or not 0 < percent <= 100:
        raise ValueError("Percentile needs samples and percent in 1..100")
    return sorted(values)[math.ceil(len(values) * percent / 100) - 1]


def summarize(samples: list[tuple[float, str]], seconds: float) -> dict:
    if not samples or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Summary needs samples and positive finite wall time")
    latencies = [latency for latency, _ in samples]
    if any(not math.isfinite(value) or value < 0 for value in latencies):
        raise ValueError("Latency must be non-negative and finite")
    counts = Counter(outcome for _, outcome in samples)
    return {
        "requests_attempted": len(samples),
        "wall_seconds": seconds,
        "requests_per_second": len(samples) / seconds,
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "p99_ms": percentile(latencies, 99),
        "governance_denials": counts["DENIED"],
        "rate_limited": counts["RATE_LIMITED"],
        "capacity_rejections": counts["CAPACITY_REJECTED"],
        "errors": len(samples) - counts["DENIED"] - counts["RATE_LIMITED"],
        "allowed_effects": counts["UNEXPECTED_ALLOW"],
        "outcomes": dict(sorted(counts.items())),
    }


async def run_local(requests: int, concurrency: int) -> dict:
    checked_workload(requests, concurrency)
    # Imports are deliberately after CLI opt-in and workload validation. Unit
    # calculation/safety tests must not start services or consult runtime config.
    import httpx
    import pytest
    import tests.pg_test_url as pg
    import uvicorn
    from sqlalchemy import text
    from tests.org_http_fixtures import seed_org_with_key

    import responsibleai.dashboard.app as dashboard
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
    from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
    from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN

    # Existing public, local-only fixture credentials; never use production
    # environment URLs or the test helper's optional external admin override.
    if dashboard.settings.redis_url:
        raise RuntimeError("Run without an ambient Redis configuration")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(pg, "_CANDIDATES", ("postgresql://wp:wp@127.0.0.1:55432/postgres",))
        patch.setattr(pg, "_cached_admin", None)
        async for url in pg.isolated_pg_url("wp_bench_denial"):
            ini = _find_alembic_ini()
            if ini is None:
                raise RuntimeError("Repository migration configuration unavailable")
            await _run_alembic(ini, _migration_env(url), "upgrade", "head")
            patch.setattr(dashboard.settings, "database_url", url)
            patch.setattr(dashboard.settings, "auto_migrate", False)
            patch.setattr(dashboard.settings, "auth_enabled", True)
            patch.setattr(dashboard.settings, "environment", "development")
            patch.setattr(dashboard.settings, "redis_url", None)
            patch.setattr(dashboard.settings, "phase7a_dispatcher_enabled", False)
            if (
                PRODUCTION_GATE_B_OPEN
                or not dashboard.limiter.enabled
                or dashboard.settings.max_inflight_requests <= 0
            ):
                raise RuntimeError("Closed Gate B, rate limiting and admission cap required")
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
            validate_local_origin(origin)
            server = uvicorn.Server(
                uvicorn.Config(dashboard.app, log_level="critical", access_log=False)
            )
            task = asyncio.create_task(server.serve(sockets=[sock]))
            try:
                async with asyncio.timeout(30):
                    while not server.started:
                        if task.done():
                            await task
                            raise RuntimeError("Local server stopped during startup")
                        await asyncio.sleep(0.01)
                org_id, _, key = await seed_org_with_key(name="Local benchmark", slug="local-bench")
                body = {"name": SYNTHETIC_COUNTER_TOOL, "arguments": {}, "purpose": "benchmark"}
                limits = httpx.Limits(
                    max_connections=concurrency, max_keepalive_connections=concurrency
                )
                async with httpx.AsyncClient(
                    base_url=origin,
                    follow_redirects=False,
                    trust_env=False,
                    timeout=15,
                    limits=limits,
                ) as client:
                    path = "/api/v1/governance/tools/call"
                    unauthenticated = await client.post(path, json=body)
                    if unauthenticated.status_code != 401:
                        raise RuntimeError("Unauthenticated request was not rejected")
                    headers = {"Authorization": f"Bearer {key}"}
                    probe = await client.post(path, json=body, headers=headers)
                    if probe.status_code != 200 or probe.json().get("error") != "governance_denied":
                        raise RuntimeError("Missing-authority probe was not denied")
                    semaphore = asyncio.Semaphore(concurrency)

                    async def measure(
                        semaphore: asyncio.Semaphore,
                        path: str,
                        body: dict,
                        headers: dict,
                    ) -> tuple[float, str]:
                        async with semaphore:
                            started = time.perf_counter()
                            try:
                                response = await client.post(path, json=body, headers=headers)
                                if response.status_code == 429:
                                    outcome = "RATE_LIMITED"
                                elif (
                                    response.status_code == 503
                                    and response.json().get("error") == "overloaded"
                                ):
                                    outcome = "CAPACITY_REJECTED"
                                elif response.status_code != 200:
                                    outcome = f"HTTP_{response.status_code}"
                                else:
                                    payload = response.json()
                                    if not isinstance(payload, dict):
                                        outcome = "MALFORMED"
                                    elif payload.get("error") == "governance_denied":
                                        outcome = "DENIED"
                                    elif "result" in payload:
                                        outcome = "UNEXPECTED_ALLOW"
                                    else:
                                        outcome = "UNEXPECTED_RESPONSE"
                            except (httpx.HTTPError, ValueError):
                                outcome = "TRANSPORT_ERROR"
                            return (time.perf_counter() - started) * 1000, outcome

                    cpu_before = time.process_time()
                    started = time.perf_counter()
                    samples = await asyncio.gather(
                        *(measure(semaphore, path, body, headers) for _ in range(requests))
                    )
                    wall = time.perf_counter() - started
                    process_cpu = time.process_time() - cpu_before
                    counter = await client.get("/api/v1/governance/test-counter", headers=headers)
                    if (
                        counter.status_code != 200
                        or counter.json().get("counter") != 0
                        or counter.json().get("downstream_call_count") != 0
                    ):
                        raise RuntimeError("Zero-effect counter proof failed")
                    result = summarize(samples, wall)
                    async with dashboard._db_engine.raw.connect() as connection:
                        migration_head = (
                            await connection.execute(
                                text("SELECT version_num FROM alembic_version")
                            )
                        ).scalar_one()
                        postgres_version = (
                            await connection.execute(text("SHOW server_version"))
                        ).scalar_one()
                    evidence = await client.get(
                        "/api/governance/evidence", params={"limit": 200}, headers=headers
                    )
                    if evidence.status_code != 200:
                        raise RuntimeError("Durable denial evidence lookup failed")
                    records = evidence.json().get("evidence", [])
                    if (
                        len(records) < result["governance_denials"] + 1
                        or any(record.get("organization_id") != org_id for record in records)
                        or any(record.get("decision") != "DENY" for record in records)
                    ):
                        raise RuntimeError("Tenant-scoped durable denial evidence proof failed")
                    root = Path(__file__).resolve().parents[2]
                    source_head = subprocess.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=root,
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout.strip()
                    result.update(
                        source_head=source_head,
                        python_version=sys.version.split()[0],
                        alembic_head=migration_head,
                        postgres_version=postgres_version,
                        harness_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        workload="authenticated missing-authority denial; no root/consent/delegation seeded",
                        concurrency=concurrency,
                        warmup_denials=1,
                        unauthenticated_probe_status=401,
                        counter_after=0,
                        downstream_call_count=0,
                        durable_denial_evidence_count=len(records),
                        process_cpu_seconds=process_cpu,
                        process_cpu_percent_one_core=100 * process_cpu / wall,
                        process_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                        * (1 if platform.system() == "Darwin" else 1024),
                        resource_scope="client and API in same Python process; excludes PostgreSQL/container/host peers",
                        hardware={
                            "os": platform.system(),
                            "architecture": platform.machine(),
                            "logical_cpus": os.cpu_count(),
                        },
                        auth_enabled=True,
                        rate_limiter_enabled=True,
                        max_inflight_requests=dashboard.settings.max_inflight_requests,
                        rate_limiter_backend="local memory; not Redis qualification",
                        gate_b="CLOSED",
                        phase7a="DISABLED",
                        database="disposable PostgreSQL on 127.0.0.1:55432; migrated head",
                        successful_execution_throughput_qualified=False,
                    )
                    return result
            finally:
                server.should_exit = True
                await asyncio.wait_for(task, timeout=30)
                sock.close()
    raise RuntimeError("Disposable database unavailable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-local", action="store_true", help="Explicitly permit owned local server/database"
    )
    parser.add_argument("--requests", type=int, default=24)
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    if not args.run_local:
        parser.error("--run-local opt-in is required; no service contacted")
    try:
        result = asyncio.run(run_local(args.requests, args.concurrency))
    except Exception as exc:
        # Do not print exception arguments: driver errors can contain URLs/keys.
        print(json.dumps({"status": "BLOCKED", "error_class": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 1 if result["errors"] or result["allowed_effects"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
