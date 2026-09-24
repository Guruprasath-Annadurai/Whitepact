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
    ClaimType,
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

CLAIM_AUTHORITATIVE_SOURCE_TIERS: dict[ClaimType, set[str]] = {
    ClaimType.LEGAL_ENTITY_EXISTENCE: {SourceTier.TIER_B.value, SourceTier.TIER_A.value},
    ClaimType.LEGAL_ENTITY_STATUS: {SourceTier.TIER_B.value, SourceTier.TIER_A.value},
    ClaimType.CURRENT_EMPLOYMENT: {SourceTier.TIER_C.value, SourceTier.TIER_D.value},
    ClaimType.CURRENT_ORGANIZATION_ROLE: {SourceTier.TIER_C.value, SourceTier.TIER_A.value},
    ClaimType.CURRENT_DELEGATED_AUTHORITY: {SourceTier.TIER_A.value, SourceTier.TIER_C.value},
    ClaimType.DOMAIN_CONTROL: {SourceTier.TIER_A.value, SourceTier.TIER_C.value},
    ClaimType.EMAIL_CONTROL: {SourceTier.TIER_C.value, SourceTier.TIER_D.value},
    ClaimType.KEY_POSSESSION: {SourceTier.TIER_A.value},
    ClaimType.AGENT_OWNERSHIP: {SourceTier.TIER_C.value, SourceTier.TIER_A.value},
    ClaimType.WORKLOAD_IDENTITY: {SourceTier.TIER_A.value, SourceTier.TIER_C.value},
    ClaimType.PUBLIC_PROFESSIONAL_ASSERTION: {SourceTier.TIER_E.value, SourceTier.TIER_F.value},
}


