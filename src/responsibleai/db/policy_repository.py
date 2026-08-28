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

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, governance_policies, governance_policy_versions
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import Policy, PolicyRule
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


async def _bump_version(conn: Any, org_id: str) -> int:
    """Increments `governance_policy_versions`' counter for *org_id* by
    1 (creating the row at version 1 if none exists), within the
    caller's already-open transaction — every mutation below calls this
    inside its own `begin()` block, so the rule-set change and the
    version bump are atomic together, never one without the other."""
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

    async def add_rule(self, org_id: str, rule: PolicyRule) -> None:
        """Appends *rule* at the end of the org's current evaluation
        order (highest existing `position` + 1) — first-match-wins means
        append-by-default is the safe choice; reordering is a separate,
        explicit operation (`reorder`) rather than something `add_rule`
        guesses at."""
        async with self._engine.raw.begin() as conn:
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
            await _bump_version(conn, org_id)

    async def remove_rule(self, org_id: str, rule_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(governance_policies)
                .where(governance_policies.c.org_id == org_id)
                .where(governance_policies.c.rule_id == rule_id)
            )
            if result.rowcount == 0:
                raise PolicyRuleNotFoundError(f"No rule {rule_id!r} for org {org_id!r}")
            await _bump_version(conn, org_id)

    async def reorder(self, org_id: str, rule_ids_in_order: list[str]) -> None:
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
        now = _now()
        async with self._engine.raw.begin() as conn:
            for position, rule_id in enumerate(rule_ids_in_order):
                await conn.execute(
                    update(governance_policies)
                    .where(governance_policies.c.org_id == org_id)
                    .where(governance_policies.c.rule_id == rule_id)
                    .values(position=position, updated_at=now)
                )
            await _bump_version(conn, org_id)
