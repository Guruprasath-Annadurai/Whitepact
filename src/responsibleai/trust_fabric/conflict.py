# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Conflict Resolution Engine.

Core Invariants:
- Explicit Representation: Sources will disagree. Contradictions are explicitly
  recorded as CONFLICTED, never silently ignored.
- Deterministic Resolution Hierarchy:
  1. Higher-tier sources supersede lower-tier sources (e.g. Tier B Legal Registry
     supersedes Tier F Self-attestation).
  2. Fresh authoritative sources supersede stale sources.
  3. Equal-tier direct contradictions cannot be automatically resolved and
     remain UNRESOLVED / REQUIRES_REVIEW.
- Never Silently Upgrade Confidence: In the presence of unresolved material conflicts,
  trust decisions fail closed to REQUIRES_REVIEW or DENY.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_assertions,
    trust_fabric_conflicts,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.enums import (
    ConflictStatus,
    ConflictType,
    PrincipalState,
    SourceTier,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
)
from responsibleai.trust_fabric.models import (
    TrustConflict,
)


class TrustConflictEngine:
    """Manages detection, tracking, and deterministic resolution of trust contradictions."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def record_conflict(
        self,
        *,
        principal_id: str,
        org_id: str,
        field_or_claim: str,
        assertion_id_a: str,
        assertion_id_b: str,
        conflict_type: ConflictType = ConflictType.VALUE_CONTRADICTION,
    ) -> TrustConflict:
        """Record an explicit contradiction between two trust assertions."""
        conflict_id = f"wp_conf_{uuid.uuid4().hex}"
        now_iso = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_conflicts.insert().values(
                    id=conflict_id,
                    principal_id=principal_id,
                    org_id=org_id,
                    field_or_claim=field_or_claim,
                    assertion_id_a=assertion_id_a,
                    assertion_id_b=assertion_id_b,
                    conflict_type=conflict_type.value,
                    detected_at=now_iso,
                    status=ConflictStatus.UNRESOLVED.value,
                    resolution_reason=None,
                    resolved_at=None,
                )
            )
            # Update principal lifecycle to CONFLICTED
            await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == principal_id,
                        trust_fabric_principals.c.org_id == org_id,
                    )
                )
                .values(lifecycle_state=PrincipalState.CONFLICTED.value)
            )

        return TrustConflict(
            id=conflict_id,
            principal_id=principal_id,
            org_id=org_id,
            field_or_claim=field_or_claim,
            assertion_id_a=assertion_id_a,
            assertion_id_b=assertion_id_b,
            conflict_type=conflict_type,
            detected_at=now_iso,
            status=ConflictStatus.UNRESOLVED,
        )

    async def evaluate_and_resolve(
        self,
        conflict_id: str,
        *,
        org_id: str,
    ) -> tuple[ConflictStatus, str]:
        """Deterministically resolve a conflict based on source tier and freshness."""
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_conflicts).where(
                and_(
                    trust_fabric_conflicts.c.id == conflict_id,
                    trust_fabric_conflicts.c.org_id == org_id,
                )
            )
            conf_row = (await conn.execute(stmt)).first()
            if not conf_row:
                raise CrossTenantAccessError(f"Conflict {conflict_id!r} not found for organization {org_id!r}.")

            conf = dict(conf_row._mapping)
            asst_a_stmt = select(trust_fabric_assertions).where(
                trust_fabric_assertions.c.id == conf["assertion_id_a"]
            )
            asst_b_stmt = select(trust_fabric_assertions).where(
                trust_fabric_assertions.c.id == conf["assertion_id_b"]
            )
            row_a = (await conn.execute(asst_a_stmt)).first()
            row_b = (await conn.execute(asst_b_stmt)).first()

        if not row_a or not row_b:
            return ConflictStatus.UNRESOLVED, "One or both conflicting assertions missing."

        a = dict(row_a._mapping)
        b = dict(row_b._mapping)

        tier_rank = {
            SourceTier.TIER_A.value: 1,
            SourceTier.TIER_B.value: 2,
            SourceTier.TIER_C.value: 3,
            SourceTier.TIER_D.value: 4,
            SourceTier.TIER_E.value: 5,
            SourceTier.TIER_F.value: 6,
        }

        rank_a = tier_rank.get(a["source_tier"], 99)
        rank_b = tier_rank.get(b["source_tier"], 99)

        now_iso = datetime.now(UTC).isoformat()

        # Rule 1: Higher tier strictly supersedes lower tier
        if rank_a < rank_b:
            reason = (
                f"Resolved by tier priority: Assertion A ({a['source_tier']}) "
                f"supersedes Assertion B ({b['source_tier']})."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason
        elif rank_b < rank_a:
            reason = (
                f"Resolved by tier priority: Assertion B ({b['source_tier']}) "
                f"supersedes Assertion A ({a['source_tier']})."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # Rule 2: Equal tier — fresh authoritative source supersedes stale
        time_a = datetime.fromisoformat(a["verified_at"])
        time_b = datetime.fromisoformat(b["verified_at"])
        delta = abs((time_a - time_b).total_seconds())

        if delta > 86400 * 30:  # More than 30 days difference
            newer = "A" if time_a > time_b else "B"
            older = "B" if newer == "A" else "A"
            reason = f"Resolved by freshness: Assertion {newer} supersedes older Assertion {older} (>30d diff)."
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # Rule 3: Equal tier, concurrent or direct contradiction -> Cannot auto-resolve
        return ConflictStatus.UNRESOLVED, "Direct contradiction between equal-tier authoritative sources requires human review."

    async def _mark_resolved(self, conflict_id: str, reason: str, timestamp: str) -> None:
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_conflicts)
                .where(trust_fabric_conflicts.c.id == conflict_id)
                .values(
                    status=ConflictStatus.RESOLVED_SUPERSEDED.value,
                    resolution_reason=reason,
                    resolved_at=timestamp,
                )
            )
