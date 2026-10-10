# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Policy changes are attributable and the rules in force at each version are recoverable.

Evidence records carry only ``policy_version``. Before ``governance_policy_history`` the rule set that
governed a past decision was gone the moment someone edited it, and nothing recorded who edited it.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from responsibleai.db import PolicyActor, PolicyRepository, create_engine
from responsibleai.db.policy_repository import PolicyRuleNotFoundError
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from tests import test_web_policy_management as _web
from tests.test_web_policy_management import _onboard_owner

web_client = _web.web_client

ALICE = PolicyActor("web_user", "user-alice")
KEY = PolicyActor("api_key", "key-1")


def _rule(rule_id: str, effect=GovernanceDecision.DENY, *actions: str) -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        reason_code=f"R_{rule_id.upper()}",
        effect=effect,
        action_types=frozenset(actions) if actions else None,
    )


@pytest.fixture
async def repo():
    engine = create_engine(":memory:")
    await engine.init()
    yield PolicyRepository(engine), engine
    await engine.close()


async def test_every_mutation_records_actor_change_and_the_rules_then_in_force(repo) -> None:
    policy, _engine = repo
    await policy.add_rule(
        "org-a", _rule("deny-send", GovernanceDecision.DENY, "external.send"), actor=ALICE
    )
    await policy.add_rule(
        "org-a",
        _rule("review-pay", GovernanceDecision.REQUIRE_APPROVAL, "payment.create"),
        actor=KEY,
    )
    await policy.reorder("org-a", ["review-pay", "deny-send"], actor=ALICE)
    await policy.remove_rule("org-a", "deny-send", actor=KEY)

    entries = await policy.history("org-a")
    assert [e["change"] for e in entries] == [
        "rule_removed",
        "reordered",
        "rule_added",
        "rule_added",
    ]
    assert [e["version"] for e in entries] == [4, 3, 2, 1]
    assert (entries[0]["actor_type"], entries[0]["actor_id"]) == ("api_key", "key-1")
    assert (entries[1]["actor_type"], entries[1]["actor_id"]) == ("web_user", "user-alice")
    assert [r["rule_id"] for r in entries[3]["rules"]] == ["deny-send"]
    assert [r["rule_id"] for r in entries[2]["rules"]] == ["deny-send", "review-pay"]
    assert [r["rule_id"] for r in entries[1]["rules"]] == ["review-pay", "deny-send"]
    assert [r["rule_id"] for r in entries[0]["rules"]] == ["review-pay"]
    # The history version is the same number evidence records carry as policy_version.
    assert entries[0]["version"] == await policy.get_policy_version("org-a")
    assert await policy.verify_history("org-a") is True


async def test_a_change_without_a_declared_actor_is_recorded_as_unattributed(repo) -> None:
    policy, _engine = repo
    await policy.add_rule("org-a", _rule("r1", GovernanceDecision.DENY, "x"))
    (entry,) = await policy.history("org-a")
    assert (entry["actor_type"], entry["actor_id"]) == ("unattributed", "unattributed")


async def test_a_refused_change_leaves_neither_a_version_nor_a_history_row(repo) -> None:
    policy, _engine = repo
    await policy.add_rule("org-a", _rule("r1", GovernanceDecision.DENY, "x"), actor=ALICE)
    with pytest.raises(PolicyRuleNotFoundError):
        await policy.remove_rule("org-a", "missing", actor=ALICE)
    with pytest.raises(ValueError):
        await policy.reorder("org-a", ["r1", "ghost"], actor=ALICE)
    assert await policy.get_policy_version("org-a") == 1
    assert len(await policy.history("org-a")) == 1


