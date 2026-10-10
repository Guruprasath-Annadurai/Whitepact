# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for persisted governance policy rules (gap-closure
work tracked in MIGRATION_WHITEPACT_V2.md Section 8.2: policy rules
previously existed only as in-code `PolicyRule`/`Policy` objects built
fresh per call site — never stored, never queryable, never editable
without a deploy).

`Policy.evaluate()` is first-match-wins over an ordered list — `position`
here is that order, persisted so it survives process restarts. Building
a richer rule language (OPA/Rego) remains explicitly out of scope, per
`governance/policy.py`'s own docstring; this repository stores exactly
the same flat, typed `PolicyRule` shape that module already defines.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    governance_policies,
    governance_policy_history,
    governance_policy_versions,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import Policy, PolicyRule, reject_shadowed_restrictive_rules
from responsibleai.governance.risk import RiskTier


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_rule(row: Any) -> PolicyRule:
    risk_tiers = json.loads(row.risk_tiers) if row.risk_tiers else None
    action_types = json.loads(row.action_types) if row.action_types else None
    targets = json.loads(row.targets) if row.targets else None
    return PolicyRule(
        rule_id=row.rule_id,
        reason_code=row.reason_code,
        effect=GovernanceDecision(row.effect),
        risk_tiers=frozenset(RiskTier(t) for t in risk_tiers) if risk_tiers else None,
        action_types=frozenset(action_types) if action_types else None,
        targets=frozenset(targets) if targets else None,
    )


class PolicyRuleNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class PolicyActor:
    """Who made a policy change. Recorded in the append-only history, never inferred later."""

    actor_type: str  # "web_user" | "api_key" | "system"
    actor_id: str


UNATTRIBUTED = PolicyActor("unattributed", "unattributed")
_HISTORY_GENESIS = "0" * 64


def _rule_to_snapshot(rule: PolicyRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "reason_code": rule.reason_code,
        "effect": rule.effect.value,
        "risk_tiers": sorted(t.value for t in rule.risk_tiers) if rule.risk_tiers else None,
        "action_types": sorted(rule.action_types) if rule.action_types else None,
        "targets": sorted(rule.targets) if rule.targets else None,
    }


