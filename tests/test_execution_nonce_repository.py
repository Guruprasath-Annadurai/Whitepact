"""Tests for `ExecutionNonceRepository` (Enterprise Readiness Phase 4,
replay protection).

Mirrors `test_revocation_epoch_repository.py`'s own structure --
concurrent-consume correctness, restart durability, multi-instance
simulation -- since this repository is the same class of "durable,
opt-in layer on top of an always-on in-memory check" primitive.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import uuid

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
)


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return ExecutionNonceRepository(db)


def _nonce() -> str:
    return uuid.uuid4().hex


class TestConsume:
    async def test_first_consume_succeeds(self, repo) -> None:
        await repo.consume(_nonce(), authorization_id="auth-1", organization_id="org-1")

    async def test_second_consume_of_the_same_nonce_raises(self, repo) -> None:
        nonce = _nonce()
        await repo.consume(nonce, authorization_id="auth-1", organization_id="org-1")
        with pytest.raises(NonceAlreadyConsumedError):
            await repo.consume(nonce, authorization_id="auth-2", organization_id="org-1")

    async def test_different_nonces_do_not_conflict(self, repo) -> None:
        await repo.consume(_nonce(), authorization_id="auth-1", organization_id="org-1")
        await repo.consume(_nonce(), authorization_id="auth-2", organization_id="org-1")  # no raise

    async def test_same_nonce_different_org_still_conflicts(self, repo) -> None:
        """The nonce itself is the whole guarantee -- a UUID-derived
        nonce colliding across orgs is already cryptographically
        implausible, so this repository does not additionally scope
        uniqueness by org (unlike RevocationEpochRepository's
        deliberate per-org scoping, which is a real multi-tenant
        counter, not a random token)."""
        nonce = _nonce()
        await repo.consume(nonce, authorization_id="auth-1", organization_id="org-1")
        with pytest.raises(NonceAlreadyConsumedError):
            await repo.consume(nonce, authorization_id="auth-2", organization_id="org-2")


class TestConcurrentConsume:
    async def test_concurrent_consume_of_the_same_nonce_only_one_wins(self, repo) -> None:
        nonce = _nonce()
        results = await asyncio.gather(
            *(
                repo.consume(nonce, authorization_id=f"auth-{i}", organization_id="org-1")
                for i in range(10)
            ),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 9
        assert all(isinstance(f, NonceAlreadyConsumedError) for f in failures)

    async def test_concurrent_consume_of_different_nonces_all_succeed(self, repo) -> None:
        nonces = [_nonce() for _ in range(20)]
        await asyncio.gather(
            *(
                repo.consume(n, authorization_id=f"auth-{i}", organization_id="org-1")
                for i, n in enumerate(nonces)
            )
        )  # must not raise


class TestMultiInstanceSimulation:
    """Two independent `ExecutionNonceRepository` objects standing in
    for two separate WhitePact process instances sharing one durable
    store -- proves the durability guarantee actually crosses instance
    boundaries, not just concurrent calls within one."""

    async def test_instance_b_sees_instance_as_consume_and_rejects_replay(self, db) -> None:
        instance_a = ExecutionNonceRepository(db)
        instance_b = ExecutionNonceRepository(db)
        nonce = _nonce()

        await instance_a.consume(nonce, authorization_id="auth-1", organization_id="org-1")

        with pytest.raises(NonceAlreadyConsumedError):
            await instance_b.consume(nonce, authorization_id="auth-1", organization_id="org-1")


class TestRestartDurability:
    async def test_consumed_nonce_survives_engine_close_and_reopen(self) -> None:
        """A fresh engine/repo pointed at the same on-disk file after
        the original engine is closed (simulating a process restart)
        must still refuse a nonce consumed before the restart."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.unlink(path)
        nonce = _nonce()
        try:
            engine_before = create_engine(path)
            await engine_before.init()
            repo_before = ExecutionNonceRepository(engine_before)
            await repo_before.consume(nonce, authorization_id="auth-1", organization_id="org-1")
            await engine_before.close()

            engine_after = create_engine(path)
            await engine_after.init()
            repo_after = ExecutionNonceRepository(engine_after)
            with pytest.raises(NonceAlreadyConsumedError):
                await repo_after.consume(nonce, authorization_id="auth-2", organization_id="org-1")
            await engine_after.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