async def test_history_is_per_tenant(repo) -> None:
    policy, _engine = repo
    await policy.add_rule("org-a", _rule("a-rule", GovernanceDecision.DENY, "x"), actor=ALICE)
    await policy.add_rule("org-b", _rule("b-rule", GovernanceDecision.DENY, "y"), actor=KEY)
    assert [e["rules"][0]["rule_id"] for e in await policy.history("org-a")] == ["a-rule"]
    assert [e["rules"][0]["rule_id"] for e in await policy.history("org-b")] == ["b-rule"]
    assert await policy.history("org-c") == []


@pytest.mark.parametrize(
    "tamper",
    [
        "UPDATE governance_policy_history SET actor_id = 'someone-else' WHERE version = 2",
        "UPDATE governance_policy_history SET rules_json = '[]' WHERE version = 2",
        "UPDATE governance_policy_history SET change = 'rule_removed' WHERE version = 2",
        "DELETE FROM governance_policy_history WHERE version = 2",
        # Toggling the leading character guarantees the digest is modified,
        # avoiding the 1/16 collision when prev_entry_digest already starts with 'f':
        "UPDATE governance_policy_history SET prev_entry_digest = "
        "CASE WHEN substr(prev_entry_digest, 1, 1) = 'f' THEN '0' ELSE 'f' END || substr(prev_entry_digest, 2) "
        "WHERE version = 3",
        # Rewriting entry digest
        "UPDATE governance_policy_history SET entry_digest = "
        "CASE WHEN substr(entry_digest, 1, 1) = 'f' THEN '0' ELSE 'f' END || substr(entry_digest, 2) "
        "WHERE version = 2",
        # Altering version sequence / ordering
        "UPDATE governance_policy_history SET version = 99 WHERE version = 2",
        # Tampering with creation timestamp
        "UPDATE governance_policy_history SET created_at = '1970-01-01 00:00:00' WHERE version = 2",
        # Cross-tenant tampering / moving a row to another organization
        "UPDATE governance_policy_history SET org_id = 'org-b' WHERE version = 2",
    ],
)
async def test_a_rewritten_or_deleted_history_row_is_detected(repo, tamper: str) -> None:
    policy, engine = repo
    for i in range(3):
        await policy.add_rule(
            "org-a", _rule(f"r{i}", GovernanceDecision.DENY, f"a{i}"), actor=ALICE
        )
    assert await policy.verify_history("org-a") is True
    async with engine.raw.begin() as conn:
        await conn.execute(text(tamper))
    assert await policy.verify_history("org-a") is False


async def test_history_reordering_is_detected(repo) -> None:
    policy, engine = repo
    for i in range(3):
        await policy.add_rule(
            "org-a", _rule(f"r{i}", GovernanceDecision.DENY, f"a{i}"), actor=ALICE
        )
    assert await policy.verify_history("org-a") is True
    # Swap versions of row 1 and row 2
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE governance_policy_history SET version = -1 WHERE version = 1")
        )
        await conn.execute(
            text("UPDATE governance_policy_history SET version = 1 WHERE version = 2")
        )
        await conn.execute(
            text("UPDATE governance_policy_history SET version = 2 WHERE version = -1")
        )
    assert await policy.verify_history("org-a") is False


async def test_history_cross_tenant_injection_is_detected(repo) -> None:
    policy, engine = repo
    await policy.add_rule("org-a", _rule("r-a1", GovernanceDecision.DENY, "act-a1"), actor=ALICE)
    await policy.add_rule("org-a", _rule("r-a2", GovernanceDecision.DENY, "act-a2"), actor=ALICE)
    await policy.add_rule("org-b", _rule("r-b1", GovernanceDecision.DENY, "act-b1"), actor=KEY)

    assert await policy.verify_history("org-a") is True
    assert await policy.verify_history("org-b") is True

    # Attempt cross-tenant injection: inject org-b's row into org-a as version 3
    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "UPDATE governance_policy_history SET org_id = 'org-a', version = 3 WHERE org_id = 'org-b'"
            )
        )

    # org-a fails verification because the injected row does not chain from org-a's version 2
    assert await policy.verify_history("org-a") is False
    # org-b lost its only row while its policy version is still 1. An empty history is valid only for
    # an org that was never edited, so this is reported as tampering, not as a valid empty chain.
    assert await policy.verify_history("org-b") is False