def _history_entry_digest(
    prev: str,
    org_id: str,
    version: int,
    change: str,
    rule_id: str | None,
    actor: PolicyActor,
    rules_digest: str,
    created_at: str,
) -> str:
    material = "|".join(
        [
            prev,
            org_id,
            str(version),
            change,
            rule_id or "",
            actor.actor_type,
            actor.actor_id,
            rules_digest,
            created_at,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _record_history(
    conn: Any,
    org_id: str,
    version: int,
    change: str,
    rule_id: str | None,
    actor: PolicyActor,
) -> None:
    """Append the post-change rule set to the org's history, in the mutation's own transaction."""
    rows = (
        await conn.execute(
            select(governance_policies)
            .where(governance_policies.c.org_id == org_id)
            .order_by(governance_policies.c.position.asc())
        )
    ).fetchall()
    rules_json = json.dumps(
        [_rule_to_snapshot(_row_to_rule(row)) for row in rows],
        sort_keys=True,
        separators=(",", ":"),
    )
    rules_digest = hashlib.sha256(rules_json.encode("utf-8")).hexdigest()
    prev = (
        await conn.execute(
            select(governance_policy_history.c.entry_digest)
            .where(governance_policy_history.c.org_id == org_id)
            .order_by(governance_policy_history.c.version.desc())
            .limit(1)
        )
    ).scalar() or _HISTORY_GENESIS
    created_at = _now()
    await conn.execute(
        insert(governance_policy_history).values(
            id=str(uuid.uuid4()),
            org_id=org_id,
            version=version,
            change=change,
            rule_id=rule_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            rules_json=rules_json,
            rules_digest=rules_digest,
            prev_entry_digest=prev,
            entry_digest=_history_entry_digest(
                prev, org_id, version, change, rule_id, actor, rules_digest, created_at
            ),
            created_at=created_at,
        )
    )


async def _bump_version(conn: Any, org_id: str) -> int:
    """Increments `governance_policy_versions`' counter for *org_id* by
    1 (creating the row at version 1 if none exists), within the
    caller's already-open transaction — every mutation below calls this
    inside its own `begin()` block, so the rule-set change and the
    version bump are atomic together, never one without the other."""
    await bump_epoch_on_connection(conn, org_id)
    current = (
        await conn.execute(
            select(governance_policy_versions.c.version).where(
                governance_policy_versions.c.org_id == org_id
            )
        )
    ).scalar()
    now = _now()
    next_version = 1 if current is None else current + 1
    if current is None:
        await conn.execute(
            insert(governance_policy_versions).values(
                org_id=org_id,
                version=next_version,
                updated_at=now,
            )
        )
    else:
        await conn.execute(
            update(governance_policy_versions)
            .where(governance_policy_versions.c.org_id == org_id)
            .values(version=next_version, updated_at=now)
        )
    return next_version


class PolicyRepository:
    """CRUD over one ordered rule set per organization."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get_policy_version(self, org_id: str) -> int:
        """0 for an org that has never mutated its rule set — matches
        `Policy.version`'s own documented default for an unpersisted
        `Policy`, so a never-touched org's evaluations are indistinguishable
        from "no real version exists yet," which is the honest state."""
        async with self._engine.raw.connect() as conn:
            version = (
                await conn.execute(
                    select(governance_policy_versions.c.version).where(
                        governance_policy_versions.c.org_id == org_id
                    )
                )
            ).scalar()
        return version or 0

    async def get_policy(self, org_id: str) -> Policy:
        """Always returns a `Policy` — empty (no rules) if the org has
        never added one, matching `WhitePactRuntimeGateway.evaluate()`'s
        existing "no policy supplied" behavior when nothing matches."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_policies)
                    .where(governance_policies.c.org_id == org_id)
                    .order_by(governance_policies.c.position.asc())
                )
            ).fetchall()
        version = await self.get_policy_version(org_id)
        return Policy(org_id=org_id, rules=[_row_to_rule(r) for r in rows], version=version)

    async def add_rule(
        self, org_id: str, rule: PolicyRule, *, actor: PolicyActor | None = None
    ) -> None:
        """Appends *rule* at the end of the org's current evaluation
        order (highest existing `position` + 1). Appending a stricter
        rule that an earlier rule already covers is rejected: first-match
        would never reach it."""
        async with self._engine.raw.begin() as conn:
            existing_rows = (
                await conn.execute(
                    select(governance_policies)
                    .where(governance_policies.c.org_id == org_id)
                    .order_by(governance_policies.c.position.asc())
                )
            ).fetchall()
            reject_shadowed_restrictive_rules([*(_row_to_rule(row) for row in existing_rows), rule])
            max_pos = (
                await conn.execute(
                    select(governance_policies.c.position)
                    .where(governance_policies.c.org_id == org_id)
                    .order_by(governance_policies.c.position.desc())
                    .limit(1)
                )
            ).scalar()
            next_pos = 0 if max_pos is None else max_pos + 1
            now = _now()
            await conn.execute(
                insert(governance_policies).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    rule_id=rule.rule_id,
                    reason_code=rule.reason_code,
                    effect=rule.effect.value,
                    risk_tiers=json.dumps(sorted(t.value for t in rule.risk_tiers))
                    if rule.risk_tiers
                    else None,
                    action_types=json.dumps(sorted(rule.action_types))
                    if rule.action_types
                    else None,
                    targets=json.dumps(sorted(rule.targets)) if rule.targets else None,
                    position=next_pos,
                    created_at=now,
                    updated_at=now,
                )
            )
            version = await _bump_version(conn, org_id)
            await _record_history(
                conn, org_id, version, "rule_added", rule.rule_id, actor or UNATTRIBUTED
            )

    async def remove_rule(
        self, org_id: str, rule_id: str, *, actor: PolicyActor | None = None
    ) -> None:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(governance_policies)
                .where(governance_policies.c.org_id == org_id)
                .where(governance_policies.c.rule_id == rule_id)
            )
            if result.rowcount == 0:
                raise PolicyRuleNotFoundError(f"No rule {rule_id!r} for org {org_id!r}")
            version = await _bump_version(conn, org_id)
            await _record_history(
                conn, org_id, version, "rule_removed", rule_id, actor or UNATTRIBUTED
            )

    async def reorder(
        self,
        org_id: str,
        rule_ids_in_order: list[str],
        *,
        actor: PolicyActor | None = None,
    ) -> None:
        """Replaces the org's evaluation order wholesale — every existing
        `rule_id` must appear exactly once, or this raises rather than
        silently dropping/duplicating a rule (a corrupted policy order is
        a security-relevant bug, not a best-effort operation)."""
        current = await self.get_policy(org_id)
        current_ids = {r.rule_id for r in current.rules}
        if set(rule_ids_in_order) != current_ids:
            raise ValueError(
                f"reorder() must include exactly the org's current rule_ids "
                f"{sorted(current_ids)}, got {sorted(rule_ids_in_order)}"
            )
        by_id = {rule.rule_id: rule for rule in current.rules}
        reject_shadowed_restrictive_rules([by_id[rule_id] for rule_id in rule_ids_in_order])
        now = _now()
        async with self._engine.raw.begin() as conn:
            for position, rule_id in enumerate(rule_ids_in_order):
                await conn.execute(
                    update(governance_policies)
                    .where(governance_policies.c.org_id == org_id)
                    .where(governance_policies.c.rule_id == rule_id)
                    .values(position=position, updated_at=now)
                )
            version = await _bump_version(conn, org_id)
            await _record_history(conn, org_id, version, "reordered", None, actor or UNATTRIBUTED)

    async def history(self, org_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Newest-first policy changes for one organization: who, what, and the rules in force."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_policy_history)
                    .where(governance_policy_history.c.org_id == org_id)
                    .order_by(governance_policy_history.c.version.desc())
                    .limit(max(1, min(limit, 1000)))
                )
            ).fetchall()
        return [
            {
                "version": row.version,
                "change": row.change,
                "rule_id": row.rule_id,
                "actor_type": row.actor_type,
                "actor_id": row.actor_id,
                "rules": json.loads(row.rules_json),
                "rules_digest": row.rules_digest,
                "entry_digest": row.entry_digest,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    async def verify_history(self, org_id: str) -> bool:
        """Recompute the org's history chain. False if any row was altered, removed or reordered."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_policy_history)
                    .where(governance_policy_history.c.org_id == org_id)
                    .order_by(governance_policy_history.c.version.asc())
                )
            ).fetchall()
        prev = _HISTORY_GENESIS
        for row in rows:
            if hashlib.sha256(row.rules_json.encode("utf-8")).hexdigest() != row.rules_digest:
                return False
            actor = PolicyActor(row.actor_type, row.actor_id)
            expected = _history_entry_digest(
                prev,
                org_id,
                row.version,
                row.change,
                row.rule_id,
                actor,
                row.rules_digest,
                row.created_at,
            )
            if row.prev_entry_digest != prev or row.entry_digest != expected:
                return False
            prev = row.entry_digest
        return True
