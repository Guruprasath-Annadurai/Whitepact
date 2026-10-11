# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""REC-28: a per-route slowapi limit must not make a plan's documented budget unreachable.

Observed before the fix: one ENTERPRISE organization got 429 after 30 calls a minute on a
route whose plan budget is "unlimited". These tests run with the limiter ON, over real HTTP.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.dashboard.plan_rate_limiter import (
    ENTERPRISE_ROUTE_CEILING_PER_MINUTE,
    MIN_SCALED_BASE_PER_MINUTE,
    OrgPlanDirectory,
    scaled_route_limit,
)
from responsibleai.rbac.models import Plan, Role
from tests.org_http_fixtures import seed_org_with_key

ROUTE = "/api/audit"  # decorated @_plan_scaled("60/minute")


@pytest.fixture(autouse=True)
def _auth(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
async def client():
    """A real uvicorn server on a loopback port, not the in-process ASGI transport: the transport
    shares request state across calls and defeats slowapi's per-request check, which is exactly
    why in-process tests never reproduced REC-28."""
    import asyncio
    import socket

    import uvicorn

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on")
    )
    task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        await asyncio.sleep(0.05)
    assert server.started, "uvicorn did not start"
    try:
        async with AsyncClient(base_url=f"http://127.0.0.1:{port}") as c:
            yield c
    finally:
        server.should_exit = True
        await task


async def _org_key(slug: str, plan: Plan) -> str:
    from responsibleai.dashboard.app import _org_repo

    org_id, _kid, raw = await seed_org_with_key(name=slug, slug=slug, role=Role.ADMIN)
    assert _org_repo is not None
    await _org_repo.set_plan(org_id, plan)
    return raw


async def _burst(client: AsyncClient, key: str, n: int) -> list[int]:
    return [
        (await client.get(ROUTE, headers={"Authorization": f"Bearer {key}"})).status_code
        for _ in range(n)
    ]


def test_scaling_function_is_monotone_floored_and_ceilinged() -> None:
    assert scaled_route_limit(30, Plan.FREE) == 60
    assert scaled_route_limit(30, Plan.PRO) == 300
    assert scaled_route_limit(30, Plan.ENTERPRISE) == ENTERPRISE_ROUTE_CEILING_PER_MINUTE
    assert scaled_route_limit(500, Plan.PRO) == 500  # never below the route's own base
    assert scaled_route_limit(30, None) == 30  # unauthenticated / unresolved keep the flat base
    for sensitive in (5, 10, 20, MIN_SCALED_BASE_PER_MINUTE - 1):
        for plan in Plan:
            assert scaled_route_limit(sensitive, plan) == sensitive  # abuse controls never scale


def test_directory_is_bounded_and_only_resolves_org_keys() -> None:
    d = OrgPlanDirectory(max_entries=2)
    for i in range(5):
        d.remember(f"o{i}", Plan.PRO)
    assert len(d._plans) == 2
    assert d.plan_for_key("o4") is None and d.plan_for_key("key:abc") is None
    assert d.plan_for_key("org:o4") is Plan.PRO and d.plan_for_key("1.2.3.4") is None


async def test_enterprise_org_exceeds_the_flat_per_route_limit(client) -> None:
    key = await _org_key("ent-scaled", Plan.ENTERPRISE)
    codes = await _burst(client, key, 100)
    assert codes.count(429) == 0, codes.count(429)  # was 40 x 429 at 60/min before the fix


async def test_pro_org_gets_its_plan_budget_not_the_flat_limit(client) -> None:
    key = await _org_key("pro-scaled", Plan.PRO)
    codes = await _burst(client, key, 100)
    assert codes.count(429) == 0


async def test_free_org_is_still_limited_at_its_budget(client) -> None:
    key = await _org_key("free-scaled", Plan.FREE)
    codes = await _burst(client, key, 75)
    assert 429 in codes and codes.index(429) <= 61  # the plan limiter / route limit still bite


async def test_scaling_is_per_organization(client) -> None:
    free = await _org_key("free-iso", Plan.FREE)
    ent = await _org_key("ent-iso", Plan.ENTERPRISE)
    assert 429 in await _burst(client, free, 75)
    assert (await client.get(ROUTE, headers={"Authorization": f"Bearer {ent}"})).status_code == 200