async def test_the_web_console_attributes_changes_to_the_signed_in_user(
    web_client: AsyncClient,
) -> None:
    csrf = await _onboard_owner(web_client)
    for rule_id, action in (("deny-send", "external.send"), ("deny-pay", "payment.create")):
        created = await web_client.post(
            "/api/v1/web/policy/rules",
            headers={"X-WP-CSRF": csrf},
            json={
                "rule_id": rule_id,
                "reason_code": rule_id.upper().replace("-", "_"),
                "effect": "DENY",
                "action_types": [action],
            },
        )
        assert created.status_code == 200, created.text
    removed = await web_client.delete(
        "/api/v1/web/policy/rules/deny-send", headers={"X-WP-CSRF": csrf}
    )
    assert removed.status_code == 200

    history = await web_client.get("/api/v1/web/policy/history")
    assert history.status_code == 200, history.text
    body = history.json()
    assert body["chain_valid"] is True
    assert [e["change"] for e in body["entries"]] == ["rule_removed", "rule_added", "rule_added"]
    actors = {(e["actor_type"], e["actor_id"]) for e in body["entries"]}
    assert len(actors) == 1
    ((actor_type, actor_id),) = actors
    assert actor_type == "web_user" and actor_id not in {"", "unattributed", "None"}
    assert [r["rule_id"] for r in body["entries"][0]["rules"]] == ["deny-pay"]


async def test_history_requires_a_session_and_is_not_shared_between_tenants(
    web_client: AsyncClient,
) -> None:
    anonymous = AsyncClient(transport=web_client._transport, base_url="http://test")
    try:
        assert (await anonymous.get("/api/v1/web/policy/history")).status_code in (401, 403)
    finally:
        await anonymous.aclose()

    csrf = await _onboard_owner(web_client)
    await web_client.post(
        "/api/v1/web/policy/rules",
        headers={"X-WP-CSRF": csrf},
        json={"rule_id": "mine", "reason_code": "MINE", "effect": "DENY", "action_types": ["x"]},
    )
    other = AsyncClient(transport=web_client._transport, base_url="http://test")
    try:
        other_csrf = await _onboard_owner(other)
        assert other_csrf
        theirs = await other.get("/api/v1/web/policy/history")
        assert theirs.status_code == 200
        assert theirs.json()["entries"] == []
    finally:
        await other.aclose()


async def test_deleting_every_history_row_is_detected_against_the_version_counter(repo) -> None:
    """An empty chain is internally valid; it is only wrong because the org has been edited."""
    policy, engine = repo
    for i in range(3):
        await policy.add_rule(
            "org-a", _rule(f"r{i}", GovernanceDecision.DENY, f"a{i}"), actor=ALICE
        )
    assert await policy.verify_history("org-a") is True
    async with engine.raw.begin() as conn:
        await conn.execute(text("DELETE FROM governance_policy_history WHERE org_id = 'org-a'"))
    assert await policy.history("org-a") == []
    assert await policy.verify_history("org-a") is False


async def test_dropping_only_the_newest_rows_is_detected(repo) -> None:
    policy, engine = repo
    for i in range(3):
        await policy.add_rule(
            "org-a", _rule(f"r{i}", GovernanceDecision.DENY, f"a{i}"), actor=ALICE
        )
    async with engine.raw.begin() as conn:
        await conn.execute(text("DELETE FROM governance_policy_history WHERE version = 3"))
    assert await policy.verify_history("org-a") is False  # chain intact, but behind the counter


