# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Policy history on real PostgreSQL: concurrent writers, new organizations, and external checkpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from responsibleai.db import OrgRepository, PolicyActor, PolicyRepository, create_engine
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from tests.test_v1_customer_journey import _pg_url, _upgrade_head

ACTOR = PolicyActor("web_user", "u-1")


@pytest.fixture()
async def pg() -> AsyncIterator[str]:
    async for url in _pg_url("wp_polhist_pg"):
        await _upgrade_head(url)
        yield url


def _rule(i: int) -> PolicyRule:
    return PolicyRule(f"r{i}", f"R{i}", GovernanceDecision.DENY, action_types=frozenset({f"a{i}"}))


async def test_concurrent_writers_produce_one_contiguous_verifiable_history(pg: str) -> None:
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        org = (await OrgRepository(engine).create_org("Conc", "conc-co")).id
        policy = PolicyRepository(engine)
        results = await asyncio.gather(
            *(policy.add_rule(org, _rule(i), actor=ACTOR) for i in range(24)),
            return_exceptions=True,
        )
        assert [r for r in results if isinstance(r, Exception)] == []
        entries = await policy.history(org, limit=100)
        assert sorted(e["version"] for e in entries) == list(range(1, 25))
        assert await policy.get_policy_version(org) == 24
        assert await policy.verify_history(org) is True

        # Mixed concurrent mutations on top: removals and a reorder racing with additions.
        mixed = await asyncio.gather(
            policy.remove_rule(org, "r0", actor=ACTOR),
            policy.remove_rule(org, "r1", actor=ACTOR),
            policy.add_rule(org, _rule(100), actor=ACTOR),
            policy.add_rule(org, _rule(101), actor=ACTOR),
            return_exceptions=True,
        )
        assert [r for r in mixed if isinstance(r, Exception)] == []
        assert await policy.get_policy_version(org) == 28
        assert await policy.verify_history(org) is True
    finally:
        await engine.close()


async def test_a_new_org_chain_starts_at_one_and_survives_a_retained_checkpoint(pg: str) -> None:
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        org = (await OrgRepository(engine).create_org("New", "new-co")).id
        policy = PolicyRepository(engine)
        for i in range(4):
            await policy.add_rule(org, _rule(i), actor=ACTOR)
        checkpoint = await policy.history_head(org)
        assert checkpoint and checkpoint["version"] == 4
        await policy.add_rule(
            org, _rule(9), actor=ACTOR
        )  # history moves on; old checkpoint stays valid
        assert await policy.verify_history(org, checkpoint=checkpoint) is True

        # Truncation and whole-history deletion are both caught, with and without a checkpoint.
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("DELETE FROM governance_policy_history WHERE org_id = :o AND version = 5"),
                {"o": org},
            )
        assert await policy.verify_history(org) is False
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("DELETE FROM governance_policy_history WHERE org_id = :o"), {"o": org}
            )
        assert await policy.verify_history(org) is False
        assert await policy.verify_history(org, checkpoint=checkpoint) is False
    finally:
        await engine.close()


async def test_version_rollback_is_caught_only_by_the_checkpoint_when_everything_is_reset(
    pg: str,
) -> None:
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        org = (await OrgRepository(engine).create_org("Roll", "roll-co")).id
        policy = PolicyRepository(engine)
        for i in range(3):
            await policy.add_rule(org, _rule(i), actor=ACTOR)
        checkpoint = await policy.history_head(org)
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("DELETE FROM governance_policy_history WHERE org_id = :o AND version = 3"),
                {"o": org},
            )
            await conn.execute(
                text("UPDATE governance_policy_versions SET version = 2 WHERE org_id = :o"),
                {"o": org},
            )
        assert await policy.verify_history(org) is True  # self-consistent at version 2
        assert await policy.verify_history(org, checkpoint=checkpoint) is False
    finally:
        await engine.close()
