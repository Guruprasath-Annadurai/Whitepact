# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Live Redis failover: the limiter shares a window, survives the store dying, and recovers.

Starts a disposable ``redis:7-alpine`` container, kills it mid-run, restarts it on the same port, and
checks the plan limiter degrades to per-replica enforcement (no exception, still bounded) and returns
to the shared window afterwards. Needs a Docker daemon; ``WHITEPACT_REQUIRE_REDIS=1`` makes a missing
daemon a failure instead of a recorded skip.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import uuid

import pytest
from fastapi import HTTPException

from responsibleai.dashboard.plan_rate_limiter import PlanRateLimiter, plan_limit
from responsibleai.rbac.models import Plan


def _docker_ok() -> bool:
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0  # noqa: S603, S607


@pytest.fixture()
def redis_container():
    if not _docker_ok():
        if os.environ.get("WHITEPACT_REQUIRE_REDIS") == "1":
            pytest.fail("WHITEPACT_REQUIRE_REDIS=1 but no Docker daemon is available")
        pytest.skip("QUALIFICATION_SKIP purpose=live Redis failover. No Docker daemon. Not a pass.")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    name = f"wp-redis-failover-{uuid.uuid4().hex[:8]}"

    def start() -> None:
        subprocess.run(  # noqa: S603, S607
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                name,
                "-p",
                f"127.0.0.1:{port}:6379",
                "redis:7-alpine",
            ],
            check=True,
            capture_output=True,
        )

    def stop() -> None:
        subprocess.run(["docker", "kill", name], capture_output=True)  # noqa: S603, S607

    start()
    try:
        yield f"redis://127.0.0.1:{port}/0", start, stop
    finally:
        stop()


async def _wait_redis(url: str) -> None:
    import redis.asyncio as redis_asyncio

    client = redis_asyncio.from_url(url)
    try:
        for _ in range(100):
            try:
                await client.ping()
                return
            except Exception:
                await asyncio.sleep(0.2)
        raise AssertionError("redis did not come up")
    finally:
        await client.aclose()


async def test_limiter_degrades_during_an_outage_and_recovers_the_shared_window(
    redis_container,
) -> None:
    url, start, stop = redis_container
    await _wait_redis(url)
    budget = plan_limit(Plan.FREE)
    assert budget is not None
    a, b = PlanRateLimiter(redis_url=url), PlanRateLimiter(redis_url=url)

    # 1. Healthy: two replicas share ONE window (half the budget from each exhausts it).
    for _ in range(budget // 2):
        await a.check("org-f", Plan.FREE)
        await b.check("org-f", Plan.FREE)
    with pytest.raises(HTTPException) as shared:
        await a.check("org-f", Plan.FREE)
    assert shared.value.status_code == 429 and a.degraded_events == 0

    # 2. Redis dies: no exception reaches the caller, enforcement continues per replica.
    stop()
    await asyncio.sleep(0.5)
    for _ in range(budget):
        await a.check("org-outage", Plan.FREE)
    with pytest.raises(HTTPException) as local:
        await a.check("org-outage", Plan.FREE)
    assert local.value.status_code == 429  # bounded while degraded
    assert a.degraded_events >= budget
    await b.check("org-outage", Plan.FREE)  # replica b has its own, separate local window

    # 3. Redis returns: replicas use the shared store again (a fresh org gets a fresh shared window).
    start()
    await _wait_redis(url)
    before = a.degraded_events
    for _ in range(budget // 2):
        await a.check("org-back", Plan.FREE)
        await b.check("org-back", Plan.FREE)
    with pytest.raises(HTTPException):
        await a.check("org-back", Plan.FREE)
    assert a.degraded_events == before  # no further degradation once the store is back
