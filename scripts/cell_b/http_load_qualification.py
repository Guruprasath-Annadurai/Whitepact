#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""B9 — HTTP load qualification against a live uvicorn process + PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _start_server(db_url: str, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update(
        {
            "WHITEPACT_ENV": "development",
            "WHITEPACT_AUTH_ENABLED": "false",
            "DATABASE_URL": db_url,
            "WHITEPACT_DATABASE_URL": db_url,
            "WHITEPACT_AUTO_MIGRATE": "true",
            "WHITEPACT_HOST": "127.0.0.1",
            "WHITEPACT_PORT": str(port),
        }
    )
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_ready(base: str, timeout_s: float = 120.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base}/api/health", timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"server not ready at {base}")


def _run_load(base: str, duration_s: float, workers: int) -> dict:
    latencies: list[float] = []
    errors = 0
    count = 0
    deadline = time.monotonic() + duration_s
    lock = threading.Lock()

    def _worker() -> None:
        nonlocal errors, count
        client = httpx.Client(timeout=5.0)
        while time.monotonic() < deadline:
            start = time.perf_counter()
            try:
                resp = client.get(f"{base}/api/health")
                ms = (time.perf_counter() - start) * 1000
                with lock:
                    latencies.append(ms)
                    count += 1
                    if resp.status_code >= 500:
                        errors += 1
            except httpx.HTTPError:
                with lock:
                    errors += 1
                    count += 1
        client.close()

    threads = [threading.Thread(target=_worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95) - 1] if latencies else 0.0
    p99 = latencies[int(len(latencies) * 0.99) - 1] if latencies else 0.0
    p50 = statistics.median(latencies) if latencies else 0.0
    return {
        "requests": count,
        "errors": errors,
        "measured_rps": round(count / duration_s, 2),
        "measured_p50_ms": round(p50, 3),
        "measured_p95_ms": round(p95, 3),
        "measured_p99_ms": round(p99, 3),
    }


async def _run(db_url: str, args: argparse.Namespace) -> dict:
    proc = _start_server(db_url, args.port)
    base = f"http://127.0.0.1:{args.port}"
    try:
        _wait_ready(base)
        burst = _run_load(base, args.duration, args.workers)
        soak = _run_load(base, args.soak, max(2, args.workers // 2))
        return {"burst": burst, "soak": soak}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()


async def _amain(args: argparse.Namespace) -> int:
    from tests.pg_test_url import isolated_pg_url

    async for db_url in isolated_pg_url("cell_b_load"):
        results = await _run(db_url, args)
        evidence = {
            "phase": "B9",
            "test": "http_load_qualification",
            "timestamp": datetime.now(UTC).isoformat(),
            "evidence_categories": ["LOAD_TESTED", "REAL_POSTGRES_TESTED", "SOAK_TESTED"],
            "environment": "uvicorn_http + isolated_postgresql",
            "burst_duration_seconds": args.duration,
            "soak_duration_seconds": args.soak,
            "concurrency_workers": args.workers,
            **results,
            "limitations": "Single-node local qualification; not multi-replica staging.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, indent=2))
        ok = results["burst"]["errors"] == 0 and results["soak"]["errors"] == 0
        return 0 if ok else 1
    return 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--soak", type=float, default=120.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--port", type=int, default=18765)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO / "artifacts" / "production" / "b9-http-pg-load.json",
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
