# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Migration 0062 baselines organizations that were edited before the history table existed.

Without a baseline, "policy version 4, empty history" could not be told apart from a deleted history,
and ``verify_history`` would have to either flag every pre-existing tenant or accept real deletion.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text

from responsibleai.db import PolicyRepository, create_engine
from tests.test_v1_customer_journey import _pg_url, _upgrade_head


@pytest.fixture()
async def pg() -> AsyncIterator[str]:
    async for url in _pg_url("wp_polhist"):
        yield url


async def test_an_org_edited_before_the_migration_gets_a_verifiable_baseline(pg: str) -> None:
    await _upgrade_head(pg, start="0061")  # leaves the schema at 0062; rebuild at 0061 below
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    from responsibleai.db import OrgRepository

    old = (await OrgRepository(engine).create_org("Old Co", "old-co")).id
    untouched = (await OrgRepository(engine).create_org("Untouched Co", "untouched-co")).id
    async with engine.raw.begin() as conn:
        await conn.execute(text("DROP TABLE governance_policy_history"))
        await conn.execute(text("UPDATE alembic_version SET version_num = '0061'"))
        await conn.execute(
            text(
                "INSERT INTO governance_policies (id, org_id, rule_id, reason_code, effect, "
                "risk_tiers, action_types, targets, position, created_at, updated_at) VALUES "
                "('p1', :old, 'deny-send', 'NO_SEND', 'DENY', NULL, :a, NULL, 0, 'now', 'now'), "
                "('p2', :old, 'review-pay', 'PAY', 'REQUIRE_APPROVAL', :r, NULL, :t, 1, 'now', 'now')"
            ),
            {
                "a": json.dumps(["external.send"]),
                "r": json.dumps(["HIGH", "LOW"]),
                "t": json.dumps(["bank"]),
                "old": old,
            },
        )
        await conn.execute(
            text(
                "INSERT INTO governance_policy_versions (org_id, version, updated_at) "
                "VALUES (:old, 4, 'now'), (:untouched, 0, 'now')"
            ),
            {"old": old, "untouched": untouched},
        )
    await engine.close()

    await _upgrade_head(pg)  # 0061 -> 0062 with existing data

    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        policy = PolicyRepository(engine)
        (baseline,) = await policy.history(old)
        assert (baseline["change"], baseline["actor_type"]) == ("baseline", "system")
        assert baseline["version"] == 4
        assert [r["rule_id"] for r in baseline["rules"]] == ["deny-send", "review-pay"]
        assert baseline["rules"][1]["risk_tiers"] == ["HIGH", "LOW"]
        assert await policy.verify_history(old) is True
        assert await policy.history(untouched) == []  # version 0: nothing to baseline
        assert await policy.verify_history(untouched) is True

        # The baseline is the genesis of a chain that continues normally.
        from responsibleai.db import PolicyActor
        from responsibleai.governance.models import GovernanceDecision
        from responsibleai.governance.policy import PolicyRule

        await policy.add_rule(
            old,
            PolicyRule("new", "NEW", GovernanceDecision.DENY, action_types=frozenset({"x"})),
            actor=PolicyActor("web_user", "u1"),
        )
        assert [e["version"] for e in await policy.history(old)] == [5, 4]
        assert await policy.verify_history(old) is True

        # And deleting it is caught, which is the point of having one.
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("DELETE FROM governance_policy_history WHERE org_id = :o"), {"o": old}
            )
        assert await policy.verify_history(old) is False
    finally:
        await engine.close()
