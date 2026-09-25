# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import datetime

from responsibleai.formula.authority.models import AuthorityGrant, AuthorityLifecycle
from responsibleai.formula.errors import ConsumedGrant, ExpiredGrant, RevokedGrant


def lifecycle_at(grant: AuthorityGrant, at: datetime) -> AuthorityLifecycle:
    if grant.lifecycle == AuthorityLifecycle.REVOKED:
        return AuthorityLifecycle.REVOKED
    if grant.lifecycle == AuthorityLifecycle.CONSUMED:
        return AuthorityLifecycle.CONSUMED
    if grant.lifecycle == AuthorityLifecycle.SUPERSEDED:
        return AuthorityLifecycle.SUPERSEDED
    if at >= grant.expires_at:
        return AuthorityLifecycle.EXPIRED
    if at < grant.not_before:
        return AuthorityLifecycle.PENDING
    if grant.lifecycle == AuthorityLifecycle.PENDING:
        return AuthorityLifecycle.PENDING
    if grant.lifecycle == AuthorityLifecycle.ACTIVE:
        return AuthorityLifecycle.ACTIVE
    return grant.lifecycle


def assert_grant_usable(grant: AuthorityGrant, at: datetime) -> None:
    state = lifecycle_at(grant, at)
    if state != AuthorityLifecycle.ACTIVE:
        if state == AuthorityLifecycle.EXPIRED:
            raise ExpiredGrant(grant.grant_id)
        if state == AuthorityLifecycle.REVOKED:
            raise RevokedGrant(grant.grant_id)
        if state == AuthorityLifecycle.CONSUMED:
            raise ConsumedGrant(grant.grant_id)
        raise ConsumedGrant(f"grant {grant.grant_id} not active: {state}")


def consume_grant(grant: AuthorityGrant) -> AuthorityGrant:
    if not grant.constraints.one_shot:
        raise ConsumedGrant("grant is not consumable")
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
        lifecycle=AuthorityLifecycle.CONSUMED,
        evidence_ref=grant.evidence_ref,
        epistemic_status=grant.epistemic_status,
        schema_version=grant.schema_version,
        version=grant.version + 1,
    )