async def test_a_counter_bumped_without_history_is_out_of_band_modification(repo) -> None:
    policy, engine = repo
    await policy.add_rule("org-a", _rule("r0", GovernanceDecision.DENY, "a"), actor=ALICE)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "UPDATE governance_policy_versions SET version = version + 1 WHERE org_id = 'org-a'"
            )
        )
    assert await policy.verify_history("org-a") is False


async def test_a_never_edited_org_has_a_valid_empty_history(repo) -> None:
    policy, _engine = repo
    assert await policy.verify_history("never-edited") is True
    assert await policy.history_head("never-edited") is None


async def test_history_head_is_the_value_to_anchor_outside_the_database(repo) -> None:
    policy, _engine = repo
    await policy.add_rule("org-a", _rule("r0", GovernanceDecision.DENY, "a"), actor=ALICE)
    first = await policy.history_head("org-a")
    await policy.add_rule("org-a", _rule("r1", GovernanceDecision.DENY, "b"), actor=ALICE)
    second = await policy.history_head("org-a")
    assert first is not None and second is not None
    assert second["version"] == first["version"] + 1
    assert second["entry_digest"] != first["entry_digest"]


async def test_activating_a_lifecycle_revision_writes_history_in_the_same_transaction(repo) -> None:
    import uuid

    from sqlalchemy import insert

    from responsibleai.db.engine import organizations
    from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager

    policy, engine = repo
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id, name="Lifecycle Org", slug=org_id, created_at="2026-10-10T00:00:00Z"
            )
        )
    manager = PolicyLifecycleManager(engine)
    rev = await manager.create_revision(
        org_id, [_rule("lc-1", GovernanceDecision.DENY, "x")], "admin-1", "initial"
    )
    await manager.activate_revision(org_id, rev.id, "admin-1")
    (entry,) = await policy.history(org_id)
    assert (entry["change"], entry["actor_type"], entry["actor_id"]) == (
        "revision_activated",
        "lifecycle",
        "admin-1",
    )
    assert [r["rule_id"] for r in entry["rules"]] == ["lc-1"]
    assert await policy.verify_history(org_id) is True


async def _three_changes(policy) -> None:
    for i in range(3):
        await policy.add_rule(
            "org-a", _rule(f"r{i}", GovernanceDecision.DENY, f"a{i}"), actor=ALICE
        )


async def test_a_gap_in_the_version_sequence_is_detected_even_with_a_consistent_chain(repo) -> None:
    """Re-number and re-chain the survivors so every digest recomputes; the gap alone must fail."""
    policy, engine = repo
    await _three_changes(policy)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE governance_policy_versions SET version = 4 WHERE org_id = 'org-a'")
        )
        await conn.execute(
            text("UPDATE governance_policy_history SET version = 4 WHERE version = 3")
        )
    assert await policy.verify_history("org-a") is False


async def test_the_front_of_the_history_cannot_be_cut_off(repo) -> None:
    policy, engine = repo
    await _three_changes(policy)
    async with engine.raw.begin() as conn:
        await conn.execute(text("DELETE FROM governance_policy_history WHERE version = 1"))
    assert await policy.verify_history("org-a") is False


async def test_a_baseline_row_anywhere_but_first_is_invalid(repo) -> None:
    policy, engine = repo
    await _three_changes(policy)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE governance_policy_history SET change = 'baseline' WHERE version = 2")
        )
    assert await policy.verify_history("org-a") is False


