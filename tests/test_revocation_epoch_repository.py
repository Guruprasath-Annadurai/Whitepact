"""Tests for `RevocationEpochRepository` (Heart Production Closure Gap B).

Covers the directive's required properties directly: durability across
a process restart, correctness under concurrent bumpers (no lost
updates), multi-instance visibility (two independent repository
objects against the same durable store), and that an epoch only ever
advances, never regresses -- matching `RevocationEpoch`'s own
in-memory invariant (see `governance/revocation_kernel.py`), now
actually enforced by real persistence instead of merely documented.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return RevocationEpochRepository(db)


class TestCurrent:
    async def test_never_bumped_scope_reads_as_epoch_zero(self, repo):
        epoch = await repo.current("org-1", "delegation")
        assert epoch.epoch == 0
        assert epoch.organization_id == "org-1"
        assert epoch.scope == "delegation"

    async def test_different_scopes_are_independent(self, repo):
        await repo.bump("org-1", "delegation")
        assert (await repo.current("org-1", "delegation")).epoch == 1
        assert (await repo.current("org-1", "consent")).epoch == 0

    async def test_different_orgs_are_independent(self, repo):
        await repo.bump("org-1", "delegation")
        assert (await repo.current("org-1", "delegation")).epoch == 1
        assert (await repo.current("org-2", "delegation")).epoch == 0


class TestBump:
    async def test_first_bump_from_no_row_goes_to_one(self, repo):
        epoch = await repo.bump("org-1", "delegation")
        assert epoch.epoch == 1

    async def test_sequential_bumps_increment_monotonically(self, repo):
        for expected in range(1, 6):
            epoch = await repo.bump("org-1", "delegation")
            assert epoch.epoch == expected

    async def test_epoch_never_regresses_across_many_bumps(self, repo):
        seen = [(await repo.bump("org-1", "delegation")).epoch for _ in range(10)]
        assert seen == sorted(seen)
        assert len(set(seen)) == len(seen)  # every bump produced a distinct value


class TestConcurrentBump:
    async def test_concurrent_bumps_lose_no_updates(self, repo):
        """N concurrent bumpers against the same (org, scope) must
        together advance the epoch by exactly N -- proving the
        UPDATE-then-INSERT-with-retry scheme has no lost-update race,
        the exact failure mode a naive read-then-write-in-Python
        implementation would have under real concurrency."""
        n = 25
        await asyncio.gather(*(repo.bump("org-1", "delegation") for _ in range(n)))
        final = await repo.current("org-1", "delegation")
        assert final.epoch == n

    async def test_concurrent_bumps_across_different_scopes_dont_interfere(self, repo):
        await asyncio.gather(
            *(repo.bump("org-1", "delegation") for _ in range(10)),
            *(repo.bump("org-1", "consent") for _ in range(7)),
        )
        assert (await repo.current("org-1", "delegation")).epoch == 10
        assert (await repo.current("org-1", "consent")).epoch == 7


class TestMultiInstanceSimulation:
    """Two independent `RevocationEpochRepository` objects standing in
    for two separate WhitePact process instances sharing one durable
    store -- the exact multi-instance shape the directive's revocation
    tests require."""

    async def test_instance_b_sees_instance_as_bump_immediately(self, db):
        instance_a = RevocationEpochRepository(db)
        instance_b = RevocationEpochRepository(db)

        await instance_a.bump("org-1", "delegation")
        seen_by_b = await instance_b.current("org-1", "delegation")
        assert seen_by_b.epoch == 1

    async def test_instances_alternately_bumping_stay_consistent(self, db):
        instance_a = RevocationEpochRepository(db)
        instance_b = RevocationEpochRepository(db)

        await instance_a.bump("org-1", "delegation")
        await instance_b.bump("org-1", "delegation")
        await instance_a.bump("org-1", "delegation")

        assert (await instance_a.current("org-1", "delegation")).epoch == 3
        assert (await instance_b.current("org-1", "delegation")).epoch == 3


class TestRestartDurability:
    async def test_epoch_survives_engine_close_and_reopen(self):
        """A fresh `DatabaseEngine`/`RevocationEpochRepository` pointed
        at the same on-disk file after the original engine is closed
        (simulating a process restart) must see the bump that happened
        before the restart -- proving this is real durable storage, not
        an in-process cache that happens to survive within one engine's
        lifetime."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(path)  # create_engine() creates the file itself
        try:
            engine_before = create_engine(path)
            await engine_before.init()
            repo_before = RevocationEpochRepository(engine_before)
            await repo_before.bump("org-1", "delegation")
            await repo_before.bump("org-1", "delegation")
            await engine_before.close()

            engine_after = create_engine(path)
            await engine_after.init()
            repo_after = RevocationEpochRepository(engine_after)
            epoch = await repo_after.current("org-1", "delegation")
            assert epoch.epoch == 2
            await engine_after.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