def normalize_to_claim_type(field_or_claim: str) -> ClaimType:
    """Map field or claim name to canonical ClaimType."""
    name = field_or_claim.strip().upper()
    try:
        return ClaimType(name)
    except ValueError:
        pass

    if any(k in name for k in {"LEGAL_NAME", "REGISTRATION", "INCORPORATION", "JURISDICTION"}):
        return ClaimType.LEGAL_ENTITY_EXISTENCE
    if any(k in name for k in {"STATUS", "DISSOLUTION", "BANKRUPTCY"}):
        return ClaimType.LEGAL_ENTITY_STATUS
    if any(k in name for k in {"EMPLOYMENT", "EMPLOYER", "TERMINATION"}):
        return ClaimType.CURRENT_EMPLOYMENT
    if any(k in name for k in {"ROLE", "TITLE", "DEPARTMENT"}):
        return ClaimType.CURRENT_ORGANIZATION_ROLE
    if any(k in name for k in {"AUTHORITY", "DELEGATION", "CEILING", "LIMIT"}):
        return ClaimType.CURRENT_DELEGATED_AUTHORITY
    if any(k in name for k in {"DOMAIN", "DNS"}):
        return ClaimType.DOMAIN_CONTROL
    if any(k in name for k in {"EMAIL", "MAIL"}):
        return ClaimType.EMAIL_CONTROL
    if any(k in name for k in {"KEY", "PUBLIC_KEY", "SIGNING_KEY", "FINGERPRINT", "FP"}):
        return ClaimType.KEY_POSSESSION
    if any(k in name for k in {"OWNER", "AGENT_OWNER"}):
        return ClaimType.AGENT_OWNERSHIP
    if any(k in name for k in {"WORKLOAD", "IP", "ALLOWLIST", "ENDPOINT", "CONTAINER"}):
        return ClaimType.WORKLOAD_IDENTITY

    return ClaimType.PUBLIC_PROFESSIONAL_ASSERTION


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
                raise CrossTenantAccessError(
                    f"Conflict {conflict_id!r} not found for organization {org_id!r}."
                )

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

        claim_type = normalize_to_claim_type(conf["field_or_claim"])
        auth_tiers = CLAIM_AUTHORITATIVE_SOURCE_TIERS.get(
            claim_type, {SourceTier.TIER_A.value, SourceTier.TIER_B.value}
        )

        a_is_auth = a["source_tier"] in auth_tiers
        b_is_auth = b["source_tier"] in auth_tiers

        now_iso = datetime.now(UTC).isoformat()
        time_a = datetime.fromisoformat(a["verified_at"])
        time_b = datetime.fromisoformat(b["verified_at"])

        revocation_values = {
            "TERMINATED",
            "REVOKED",
            "REMOVED",
            "INACTIVE",
            "FALSE",
            "DISSOLVED",
            "DELETED",
        }
        a_is_revocation = str(a.get("field_value", "")).upper() in revocation_values
        b_is_revocation = str(b.get("field_value", "")).upper() in revocation_values

        # Rule 1: Claim-specific authoritative source strictly supersedes non-authoritative source
        # (e.g., Enterprise HRIdP Tier C supersedes old Statutory Registry Tier B for CURRENT_EMPLOYMENT)
        if a_is_auth and not b_is_auth:
            reason = (
                f"Resolved by claim-specific authority: Assertion A ({a['source_tier']}) is authoritative "
                f"for {claim_type.value} and supersedes non-authoritative Assertion B ({b['source_tier']})."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason
        elif b_is_auth and not a_is_auth:
            reason = (
                f"Resolved by claim-specific authority: Assertion B ({b['source_tier']}) is authoritative "
                f"for {claim_type.value} and supersedes non-authoritative Assertion A ({a['source_tier']})."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # If NEITHER is authoritative, do NOT escalate via generic tiers: fail closed
        if not a_is_auth and not b_is_auth:
            return (
                ConflictStatus.UNRESOLVED,
                f"Neither source ({a['source_tier']}, {b['source_tier']}) is authoritative for {claim_type.value}.",
            )

        # BOTH are within authoritative source domain for this claim:
        # Rule 2: Fresh authoritative revocation strictly supersedes stale positive claim
        if a_is_revocation and not b_is_revocation and time_a >= time_b:
            reason = f"Resolved by fresh authoritative revocation: Assertion A ({claim_type.value} revoked) supersedes Assertion B."
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason
        elif b_is_revocation and not a_is_revocation and time_b >= time_a:
            reason = f"Resolved by fresh authoritative revocation: Assertion B ({claim_type.value} revoked) supersedes Assertion A."
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # Rule 3: Authoritative tier priority within the authoritative domain
        rank_a = tier_rank.get(a["source_tier"], 99)
        rank_b = tier_rank.get(b["source_tier"], 99)

        if rank_a < rank_b:
            reason = (
                f"Resolved by tier priority within authoritative domain: Assertion A ({a['source_tier']}) "
                f"supersedes Assertion B ({b['source_tier']}) for {claim_type.value}."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason
        elif rank_b < rank_a:
            reason = (
                f"Resolved by tier priority within authoritative domain: Assertion B ({b['source_tier']}) "
                f"supersedes Assertion A ({a['source_tier']}) for {claim_type.value}."
            )
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # Rule 4: Equal tier — fresh authoritative source supersedes stale
        delta = abs((time_a - time_b).total_seconds())

        if delta > 86400 * 30:  # More than 30 days difference
            newer = "A" if time_a > time_b else "B"
            older = "B" if newer == "A" else "A"
            reason = f"Resolved by freshness: Assertion {newer} supersedes older Assertion {older} (>30d diff) for {claim_type.value}."
            await self._mark_resolved(conflict_id, reason, now_iso)
            return ConflictStatus.RESOLVED_SUPERSEDED, reason

        # Rule 5: Equal tier, concurrent or direct contradiction -> Cannot auto-resolve
        return (
            ConflictStatus.UNRESOLVED,
            f"Direct contradiction between equal-tier authoritative sources for {claim_type.value} requires human review.",
        )

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
