# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Capacity reservation races against a real Redis, from independent client connections.

``InMemoryRedisEval`` re-implements the Lua in Python, so it cannot show that the script is atomic
under concurrency. These tests use a live server and several separate clients (standing in for
replicas) and assert the invariants the script exists to provide. Redis is capacity accounting, not
execution authority (see ``runtime/capacity_reservation.py``); a pass here is not an authorization
claim.

Required in CI (``WHITEPACT_REQUIRE_REDIS=1``). Locally a missing server records a
QUALIFICATION_SKIP, which is not a pass.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from responsibleai.runtime.capacity_reservation import AtomicCapacityReservation


def _connect(url: str):
    import redis

    return redis.Redis.from_url(url, decode_responses=True)


@pytest.fixture
def replicas() -> Iterator[tuple[AtomicCapacityReservation, ...]]:
    url = os.environ.get("WHITEPACT_REDIS_URL", "")
    required = os.environ.get("WHITEPACT_REQUIRE_REDIS", "") == "1"
    if not url:
        if required:
            pytest.fail("WHITEPACT_REQUIRE_REDIS=1 but WHITEPACT_REDIS_URL is empty")
        pytest.skip("QUALIFICATION_SKIP purpose=live Redis capacity races; no WHITEPACT_REDIS_URL")
    try:
        import redis  # noqa: F401
    except ImportError:
        if required:
            pytest.fail("redis client is not installed and WHITEPACT_REQUIRE_REDIS=1")
        pytest.skip("QUALIFICATION_SKIP purpose=live Redis capacity races; redis not installed")
    clients = [_connect(url) for _ in range(3)]
    try:
        clients[0].ping()
    except Exception as exc:
        if required:
            pytest.fail(f"Redis required for the capacity race tests is unreachable: {exc}")
        pytest.skip(f"QUALIFICATION_SKIP purpose=live Redis capacity races; unreachable ({exc})")
    prefix = f"wp:test:{uuid.uuid4().hex}"
    try:
        yield tuple(AtomicCapacityReservation(c, key_prefix=prefix) for c in clients)
    finally:
        for key in clients[0].scan_iter(match=f"{prefix}:*"):
            clients[0].delete(key)
        for c in clients:
            c.close()


def _run(jobs, workers: int = 48):
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(lambda job: job(), jobs))


def test_the_tenant_limit_holds_under_concurrent_reservations_from_several_replicas(
    replicas,
) -> None:
    limit, attempts = 10, 90
    jobs = [
        (
            lambda i=i: replicas[i % len(replicas)].reserve(
                execution_id=f"exec-{i}",
                organization_id="org-a",
                ttl_seconds=60,
                tenant_limit=limit,
            )
        )
        for i in range(attempts)
    ]
    results = _run(jobs)
    admitted = [r for r in results if r.ok and r.mutated]
    assert len(admitted) == limit, f"admitted {len(admitted)} against a limit of {limit}"
    assert sum(1 for r in results if not r.ok) == attempts - limit
    assert max(r.tenant_count for r in results) == limit  # never observed above the limit


def test_the_same_execution_id_is_admitted_once_however_many_replicas_race(replicas) -> None:
    jobs = [
        (
            lambda i=i: replicas[i % len(replicas)].reserve(
                execution_id="exec-same", organization_id="org-a", ttl_seconds=60, tenant_limit=5
            )
        )
        for i in range(60)
    ]
    results = _run(jobs)
    assert sum(1 for r in results if r.mutated) == 1
    assert all(r.ok for r in results), "an idempotent retry must not look like a rejection"
    assert (
        replicas[0]
        .reserve(execution_id="probe", organization_id="org-a", ttl_seconds=60, tenant_limit=5)
        .tenant_count
        == 2
    )


def test_concurrent_reserve_and_release_leaves_the_counter_equal_to_the_outstanding_set(
    replicas,
) -> None:
    ids = [f"exec-{i}" for i in range(60)]
    _run(
        [
            (
                lambda e=e, i=i: replicas[i % 3].reserve(
                    execution_id=e, organization_id="org-a", ttl_seconds=60, tenant_limit=0
                )
            )
            for i, e in enumerate(ids)
        ]
    )
    released, kept = ids[:40], ids[40:]
    _run(
        [
            (lambda e=e, i=i: replicas[i % 3].release(execution_id=e, organization_id="org-a"))
            for i, e in enumerate(released * 2)  # every release is attempted twice
        ]
    )
    probe = replicas[0].reserve(
        execution_id="probe", organization_id="org-a", ttl_seconds=60, tenant_limit=0
    )
    assert probe.tenant_count == len(kept) + 1, "a double release changed the count twice"


def test_tenants_do_not_share_capacity(replicas) -> None:
    for i in range(3):
        assert (
            replicas[0]
            .reserve(execution_id=f"a-{i}", organization_id="org-a", ttl_seconds=60, tenant_limit=3)
            .ok
        )
    assert (
        not replicas[1]
        .reserve(execution_id="a-over", organization_id="org-a", ttl_seconds=60, tenant_limit=3)
        .ok
    )
    other = replicas[2].reserve(
        execution_id="b-0", organization_id="org-b", ttl_seconds=60, tenant_limit=3
    )
    assert other.ok and other.tenant_count == 1


def test_releasing_an_unknown_execution_id_changes_nothing(replicas) -> None:
    replicas[0].reserve(execution_id="real", organization_id="org-a", ttl_seconds=60)
    result = replicas[1].release(execution_id="never-reserved", organization_id="org-a")
    assert result.mutated is False
    assert (
        replicas[2]
        .reserve(execution_id="probe", organization_id="org-a", ttl_seconds=60)
        .tenant_count
        == 2
    )
