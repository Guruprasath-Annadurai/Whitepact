# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityGrant,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.wildcard import WILDCARD, expand_dimension


def effective_risk_ceiling(grant: AuthorityGrant) -> int:
    return min(grant.risk_ceiling, grant.constraints.max_risk_class)


def constraint_subset(child: AuthorityConstraint, parent: AuthorityConstraint) -> bool:
    if child.max_risk_class > parent.max_risk_class:
        return False
    if parent.one_shot and not child.one_shot:
        return False
    for key, value in parent.conditions.items():
        if child.conditions.get(key) != value:
            return False
    return True


def dimension_within_ceiling(values: frozenset[str], allowed: frozenset[str] | None) -> bool:
    if allowed is None:
        return True
    expanded = expand_dimension(values)
    if WILDCARD in expanded:
        return WILDCARD in allowed
    return expanded.issubset(allowed)


def grant_within_org_ceiling(grant: AuthorityGrant, ceiling: OrgAuthorityCeilingModel) -> bool:
    if grant.tenant_id != ceiling.tenant_id:
        return False
    if (
        ceiling.max_risk_class is not None
        and effective_risk_ceiling(grant) > ceiling.max_risk_class
    ):
        return False
    if not dimension_within_ceiling(grant.actions, ceiling.allowed_actions):
        return False
    if not dimension_within_ceiling(grant.resources, ceiling.allowed_resources):
        return False
    if ceiling.max_delegation_depth is not None:
        if (
            grant.constraints.allow_delegation
            and grant.delegation_depth >= ceiling.max_delegation_depth
        ):
            return False
    return True
