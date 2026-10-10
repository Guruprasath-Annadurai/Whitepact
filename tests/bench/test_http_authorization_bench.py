# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated, PostgreSQL-backed authorization latency through the real ASGI application.

Opt-in (``WHITEPACT_RUN_BENCH=1``): it is a measurement, not a correctness test, and a skipped
run is not a pass. Writes JSON to ``WHITEPACT_BENCH_OUT`` (default ``bench-http-authorization.json``).

What this measures, so nobody over-reads it:

* the whole application stack in one process: API-key authentication, tenant resolution, policy
  evaluation, a durable evidence write and, for REQUIRE_APPROVAL, an approval row, all on a real
  PostgreSQL;
* it does NOT include a TCP socket, TLS, a reverse proxy, uvicorn worker overhead, a second
  replica, a network hop to the database, or governed *execution* (no container is started).

So it bounds the decision path from below. It is not a production SLO.

    WHITEPACT_RUN_BENCH=1 WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:55433/postgres \
        pytest -o addopts= tests/bench/test_http_authorization_bench.py -q
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import statistics
import subprocess
import time
from pathlib import Path

import pytest

from tests.test_v1_exactly_one_effect import (  # noqa: F401  (fixtures)
    _call,
    _prepare_org,
    journey_client,
    pg_url,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("WHITEPACT_RUN_BENCH") != "1",
    reason="BENCH_NOT_REQUESTED set WHITEPACT_RUN_BENCH=1. A skip is not a measurement.",
)

REQUESTS = int(os.environ.get("WHITEPACT_BENCH_REQUESTS", "300"))
CONCURRENCY = int(os.environ.get("WHITEPACT_BENCH_CONCURRENCY", "16"))


def _percentile(samples: list[float], pct: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[index]


def _summary(label: str, latencies_ms: list[float], elapsed: float, errors: int, c: int) -> dict:
    if not latencies_ms:
        return {
            "workload": label,
            "concurrency": c,
            "requests": errors,
            "errors": errors,
            "error_rate": 1.0,
            "note": "every request failed",
        }
    return {
        "workload": label,
        "concurrency": c,
        "requests": len(latencies_ms) + errors,
        "errors": errors,
        "error_rate": errors / max(1, len(latencies_ms) + errors),
        "p50_ms": round(_percentile(latencies_ms, 50), 3),
        "p95_ms": round(_percentile(latencies_ms, 95), 3),
        "p99_ms": round(_percentile(latencies_ms, 99), 3),
        "mean_ms": round(statistics.fmean(latencies_ms), 3),
        "throughput_rps": round(len(latencies_ms) / elapsed, 1),
        "duration_s": round(elapsed, 3),
    }


async def _run(label: str, make_request, concurrency: int, total: int) -> dict:
    latencies: list[float] = []
    errors = 0
    first_failure: list[str] = []
    sem = asyncio.Semaphore(concurrency)

    async def one() -> None:
        nonlocal errors
        async with sem:
            start = time.perf_counter()
            try:
                response = await make_request()
                ok = response.status_code == 200
                if not ok and not first_failure:
                    first_failure.append(f"{response.status_code} {response.text[:200]}")
            except Exception as exc:
                ok = False
                if not first_failure:
                    first_failure.append(f"{type(exc).__name__}: {exc}"[:200])
            elapsed = (time.perf_counter() - start) * 1000
            if ok:
                latencies.append(elapsed)
            else:
                errors += 1

    began = time.perf_counter()
    await asyncio.gather(*(one() for _ in range(total)))
    summary = _summary(label, latencies, time.perf_counter() - began, errors, concurrency)
    if first_failure:
        summary["first_failure"] = first_failure[0]
    return summary


def _cpu() -> str:
    try:
        return subprocess.run(  # noqa: S603, S607
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
        ).stdout.strip()
    except OSError:
        return platform.processor()


@pytest.mark.asyncio
async def test_http_authorization_latency(journey_client, monkeypatch, seed_runtime_authority):
    client, pg = journey_client
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg)
    # The FREE plan is capped at 60 requests/minute by design (plan_rate_limiter). Measure the
    # tenant on ENTERPRISE, which has no per-minute cap; the limiter itself stays enabled.
    from sqlalchemy import text

    from responsibleai.db import create_engine

    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE organizations SET plan = 'ENTERPRISE' WHERE id = :id"), {"id": org_id}
        )
    await engine.close()
    auth = {"Authorization": f"Bearer {raw}"}

    async def approval_required():  # authenticated decision -> evidence + approval row
        return await _call(client, raw)

    async def denied():  # authenticated decision with no delegated authority -> evidence row
        return await client.post(
            "/api/v1/governance/tools/call",
            headers=auth,
            json={"name": "rai_scan", "arguments": {"text": "x"}, "purpose": "bench denied call"},
        )

    async def read_only():  # authenticated read, no evidence write
        return await client.get("/api/v1/governance/test-counter", headers=auth)

    # Warm the pool, caches and import paths before measuring.
    for _ in range(20):
        await denied()
        await read_only()

    results = []
    for label, request in (
        ("authenticated read (GET test-counter)", read_only),
        ("DENY decision + evidence write", denied),
        ("REQUIRE_APPROVAL decision + evidence + approval row", approval_required),
    ):
        results.append(await _run(label, request, 1, REQUESTS))
        results.append(await _run(label, request, CONCURRENCY, REQUESTS))

    # Every measured request must have succeeded, or the numbers describe a broken system.
    assert all(r["error_rate"] == 0 for r in results), json.dumps(results, indent=1)

    commit = subprocess.run(  # noqa: S603, S607
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    report = {
        "measurement": "in-process ASGI + real PostgreSQL, authenticated, durable evidence writes",
        "not_included": [
            "TCP/TLS",
            "reverse proxy",
            "uvicorn workers",
            "network hop to database",
            "multiple replicas",
            "governed execution in a container",
        ],
        "is_an_slo": False,
        "source_commit": commit,
        "hardware": {"cpu": _cpu(), "machine": platform.machine(), "os": platform.platform()},
        "python": platform.python_version(),
        "database": os.environ.get("WHITEPACT_BENCH_DB_NOTE", "PostgreSQL (see operator note)"),
        "requests_per_workload": REQUESTS,
        "results": results,
    }
    out = Path(os.environ.get("WHITEPACT_BENCH_OUT", "bench-http-authorization.json"))
    out.write_text(json.dumps(report, indent=2) + "\n")
