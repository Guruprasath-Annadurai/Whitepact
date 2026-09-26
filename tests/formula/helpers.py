# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityContext,
    AuthorityGrant,
    AuthorityLifecycle,
    AuthoritySubject,
)


def make_grant(
    gid: str,
    subject: str,
    tenant: str = "t1",
    actions: frozenset[str] | None = None,
    resources: frozenset[str] | None = None,
    purposes: frozenset[str] | None = None,
    *,
    allow_delegation: bool = False,
    one_shot: bool = False,
    risk: int = 5,
    delegator: str | None = None,
    nb: datetime | None = None,
    exp: datetime | None = None,
    context: AuthorityContext | None = None,
    lifecycle: AuthorityLifecycle = AuthorityLifecycle.ACTIVE,
    issuer_id: str = "issuer-root",
    delegation_depth: int | None = None,
    max_risk_class: int = 10,
    conditions: Mapping[str, Any] | None = None,
) -> AuthorityGrant:
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    return AuthorityGrant(
        grant_id=gid,
        tenant_id=tenant,
        subject=AuthoritySubject(subject_id=subject, tenant_id=tenant),
        issuer_id=issuer_id,
        delegator_id=delegator,
        actions=actions or frozenset({"read"}),
        resources=resources or frozenset({"x"}),
        purposes=purposes or frozenset({"ops"}),
        context=context or AuthorityContext.from_mapping(),
        not_before=nb or now,
        expires_at=exp or (now + timedelta(days=1)),
        risk_ceiling=risk,
        constraints=AuthorityConstraint.build(
            allow_delegation=allow_delegation,
            one_shot=one_shot,
            max_risk_class=max_risk_class,
            conditions=conditions,
        ),
        lifecycle=lifecycle,
        evidence_ref="ev-1",
        delegation_depth=delegation_depth
        if delegation_depth is not None
        else (1 if delegator else 0),
    )
