# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Local latency sample for the enterprise-recovery candidate.

This is one machine, one process, and the database named on the command
line. It is not a production PostgreSQL capacity proof and it does not
disable authorization. Set WHITEPACT_BENCH_DATABASE_URL to a disposable
PostgreSQL URL to measure the database-backed health path. With no URL
the script uses a temporary SQLite file.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import statistics
import tempfile
import time
from pathlib import Path


def _percentiles(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)

    def pick(q: float) -> float:
        if not ordered:
            return 0.0
        index = min(len(ordered) - 1, int(q * len(ordered)))
        return ordered[index]

    return {
        "p50_ms": round(pick(0.50), 3),
        "p95_ms": round(pick(0.95), 3),
        "p99_ms": round(pick(0.99), 3),
        "mean_ms": round(statistics.mean(samples), 3) if samples else 0.0,
    }


async def _http(database_url: str | None, requests: int, concurrency: int) -> dict[str, object]:
    if database_url:
        os.environ["WHITEPACT_DATABASE_URL"] = database_url
        backend = (
            "postgresql" if database_url.startswith("postgresql") else database_url.split(":", 1)[0]
        )
    else:
        os.environ.pop("WHITEPACT_DATABASE_URL", None)
        os.environ.pop("RAI_DATABASE_URL", None)
        os.environ.pop("DATABASE_URL", None)
        backend = "sqlite-file"
    os.environ.setdefault("WHITEPACT_AUTO_MIGRATE", "false")
    os.environ.setdefault("WHITEPACT_ENV", "development")
    os.environ.setdefault("WHITEPACT_LOG_LEVEL", "ERROR")
    os.environ.setdefault("WHITEPACT_AUTH_ENABLED", "false")

    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    import responsibleai.dashboard.app as app_module

    app_module.settings.auto_migrate = False
    app_module.settings.auth_enabled = False
    if database_url:
        app_module.settings.database_url = database_url
    else:
        path = Path(tempfile.mkdtemp(prefix="wp-bench-")) / "bench.db"
        app_module.settings.database_url = None
        app_module.settings.db_path = str(path)

    async with LifespanManager(app_module.app, startup_timeout=60) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://bench") as client:
            warm = await client.get("/api/health")
            if warm.status_code != 200:
                raise RuntimeError(f"/api/health warmup returned {warm.status_code}")

            async def one(path: str) -> tuple[float, int]:
                started = time.perf_counter()
                response = await client.get(path)
                return (time.perf_counter() - started) * 1000, response.status_code

            async def workload(path: str) -> dict[str, object]:
                samples: list[float] = []
                errors = 0
                started = time.perf_counter()
                remaining = requests
                while remaining:
                    batch = min(concurrency, remaining)
                    results = await asyncio.gather(*(one(path) for _ in range(batch)))
                    for elapsed, status in results:
                        samples.append(elapsed)
                        if status != 200:
                            errors += 1
                    remaining -= batch
                wall = time.perf_counter() - started
                return {
                    "path": path,
                    "requests": requests,
                    "concurrency": concurrency,
                    "error_rate": round(errors / requests, 6) if requests else 0.0,
                    "throughput_rps": round(requests / wall, 2) if wall else 0.0,
                    **_percentiles(samples),
                }

            health = await workload("/api/health")
            live = await workload("/healthz")
    return {"db_backend": backend, "workloads": [health, live]}


def _gateway(iterations: int) -> dict[str, object]:
    from responsibleai.governance.gateway import WhitePactRuntimeGateway
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        AuthorityContext,
        IdentityContext,
    )

    gateway = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="bench-org", kind="api_key")
    agent = AgentContext(identity=identity, organization_id="bench-org")
    authority = AuthorityContext(
        delegated_by="bench-org",
        granted_action_types=frozenset({"rai_scan"}),
    )
    action = ActionRequest(
        agent=agent,
        action_type="rai_scan",
        target="rai_scan",
        arguments={"text": "The quarterly report shows revenue grew 12% year over year."},
    )
    denied = AuthorityContext(delegated_by="bench-org", granted_action_types=frozenset())
    for _ in range(50):
        gateway.evaluate(action=action, authority=authority)

    def time_call(fn) -> dict[str, object]:
        samples: list[float] = []
        started = time.perf_counter()
        for _ in range(iterations):
            t0 = time.perf_counter()
            fn()
            samples.append((time.perf_counter() - t0) * 1000)
        wall = time.perf_counter() - started
        return {
            "iterations": iterations,
            "concurrency": 1,
            "error_rate": 0.0,
            "throughput_rps": round(iterations / wall, 2) if wall else 0.0,
            **_percentiles(samples),
        }

    return {
        "allow": time_call(lambda: gateway.evaluate(action=action, authority=authority)),
        "deny": time_call(lambda: gateway.evaluate(action=action, authority=denied)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=400)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--gateway-iterations", type=int, default=1000)
    parser.add_argument("--database-url", default=os.environ.get("WHITEPACT_BENCH_DATABASE_URL"))
    args = parser.parse_args()
    report = {
        "qualification": "local process only; not a production capacity claim",
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "http": asyncio.run(_http(args.database_url, args.requests, args.concurrency)),
        "gateway_in_process": _gateway(args.gateway_iterations),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
