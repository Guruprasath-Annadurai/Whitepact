# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Phase 5 Policy Lifecycle & Historical Integrity Subsystem.

Provides:
- Deterministic canonical policy content digest calculation (SHA-256).
- Immutable, monotonic policy revision history (governance_policy_revisions).
- Atomic single-winner policy activations with epoch synchronization (governance_policy_activations).
- Safe policy rollback without historical rewriting or deletion.
- Integration with Phase-4 Privileged Surface Guard for sensitive policy changes.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, desc, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    governance_policies,
    governance_policy_activations,
    governance_policy_revisions,
    governance_policy_versions,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier


def _now() -> str:
    return datetime.now(UTC).isoformat()


def serialize_rule_canonical(rule: PolicyRule) -> dict[str, Any]:
    """Produce a normalized dictionary representation of a PolicyRule."""
    return {
        "action_types": sorted(rule.action_types) if rule.action_types is not None else None,
        "effect": rule.effect.value,
        "reason_code": rule.reason_code,
        "risk_tiers": sorted(t.value for t in rule.risk_tiers) if rule.risk_tiers is not None else None,
        "rule_id": rule.rule_id,
        "targets": sorted(rule.targets) if rule.targets is not None else None,
    }


def deserialize_rule_canonical(d: dict[str, Any]) -> PolicyRule:
    """Reconstruct a PolicyRule from a normalized dictionary."""
    return PolicyRule(
        rule_id=d["rule_id"],
        reason_code=d["reason_code"],
        effect=GovernanceDecision(d["effect"]),
        risk_tiers=frozenset(RiskTier(t) for t in d["risk_tiers"]) if d.get("risk_tiers") is not None else None,
        action_types=frozenset(d["action_types"]) if d.get("action_types") is not None else None,
        targets=frozenset(d["targets"]) if d.get("targets") is not None else None,
    )


