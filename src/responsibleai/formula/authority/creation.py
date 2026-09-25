# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from responsibleai.formula.authority.algebra import EffectiveAuthorityEvaluator
from responsibleai.formula.authority.models import AuthorityGrant, AuthorityLifecycle
from responsibleai.formula.errors import AuthorityExpansion, InvalidGrant


@dataclass(frozen=True, slots=True)
class AuthorityCreationEvent:
    issuer_id: str
    subject_id: str
    new_grant: AuthorityGrant
    reason: str
    at: datetime
    evidence_ref: str
    policy_version: str


def issuer_can_grant(
    issuer_id: str,
    grant: AuthorityGrant,
    issuer_grants: tuple[AuthorityGrant, ...],
    evaluator: EffectiveAuthorityEvaluator,
    at: datetime,
) -> bool:
    """Issuer must already hold superset authority (or be tenant root)."""
    if grant.issuer_id != issuer_id:
        return False
    if grant.subject.subject_id == issuer_id:
        return False
    if issuer_id.startswith("tenant_root:"):
        return True
    effective = evaluator.effective(issuer_grants, (), issuer_id, at)
    for action in grant.actions:
        for resource in grant.resources:
            if not any(t.action == action and t.resource == resource for t in effective):
                return False
    return True


def apply_creation_event(
    state: tuple[AuthorityGrant, ...],
    event: AuthorityCreationEvent,
    evaluator: EffectiveAuthorityEvaluator,
) -> tuple[AuthorityGrant, ...]:
    if not issuer_can_grant(event.issuer_id, event.new_grant, state, evaluator, event.at):
        raise AuthorityExpansion("issuer cannot mint this grant")
    grant = event.new_grant
    if grant.lifecycle == AuthorityLifecycle.PENDING:
        grant = _with_lifecycle(grant, AuthorityLifecycle.ACTIVE)
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
    )


def apply_delegation(
    parent: AuthorityGrant,
    child: AuthorityGrant,
) -> AuthorityGrant:
    from responsibleai.formula.authority.algebra import validate_delegation

    validate_delegation(parent, child)
    if child.delegator_id != parent.subject.subject_id:
        raise InvalidGrant("delegator_id must match parent subject")
    return child
