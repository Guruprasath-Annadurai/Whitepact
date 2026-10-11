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
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic

    ini = _find_alembic_ini()
    assert ini is not None
    await _run_alembic(ini, _migration_env(pg), "upgrade", "0061")  # the schema before 0062
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    from responsibleai.db import OrgRepository

    old = (await OrgRepository(engine).create_org("Old Co", "old-co")).id
    untouched = (await OrgRepository(engine).create_org("Untouched Co", "untouched-co")).id
    async with engine.raw.begin() as conn:
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

        # The parameters contributed by the FastStart review work against a baselined history too.
        head = await policy.history_head(old)
        assert head is not None and head["version"] == 5
        assert await policy.verify_history(old, expected_version=5) is True
        assert await policy.verify_history(old, expected_version=4) is False  # a rollback claim
        assert await policy.verify_history(old, expected_head_digest=head["entry_digest"]) is True
        assert await policy.verify_history(old, expected_head_digest="f" * 64) is False
        assert await policy.verify_history(old, checkpoint=head) is True
        # Rolling the counter back out of band is caught by the cross-check, and by the retained checkpoint
        # even when the cross-check is deliberately turned off.
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("UPDATE governance_policy_versions SET version = 4 WHERE org_id = :o"),
                {"o": old},
            )
        assert await policy.verify_history(old) is False
        assert await policy.verify_history(old, check_persisted_version=False) is True
        assert (
            await policy.verify_history(old, check_persisted_version=False, expected_version=4)
            is False
        )
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("UPDATE governance_policy_versions SET version = 5 WHERE org_id = :o"),
                {"o": old},
            )

        # And deleting it is caught, which is the point of having one.
        async with engine.raw.begin() as conn:
            await conn.execute(
                text("DELETE FROM governance_policy_history WHERE org_id = :o"), {"o": old}
            )
        assert await policy.verify_history(old) is False
    finally:
        await engine.close()