async def test_a_retained_checkpoint_defeats_a_complete_rewrite_that_recomputes_every_digest(
    repo,
) -> None:
    """Someone with write access to both tables can rebuild a self-consistent history. The external
    checkpoint still names the digest the real history had."""
    import hashlib
    import json

    from responsibleai.db.policy_repository import (
        _HISTORY_GENESIS,
        PolicyActor,
        _history_entry_digest,
    )

    policy, engine = repo
    await _three_changes(policy)
    checkpoint = await policy.history_head("org-a")
    assert checkpoint is not None and checkpoint["version"] == 3
    assert await policy.verify_history("org-a", checkpoint=checkpoint) is True

    # Attacker rewrites who made version 2 and rebuilds every digest from there.
    entries = sorted(await policy.history("org-a"), key=lambda e: e["version"])
    prev = _HISTORY_GENESIS
    async with engine.raw.begin() as conn:
        for entry in entries:
            actor = PolicyActor(
                "web_user", "mallory" if entry["version"] == 2 else entry["actor_id"]
            )
            rules_json = json.dumps(entry["rules"], sort_keys=True, separators=(",", ":"))
            rules_digest = hashlib.sha256(rules_json.encode()).hexdigest()
            digest = _history_entry_digest(
                prev,
                "org-a",
                entry["version"],
                entry["change"],
                entry["rule_id"],
                actor,
                rules_digest,
                entry["created_at"],
            )
            await conn.execute(
                text(
                    "UPDATE governance_policy_history SET actor_id = :a, rules_digest = :rd, "
                    "rules_json = :rj, prev_entry_digest = :p, entry_digest = :d WHERE version = :v"
                ),
                {
                    "a": actor.actor_id,
                    "rd": rules_digest,
                    "rj": rules_json,
                    "p": prev,
                    "d": digest,
                    "v": entry["version"],
                },
            )
            prev = digest
    assert await policy.verify_history("org-a") is True, "the rewrite is internally consistent"
    assert await policy.verify_history("org-a", checkpoint=checkpoint) is False


async def test_a_consistent_rollback_of_history_and_counter_is_caught_by_the_checkpoint(
    repo,
) -> None:
    policy, engine = repo
    await _three_changes(policy)
    checkpoint = await policy.history_head("org-a")
    async with engine.raw.begin() as conn:
        await conn.execute(text("DELETE FROM governance_policy_history WHERE version = 3"))
        await conn.execute(
            text("UPDATE governance_policy_versions SET version = 2 WHERE org_id = 'org-a'")
        )
    assert await policy.verify_history("org-a") is True, "internally consistent at version 2"
    assert await policy.verify_history("org-a", checkpoint=checkpoint) is False


async def test_a_checkpoint_from_another_org_or_a_wrong_digest_never_matches(repo) -> None:
    policy, _engine = repo
    await _three_changes(policy)
    await policy.add_rule("org-b", _rule("b0", GovernanceDecision.DENY, "b"), actor=KEY)
    other = await policy.history_head("org-b")
    assert await policy.verify_history("org-a", checkpoint=other) is False
    assert (
        await policy.verify_history("org-a", checkpoint={"version": 3, "entry_digest": "0" * 64})
        is False
    )


async def test_an_edit_authorized_against_an_old_version_is_refused_not_applied(repo) -> None:
    from responsibleai.db.policy_repository import PolicyVersionConflictError

    policy, _engine = repo
    await policy.add_rule("org-a", _rule("r0", GovernanceDecision.DENY, "a"), actor=ALICE)
    version = await policy.get_policy_version("org-a")
    await policy.add_rule("org-a", _rule("r1", GovernanceDecision.DENY, "b"), actor=ALICE)
    with pytest.raises(PolicyVersionConflictError):
        await policy.add_rule(
            "org-a",
            _rule("r2", GovernanceDecision.DENY, "c"),
            actor=ALICE,
            expected_version=version,
        )
    with pytest.raises(PolicyVersionConflictError):
        await policy.remove_rule("org-a", "r0", actor=ALICE, expected_version=version)
    with pytest.raises(PolicyVersionConflictError):
        await policy.reorder("org-a", ["r1", "r0"], actor=ALICE, expected_version=version)
    assert [r.rule_id for r in (await policy.get_policy("org-a")).rules] == ["r0", "r1"]
    await policy.add_rule(
        "org-a",
        _rule("r2", GovernanceDecision.DENY, "c"),
        actor=ALICE,
        expected_version=await policy.get_policy_version("org-a"),
    )
