# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Proofs Engine — Evaluates bounded, factual verification proofs.

Constitutional Doctrine:
- Proves objective factual claims (employment, ownership, authority, credentials).
- Truth valuation: PROVEN, NOT_PROVEN, CONFLICTED, EXPIRED, REVOKED, UNKNOWN, REQUIRES_REVIEW.
- Never outputs subjective character judgments, moral scores, or social rankings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_authority_edges,
    trust_fabric_conflicts,
    trust_fabric_identifiers,
    trust_fabric_principals,
    trust_fabric_relationships,
)
from responsibleai.trust_fabric.directory import normalize_identifier
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
    ProofStatus,
    RelationshipType,
)


class TrustProofEngine:
    """Evaluates objective trust proofs against the Global Trust Fabric."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def prove_employment(self, *, principal_id: str, org_id: str) -> ProofStatus:
        """Prove whether a principal is an active verified employee/director of an organization."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.connect() as conn:
            # Check if principal exists and is active
            p_stmt = select(trust_fabric_principals).where(
                and_(
                    trust_fabric_principals.c.id == principal_id,
                    trust_fabric_principals.c.org_id == org_id,
                )
            )
            p_row = (await conn.execute(p_stmt)).first()
            if not p_row:
                return ProofStatus.UNKNOWN
            if p_row._mapping["lifecycle_state"] in (
                PrincipalState.DELETED.value,
                PrincipalState.DISABLED.value,
            ):
                return ProofStatus.NOT_PROVEN
            if p_row._mapping["lifecycle_state"] == PrincipalState.REVOKED.value:
                return ProofStatus.REVOKED
            if p_row._mapping["lifecycle_state"] == PrincipalState.CONFLICTED.value:
                return ProofStatus.CONFLICTED

            # Check relationship
            rel_stmt = select(trust_fabric_relationships).where(
                and_(
                    trust_fabric_relationships.c.subject_principal_id == principal_id,
                    trust_fabric_relationships.c.org_id == org_id,
                    trust_fabric_relationships.c.relationship_type.in_(
                        [RelationshipType.EMPLOYED_BY.value, RelationshipType.DIRECTOR_OF.value]
                    ),
                )
            )
            rels = (await conn.execute(rel_stmt)).fetchall()
            if not rels:
                return ProofStatus.NOT_PROVEN

            for r in [dict(row._mapping) for row in rels]:
                if r["revoked_at"] is not None:
                    return ProofStatus.REVOKED
                if r["expires_at"] and r["expires_at"] <= now_iso:
                    return ProofStatus.EXPIRED
                if r["verification_state"] == IdentifierVerificationState.VERIFIED.value:
                    return ProofStatus.PROVEN

            return ProofStatus.NOT_PROVEN

    async def prove_signing_authority(
        self,
        *,
        principal_id: str,
        org_id: str,
        amount_usd: float | None = None,
    ) -> ProofStatus:
        """Prove whether a principal holds active signing authority within specified ceiling."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.connect() as conn:
            # Check conflicts
            c_stmt = select(trust_fabric_conflicts).where(
                and_(
                    trust_fabric_conflicts.c.principal_id == principal_id,
                    trust_fabric_conflicts.c.org_id == org_id,
                    trust_fabric_conflicts.c.status == "UNRESOLVED",
                )
            )
            if (await conn.execute(c_stmt)).first():
                return ProofStatus.CONFLICTED

            # Check authority edge
            auth_stmt = select(trust_fabric_authority_edges).where(
                and_(
                    trust_fabric_authority_edges.c.grantee_principal_id == principal_id,
                    trust_fabric_authority_edges.c.org_id == org_id,
                    trust_fabric_authority_edges.c.action_type.in_(
                        ["contract.sign", "payment.disburse", "authority.sign"]
                    ),
                )
            )
            edges = (await conn.execute(auth_stmt)).fetchall()
            if not edges:
                return ProofStatus.NOT_PROVEN

            for e in [dict(row._mapping) for row in edges]:
                if e["revoked_at"] is not None:
                    return ProofStatus.REVOKED
                if e["expires_at"] and e["expires_at"] <= now_iso:
                    return ProofStatus.EXPIRED
                if amount_usd is not None and e["ceiling_limit_usd"] is not None:
                    if amount_usd > e["ceiling_limit_usd"]:
                        return ProofStatus.NOT_PROVEN  # Ceiling exceeded
                return ProofStatus.PROVEN

            return ProofStatus.NOT_PROVEN

    async def prove_agent_ownership(
        self,
        *,
        agent_principal_id: str,
        org_id: str,
    ) -> ProofStatus:
        """Prove whether an AI agent belongs to an organization."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.connect() as conn:
            # Check principal type
            p_stmt = select(trust_fabric_principals).where(
                and_(
                    trust_fabric_principals.c.id == agent_principal_id,
                    trust_fabric_principals.c.org_id == org_id,
                )
            )
            p_row = (await conn.execute(p_stmt)).first()
            if not p_row:
                return ProofStatus.UNKNOWN

            p = dict(p_row._mapping)
            if p["principal_type"] != PrincipalType.AI_AGENT.value:
                return ProofStatus.NOT_PROVEN
            if p["lifecycle_state"] in (PrincipalState.DELETED.value, PrincipalState.DISABLED.value):
                return ProofStatus.NOT_PROVEN
            if p["lifecycle_state"] == PrincipalState.REVOKED.value:
                return ProofStatus.REVOKED

            # Check OWNED_BY relationship
            rel_stmt = select(trust_fabric_relationships).where(
                and_(
                    trust_fabric_relationships.c.subject_principal_id == agent_principal_id,
                    trust_fabric_relationships.c.org_id == org_id,
                    trust_fabric_relationships.c.relationship_type == RelationshipType.OWNED_BY.value,
                )
            )
            rel_row = (await conn.execute(rel_stmt)).first()
            if not rel_row:
                # Direct org_id match is sufficient if in ACTIVE or PENDING_VERIFICATION state
                if p["lifecycle_state"] in (
                    PrincipalState.ACTIVE.value,
                    PrincipalState.PENDING_VERIFICATION.value,
                ):
                    return ProofStatus.PROVEN
                return ProofStatus.NOT_PROVEN

            r = dict(rel_row._mapping)
            if r["revoked_at"] is not None:
                return ProofStatus.REVOKED
            if r["expires_at"] and r["expires_at"] <= now_iso:
                return ProofStatus.EXPIRED

            return ProofStatus.PROVEN

    async def prove_domain_control(
        self,
        *,
        org_id: str,
        domain: str,
    ) -> ProofStatus:
        """Prove whether an organization controls a domain."""
        norm_domain = normalize_identifier(IdentifierType.DOMAIN, domain)
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_identifiers).where(
                and_(
                    trust_fabric_identifiers.c.org_id == org_id,
                    trust_fabric_identifiers.c.identifier_type == IdentifierType.DOMAIN.value,
                    trust_fabric_identifiers.c.normalized_value == norm_domain,
                    trust_fabric_identifiers.c.revoked_at.is_(None),
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                return ProofStatus.UNKNOWN

            rec = dict(row._mapping)
            if rec["verification_state"] == IdentifierVerificationState.VERIFIED.value:
                return ProofStatus.PROVEN
            elif rec["verification_state"] == IdentifierVerificationState.EXPIRED.value:
                return ProofStatus.EXPIRED
            elif rec["verification_state"] == IdentifierVerificationState.REVOKED.value:
                return ProofStatus.REVOKED
            else:
                return ProofStatus.NOT_PROVEN

    async def evaluate_privileged_legitimacy(self, *, principal_id: str, org_id: str) -> ProofStatus:
        """Canonical legitimacy admission claim consulted by the IAM privileged surface guard.

        Dispatches to the existing claim-specific proof appropriate to the principal's
        registered type -- it introduces no new relationship type, claim type, or trust
        score, only a routing layer over primitives that already exist in this engine.
        A principal never registered in the trust fabric under this exact (principal_id,
        org_id) pair is UNKNOWN, not NOT_PROVEN: those are deliberately distinct proof
        states and callers must fail closed on both.
        """
        async with self.db.raw.connect() as conn:
            p_stmt = select(trust_fabric_principals).where(
                and_(
                    trust_fabric_principals.c.id == principal_id,
                    trust_fabric_principals.c.org_id == org_id,
                )
            )
            p_row = (await conn.execute(p_stmt)).first()
        if not p_row:
            return ProofStatus.UNKNOWN

        principal_type = p_row._mapping["principal_type"]
        if principal_type in (PrincipalType.HUMAN.value, PrincipalType.ORGANIZATION.value):
            return await self.prove_employment(principal_id=principal_id, org_id=org_id)
        if principal_type == PrincipalType.AI_AGENT.value:
            return await self.prove_agent_ownership(agent_principal_id=principal_id, org_id=org_id)

        # WORKLOAD / SERVICE / MACHINE principals have no automated claim-specific proof
        # primitive in this engine yet. Route to human review rather than fabricating a
        # new proof primitive or silently allowing an unproven principal type.
        return ProofStatus.REQUIRES_REVIEW

    async def prove_credential(
        self,
        *,
        principal_id: str,
        org_id: str,
        identifier_type: IdentifierType,
        value: str,
    ) -> ProofStatus:
        """Prove whether an identifier credential belongs to a principal."""
        norm_val = normalize_identifier(identifier_type, value)
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_identifiers).where(
                and_(
                    trust_fabric_identifiers.c.principal_id == principal_id,
                    trust_fabric_identifiers.c.org_id == org_id,
                    trust_fabric_identifiers.c.identifier_type == identifier_type.value,
                    trust_fabric_identifiers.c.normalized_value == norm_val,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                return ProofStatus.UNKNOWN

            rec = dict(row._mapping)
            if rec["revoked_at"] is not None:
                return ProofStatus.REVOKED
            if rec["expires_at"] and rec["expires_at"] <= datetime.now(UTC).isoformat():
                return ProofStatus.EXPIRED
            if rec["verification_state"] == IdentifierVerificationState.VERIFIED.value:
                return ProofStatus.PROVEN

            return ProofStatus.NOT_PROVEN
