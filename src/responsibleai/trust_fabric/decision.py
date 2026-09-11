# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Decision API & Enterprise Gating Engine.

Core Invariants:
- Gating decisions bind request context: requesting org, target org, subject principal,
  requested action, resource, amount ceiling, and evidence provenance.
- Explainable outputs: returns explicit reasons (e.g. CEILING_EXCEEDED, RELATIONSHIP_REVOKED)
  without leaking private confidential data.
- Never a universal reputation score: outputs multidimensional assurance and boolean/state judgments.
- Unknown principal handling: unknown entities return UNKNOWN / REQUIRE_VERIFICATION.
"""

from __future__ import annotations

from responsibleai.db.engine import DatabaseEngine
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DecisionOutcome,
    PrincipalState,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    PrincipalNotFoundError,
)
from responsibleai.trust_fabric.models import (
    AssuranceVector,
    TrustDecisionRequest,
    TrustDecisionResponse,
)
from responsibleai.trust_fabric.monitor import ContinuousTrustMonitor
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


class TrustDecisionEngine:
    """Evaluates high-consequence business actions against the Global Trust Fabric."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.directory = PrincipalDirectory(db)
        self.provenance = TrustProvenanceEngine(db)
        self.authority = AuthorityGraph(db)
        self.monitor = ContinuousTrustMonitor(db)

    async def evaluate_decision(self, request: TrustDecisionRequest) -> TrustDecisionResponse:
        """Evaluate whether a requested interaction or transaction can legitimately proceed."""
        cache_key = (
            f"{request.requesting_org_id}:{request.target_org_id}:"
            f"{request.subject_principal_id}:{request.requested_action}:"
            f"{request.context.get('amount_usd')}"
        )
        cached = self.monitor.get_cached_decision(cache_key)
        if cached is not None:
            return cached

        # 1. Identity Resolution
        try:
            principal = await self.directory.get_principal(
                request.subject_principal_id, org_id=request.target_org_id
            )
        except PrincipalNotFoundError:
            assurance = AssuranceVector(
                identity_assurance=AssuranceLevel.LOW,
                affiliation_assurance=AssuranceLevel.LOW,
                authority_assurance=AssuranceLevel.LOW,
                source_freshness="UNKNOWN",
                credential_state="UNKNOWN",
                conflict_state="NONE",
            )
            return TrustDecisionResponse(
                decision=DecisionOutcome.UNKNOWN,
                reason_code="PRINCIPAL_UNKNOWN",
                explanation=f"Subject principal {request.subject_principal_id!r} is unknown to WhitePact.",
                assurance=assurance,
                evidence_references=(),
            )
        except CrossTenantAccessError:
            assurance = AssuranceVector(
                identity_assurance=AssuranceLevel.LOW,
                affiliation_assurance=AssuranceLevel.LOW,
                authority_assurance=AssuranceLevel.LOW,
                source_freshness="UNKNOWN",
                credential_state="UNKNOWN",
                conflict_state="NONE",
            )
            return TrustDecisionResponse(
                decision=DecisionOutcome.DENY,
                reason_code="CROSS_TENANT_DISALLOWED",
                explanation="Subject principal does not belong to target organization.",
                assurance=assurance,
                evidence_references=(),
            )

        # 2. Lifecycle Check
        if principal.lifecycle_state in (PrincipalState.DELETED, PrincipalState.DISABLED):
            assurance = await self.provenance.evaluate_assurance_vector(
                principal.id, org_id=request.target_org_id
            )
            return TrustDecisionResponse(
                decision=DecisionOutcome.DENY,
                reason_code="PRINCIPAL_INACTIVE",
                explanation=f"Subject principal is currently in {principal.lifecycle_state.value} state.",
                assurance=assurance,
                evidence_references=(),
            )

        if principal.lifecycle_state == PrincipalState.REVOKED:
            assurance = await self.provenance.evaluate_assurance_vector(
                principal.id, org_id=request.target_org_id
            )
            return TrustDecisionResponse(
                decision=DecisionOutcome.DENY,
                reason_code="PRINCIPAL_REVOKED",
                explanation="Subject principal identity or credentials have been revoked.",
                assurance=assurance,
                evidence_references=(),
            )

        # 3. Assurance & Conflict Evaluation
        assurance = await self.provenance.evaluate_assurance_vector(
            principal.id, org_id=request.target_org_id
        )

        if assurance.conflict_state == "CONFLICTED" or principal.lifecycle_state == PrincipalState.CONFLICTED:
            return TrustDecisionResponse(
                decision=DecisionOutcome.REQUIRES_REVIEW,
                reason_code="TRUST_CONFLICT_DETECTED",
                explanation="Independent authoritative sources are in contradiction regarding this principal.",
                assurance=assurance,
                evidence_references=(),
            )

        # 4. Authority Evaluation
        amount_usd = request.context.get("amount_usd")
        resource = request.context.get("resource", "*")

        is_auth, auth_reason, auth_edge = await self.authority.check_authority(
            grantee_principal_id=principal.id,
            org_id=request.target_org_id,
            action_type=request.requested_action,
            resource=resource,
            amount_usd=amount_usd,
        )

        if not is_auth:
            outcome = (
                DecisionOutcome.DENY
                if "exceeded" in auth_reason.lower() or "no_matching" in auth_reason.lower()
                else DecisionOutcome.REQUIRES_REVIEW
            )
            code = "AUTHORITY_CEILING_EXCEEDED" if "exceeded" in auth_reason.lower() else "AUTHORITY_NOT_SATISFIED"
            resp = TrustDecisionResponse(
                decision=outcome,
                reason_code=code,
                explanation=auth_reason,
                assurance=assurance,
                evidence_references=tuple([auth_edge.canonical_digest] if auth_edge else []),
            )
            self.monitor.set_cached_decision(cache_key, resp, ttl_seconds=30)
            return resp

        # 5. Legitimate Allow
        ev_refs = tuple([auth_edge.canonical_digest] if auth_edge else [])
        resp = TrustDecisionResponse(
            decision=DecisionOutcome.ALLOW,
            reason_code="AUTHORIZED",
            explanation="Identity verified, active affiliation confirmed, and delegated authority requirements satisfied.",
            assurance=assurance,
            evidence_references=ev_refs,
        )
        self.monitor.set_cached_decision(cache_key, resp, ttl_seconds=60)
        return resp
