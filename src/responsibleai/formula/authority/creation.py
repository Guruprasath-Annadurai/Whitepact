# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    grant_contained_in_issuer_authority,
)
from responsibleai.formula.authority.containment import grant_within_org_ceiling
from responsibleai.formula.authority.models import (
    AuthorityGrant,
    AuthorityLifecycle,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.root import TenantRootPrincipal
from responsibleai.formula.authority.tenant import validate_creation_event_tenant
from responsibleai.formula.epistemic import is_authoritative_for_hard_proof
from responsibleai.formula.errors import AuthorityExpansion, InvalidGrant


@dataclass(frozen=True, slots=True)
class AuthorityCreationEvent:
    tenant_id: str
    issuer_id: str
    subject_id: str
    new_grant: AuthorityGrant
    reason: str
    at: datetime
    evidence_ref: str
    policy_version: str


def validate_creation_event(event: AuthorityCreationEvent) -> None:
    validate_creation_event_tenant(event)
    if not event.evidence_ref:
        raise InvalidGrant("creation event requires evidence_ref")
    if not event.policy_version:
        raise InvalidGrant("creation event requires policy_version")
    g = event.new_grant
    if g.issuer_id != event.issuer_id:
        raise InvalidGrant("grant issuer must match event issuer")
    if g.subject.subject_id != event.subject_id:
        raise InvalidGrant("grant subject must match event subject")
    if event.at < g.not_before:
        raise InvalidGrant("creation before grant not_before")
    if event.at >= g.expires_at:
        raise InvalidGrant("creation at or after grant expiry")


def issuer_can_grant(
    issuer_id: str,
    grant: AuthorityGrant,
    issuer_grants: tuple[AuthorityGrant, ...],
    evaluator: EffectiveAuthorityEvaluator,
    at: datetime,
    root: TenantRootPrincipal | None = None,
) -> bool:
    if grant.issuer_id != issuer_id:
        return False
    if grant.subject.subject_id == issuer_id:
        return False
    if root is not None and root.is_issuer(issuer_id, grant.tenant_id):
        if not grant.evidence_ref or not root.evidence_ref:
            return False
        if not is_authoritative_for_hard_proof(grant.epistemic_status):
            return False
        ceilings = [c for c in (root.ceiling, evaluator.ceiling) if c is not None]
        for ceiling in ceilings:
            if not grant_within_org_ceiling(grant, ceiling):
                return False
        return True
    return grant_contained_in_issuer_authority(grant, issuer_grants, at, issuer_id)


def apply_creation_event(
    state: tuple[AuthorityGrant, ...],
    event: AuthorityCreationEvent,
    evaluator: EffectiveAuthorityEvaluator,
    root: TenantRootPrincipal | None = None,
) -> tuple[AuthorityGrant, ...]:
    validate_creation_event(event)
    if not issuer_can_grant(event.issuer_id, event.new_grant, state, evaluator, event.at, root):
        raise AuthorityExpansion("issuer cannot mint this grant")
    grant = event.new_grant
    if grant.lifecycle == AuthorityLifecycle.PENDING:
        if event.at < grant.not_before:
            raise InvalidGrant("cannot activate grant before not_before")
        grant = _with_lifecycle(grant, AuthorityLifecycle.ACTIVE)
    elif grant.lifecycle != AuthorityLifecycle.ACTIVE:
        raise InvalidGrant(f"grant lifecycle {grant.lifecycle} not active at creation")
    return state + (grant,)


def _with_lifecycle(grant: AuthorityGrant, lifecycle: AuthorityLifecycle) -> AuthorityGrant:
    return AuthorityGrant(
        grant_id=grant.grant_id,
        tenant_id=grant.tenant_id,
        subject=grant.subject,
        issuer_id=grant.issuer_id,
        delegator_id=grant.delegator_id,
        actions=grant.actions,
        resources=grant.resources,
        purposes=grant.purposes,
        context=grant.context,
        not_before=grant.not_before,
        expires_at=grant.expires_at,
        risk_ceiling=grant.risk_ceiling,
        constraints=grant.constraints,
        lifecycle=lifecycle,
        evidence_ref=grant.evidence_ref,
        epistemic_status=grant.epistemic_status,
        schema_version=grant.schema_version,
        version=grant.version,
        delegation_depth=grant.delegation_depth,
    )


def apply_delegation(
    parent: AuthorityGrant,
    child: AuthorityGrant,
    *,
    ceiling: OrgAuthorityCeilingModel | None = None,
) -> AuthorityGrant:
    from responsibleai.formula.authority.algebra import validate_delegation

    validate_delegation(parent, child, ceiling=ceiling)
    if child.delegator_id != parent.subject.subject_id:
        raise InvalidGrant("delegator_id must match parent subject")
    return child
