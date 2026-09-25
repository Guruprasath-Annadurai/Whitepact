# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Grant algebra — deterministic composition semantics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from responsibleai.formula.authority.models import (
    AuthorityContext,
    AuthorityGrant,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.errors import AuthorityExpansion, InvalidDelegation


@dataclass(frozen=True, slots=True)
class AuthorityTuple:
    """Normalized effective permission atom."""

    action: str
    resource: str
    purpose: str
    risk_ceiling: int
    grant_id: str


def grant_union(grants: Iterable[AuthorityGrant]) -> frozenset[AuthorityTuple]:
    """Independent grants **union** allowances (RoleA READ + RoleB WRITE)."""
    out: set[AuthorityTuple] = set()
    for g in grants:
        for action in g.actions:
            for resource in g.resources:
                for purpose in g.purposes or frozenset({"*"}):
                    out.add(
                        AuthorityTuple(
                            action=action,
                            resource=resource,
                            purpose=purpose,
                            risk_ceiling=g.risk_ceiling,
                            grant_id=g.grant_id,
                        )
                    )
    return frozenset(out)


def grant_intersection(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    return a & b


def grant_difference(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    return a - b


def grant_restriction(
    tuples: frozenset[AuthorityTuple], ceiling: OrgAuthorityCeilingModel
) -> frozenset[AuthorityTuple]:
    """Intersect effective tuples with org ceiling."""
    out: set[AuthorityTuple] = set()
    for t in tuples:
        if ceiling.allowed_actions is not None and t.action not in ceiling.allowed_actions:
            continue
        if ceiling.allowed_resources is not None and t.resource not in ceiling.allowed_resources:
            continue
        if ceiling.max_risk_class is not None and t.risk_ceiling > ceiling.max_risk_class:
            continue
        out.add(t)
    return frozenset(out)


def apply_explicit_denies(
    tuples: frozenset[AuthorityTuple],
    denies: Iterable[ExplicitDeny],
    subject_id: str,
    at: datetime,
) -> frozenset[AuthorityTuple]:
    """Explicit deny wins over allow on matching action/resource."""
    result = set(tuples)
    for deny in denies:
        if deny.subject_id != subject_id:
            continue
        if deny.expires_at is not None and at >= deny.expires_at:
            continue
        for t in list(result):
            action_match = t.action in deny.actions or "*" in deny.actions
            resource_match = t.resource in deny.resources or "*" in deny.resources
            if action_match and resource_match:
                result.remove(t)
    return frozenset(result)


def authority_subset(child: AuthorityGrant, parent: AuthorityGrant) -> bool:
    """Child grant must be narrower on every mandatory dimension."""
    if not child.actions.issubset(parent.actions):
        return False
    if not child.resources.issubset(parent.resources):
        return False
    if child.purposes and parent.purposes and not child.purposes.issubset(parent.purposes):
        return False
    if child.risk_ceiling > parent.risk_ceiling:
        return False
    if child.constraints.allow_delegation and not parent.constraints.allow_delegation:
        return False
    if child.not_before < parent.not_before:
        return False
    if child.expires_at > parent.expires_at:
        return False
    for key, value in child.context.attributes.items():
        if parent.context.attributes.get(key) != value:
            return False
    return True


def validate_delegation(parent: AuthorityGrant, child: AuthorityGrant) -> None:
    if not parent.constraints.allow_delegation:
        raise InvalidDelegation("parent grant disallows delegation")
    if not authority_subset(child, parent):
        raise AuthorityExpansion("delegation widens authority beyond parent")


@dataclass
class EffectiveAuthorityEvaluator:
    """Compose grants + ceiling + denies at evaluation time."""

    ceiling: OrgAuthorityCeilingModel | None = None

    def effective(
        self,
        grants: Iterable[AuthorityGrant],
        denies: Iterable[ExplicitDeny],
        subject_id: str,
        at: datetime,
        context: AuthorityContext | None = None,
    ) -> frozenset[AuthorityTuple]:
        active = [g for g in grants if g.subject.subject_id == subject_id and g.valid_at(at)]
        if context is not None:
            active = [
                g
                for g in active
                if all(
                    context.attributes.get(k) == v
                    for k, v in g.context.attributes.items()
                    if k in context.attributes
                )
                or not g.context.attributes
            ]
        tuples = grant_union(active)
        if self.ceiling is not None:
            tuples = grant_restriction(tuples, self.ceiling)
        return apply_explicit_denies(tuples, denies, subject_id, at)


def conflict_resolution_denies_first(
    allows: frozenset[AuthorityTuple], denies: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    """Documented policy: deny tuples remove matching allows."""
    return grant_difference(allows, denies)
