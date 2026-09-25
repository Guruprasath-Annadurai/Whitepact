# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.authority.models import (
    AuthorityGrant,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.errors import CrossTenantReference


def assert_same_tenant(expected: str, *labels_and_values: tuple[str, str]) -> None:
    for label, value in labels_and_values:
        if value != expected:
            raise CrossTenantReference(f"{label} tenant {value} != expected {expected}")


def validate_grant_tenant(grant: AuthorityGrant) -> None:
    assert_same_tenant(
        grant.tenant_id,
        ("subject", grant.subject.tenant_id),
    )


def validate_deny_tenant(deny: ExplicitDeny, tenant_id: str) -> None:
    assert_same_tenant(tenant_id, ("deny", deny.tenant_id))


def validate_ceiling_tenant(ceiling: OrgAuthorityCeilingModel, tenant_id: str) -> None:
    assert_same_tenant(tenant_id, ("ceiling", ceiling.tenant_id))


def validate_creation_event_tenant(event: object) -> None:
    from responsibleai.formula.authority.creation import AuthorityCreationEvent

    if not isinstance(event, AuthorityCreationEvent):
        raise TypeError("expected AuthorityCreationEvent")
    t = event.new_grant.tenant_id
    assert_same_tenant(t, ("event grant", t))
    if event.new_grant.issuer_id != event.issuer_id:
        raise CrossTenantReference("issuer mismatch on creation event")
    if event.new_grant.subject.subject_id != event.subject_id:
        raise CrossTenantReference("subject mismatch on creation event")