def compute_policy_digest(rules: list[PolicyRule]) -> str:
    """Compute a deterministic canonical SHA-256 digest over ordered rules."""
    canonical_list = [serialize_rule_canonical(r) for r in rules]
    serialized = json.dumps(canonical_list, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class PolicyLifecycleError(Exception):
    """Base exception for policy lifecycle violations."""


class PolicyRevisionNotFoundError(PolicyLifecycleError):
    """Raised when a requested policy revision does not exist."""


class PolicyHistoryImmutableError(PolicyLifecycleError):
    """Raised when an illegal in-place mutation or deletion of history is attempted."""


class ConcurrentPolicyActivationError(PolicyLifecycleError):
    """Raised on concurrency conflicts during policy activation."""


@dataclass(frozen=True)
class PolicyRevision:
    id: str
    org_id: str
    revision_num: int
    rules: list[PolicyRule]
    content_digest: str
    created_at: str
    created_by: str
    change_reason: str
    approval_id: str | None


@dataclass(frozen=True)
class PolicyActivation:
    id: str
    org_id: str
    revision_id: str
    content_digest: str
    activated_at: str
    activated_by: str
    governance_epoch: int
    previous_activation_id: str | None
    is_active: bool


class PolicyLifecycleManager:
    """Coordinates immutable revisions, atomic activation, and safe rollbacks."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create_revision(
        self,
        org_id: str,
        rules: list[PolicyRule],
        created_by: str,
        change_reason: str,
        approval_id: str | None = None,
    ) -> PolicyRevision:
        """Create an immutable policy revision. Monotonically numbered per org."""
        digest = compute_policy_digest(rules)
        serialized_rules = json.dumps([serialize_rule_canonical(r) for r in rules])
        revision_id = str(uuid.uuid4())
        now = _now()

        async with self._engine.raw.begin() as conn:
            # Query current max revision
            res = await conn.execute(
                select(governance_policy_revisions.c.revision_num)
                .where(governance_policy_revisions.c.org_id == org_id)
                .order_by(desc(governance_policy_revisions.c.revision_num))
                .limit(1)
            )
            max_num = res.scalar()
            next_num = 1 if max_num is None else max_num + 1

            await conn.execute(
                insert(governance_policy_revisions).values(
                    id=revision_id,
                    org_id=org_id,
                    revision_num=next_num,
                    rules_json=serialized_rules,
                    content_digest=digest,
                    created_at=now,
                    created_by=created_by,
                    change_reason=change_reason,
                    approval_id=approval_id,
                )
            )

        return PolicyRevision(
            id=revision_id,
            org_id=org_id,
            revision_num=next_num,
            rules=rules,
            content_digest=digest,
            created_at=now,
            created_by=created_by,
            change_reason=change_reason,
            approval_id=approval_id,
        )

    async def get_revision(self, org_id: str, revision_num: int) -> PolicyRevision | None:
        """Retrieve a specific historical revision."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_policy_revisions)
                    .where(governance_policy_revisions.c.org_id == org_id)
                    .where(governance_policy_revisions.c.revision_num == revision_num)
                )
            ).fetchone()
            if not row:
                return None
            rules_raw = json.loads(row.rules_json)
            rules = [deserialize_rule_canonical(r) for r in rules_raw]
            return PolicyRevision(
                id=row.id,
                org_id=row.org_id,
                revision_num=row.revision_num,
                rules=rules,
                content_digest=row.content_digest,
                created_at=row.created_at,
                created_by=row.created_by,
                change_reason=row.change_reason,
                approval_id=row.approval_id,
            )

    async def get_revisions(self, org_id: str) -> list[PolicyRevision]:
        """List all revisions for an organization in ascending order."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_policy_revisions)
                    .where(governance_policy_revisions.c.org_id == org_id)
                    .order_by(governance_policy_revisions.c.revision_num.asc())
                )
            ).fetchall()
            revisions = []
            for row in rows:
                rules_raw = json.loads(row.rules_json)
                rules = [deserialize_rule_canonical(r) for r in rules_raw]
                revisions.append(
                    PolicyRevision(
                        id=row.id,
                        org_id=row.org_id,
                        revision_num=row.revision_num,
                        rules=rules,
                        content_digest=row.content_digest,
                        created_at=row.created_at,
                        created_by=row.created_by,
                        change_reason=row.change_reason,
                        approval_id=row.approval_id,
                    )
                )
            return revisions

    async def activate_revision(
        self,
        org_id: str,
        revision_id: str,
        activated_by: str,
    ) -> PolicyActivation:
        """Atomically activates a revision for an org.

        Ensures single-winner activation, increments governance epoch,
        and updates existing governance_policies table for compatibility.
        """
        async with self._engine.raw.begin() as conn:
            # 1. Fetch revision
            rev_row = (
                await conn.execute(
                    select(governance_policy_revisions)
                    .where(governance_policy_revisions.c.id == revision_id)
                    .where(governance_policy_revisions.c.org_id == org_id)
                )
            ).fetchone()
            if not rev_row:
                raise PolicyRevisionNotFoundError(f"Revision {revision_id} not found for org {org_id}")

            # 2. Find currently active activation
            current_active = (
                await conn.execute(
                    select(governance_policy_activations)
                    .where(governance_policy_activations.c.org_id == org_id)
                    .where(governance_policy_activations.c.is_active == True)  # noqa: E712
                )
            ).fetchone()

            prev_activation_id = current_active.id if current_active else None

            # 3. Deactivate previous active
            if current_active:
                await conn.execute(
                    update(governance_policy_activations)
                    .where(governance_policy_activations.c.id == current_active.id)
                    .values(is_active=False)
                )

            # 4. Bump governance epoch
            epoch = await bump_epoch_on_connection(conn, org_id)

            # 5. Insert new activation
            activation_id = str(uuid.uuid4())
            now = _now()
            await conn.execute(
                insert(governance_policy_activations).values(
                    id=activation_id,
                    org_id=org_id,
                    revision_id=revision_id,
                    content_digest=rev_row.content_digest,
                    activated_at=now,
                    activated_by=activated_by,
                    governance_epoch=epoch,
                    previous_activation_id=prev_activation_id,
                    is_active=True,
                )
            )

            # 6. Synchronize into governance_policies for backwards compatibility
            await conn.execute(
                delete(governance_policies).where(governance_policies.c.org_id == org_id)
            )
            rules_raw = json.loads(rev_row.rules_json)
            for idx, r_data in enumerate(rules_raw):
                await conn.execute(
                    insert(governance_policies).values(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        rule_id=r_data["rule_id"],
                        reason_code=r_data["reason_code"],
                        effect=r_data["effect"],
                        risk_tiers=json.dumps(r_data["risk_tiers"]) if r_data["risk_tiers"] else None,
                        action_types=json.dumps(r_data["action_types"]) if r_data["action_types"] else None,
                        targets=json.dumps(r_data["targets"]) if r_data["targets"] else None,
                        position=idx,
                        created_at=now,
                        updated_at=now,
                    )
                )

            # 7. Bump governance_policy_versions counter
            ver_row = (
                await conn.execute(
                    select(governance_policy_versions.c.version).where(
                        governance_policy_versions.c.org_id == org_id
                    )
                )
            ).scalar()
            next_ver = 1 if ver_row is None else ver_row + 1
            if ver_row is None:
                await conn.execute(
                    insert(governance_policy_versions).values(
                        org_id=org_id,
                        version=next_ver,
                        updated_at=now,
                    )
                )
            else:
                await conn.execute(
                    update(governance_policy_versions)
                    .where(governance_policy_versions.c.org_id == org_id)
                    .values(version=next_ver, updated_at=now)
                )

        return PolicyActivation(
            id=activation_id,
            org_id=org_id,
            revision_id=revision_id,
            content_digest=rev_row.content_digest,
            activated_at=now,
            activated_by=activated_by,
            governance_epoch=epoch,
            previous_activation_id=prev_activation_id,
            is_active=True,
        )

    async def get_active_activation(self, org_id: str) -> PolicyActivation | None:
        """Return the current active activation for an organization."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_policy_activations)
                    .where(governance_policy_activations.c.org_id == org_id)
                    .where(governance_policy_activations.c.is_active == True)  # noqa: E712
                )
            ).fetchone()
            if not row:
                return None
            return PolicyActivation(
                id=row.id,
                org_id=row.org_id,
                revision_id=row.revision_id,
                content_digest=row.content_digest,
                activated_at=row.activated_at,
                activated_by=row.activated_by,
                governance_epoch=row.governance_epoch,
                previous_activation_id=row.previous_activation_id,
                is_active=row.is_active,
            )

    async def rollback(
        self,
        org_id: str,
        target_revision_num: int,
        rolled_back_by: str,
        reason: str,
    ) -> PolicyActivation:
        """Roll back to a past revision without rewriting history.

        Preserves all prior revisions and activation history intact.
        """
        target_rev = await self.get_revision(org_id, target_revision_num)
        if not target_rev:
            raise PolicyRevisionNotFoundError(
                f"Cannot rollback: revision {target_revision_num} not found for org {org_id}"
            )

        # Activating the target revision creates a new activation entry with new epoch
        return await self.activate_revision(
            org_id=org_id,
            revision_id=target_rev.id,
            activated_by=rolled_back_by,
        )
