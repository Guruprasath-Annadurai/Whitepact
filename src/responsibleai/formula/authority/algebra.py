# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Grant algebra — deterministic composition semantics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from responsibleai.formula.authority.atoms import AuthorityTuple, PermissionAtom
from responsibleai.formula.authority.containment import (
    constraint_subset,
    effective_risk_ceiling,
)
from responsibleai.formula.authority.context_match import grant_context_matches
from responsibleai.formula.authority.models import (
    AuthorityContext,
    AuthorityGrant,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.wildcard import WILDCARD, dimension_subset, expand_dimension
from responsibleai.formula.authority.wildcard_algebra import (
    atom_covered_by_deny,
    materialize_wildcard_tuples,
    tuple_difference,
    tuple_intersection,
)
from responsibleai.formula.epistemic import is_authoritative_for_hard_proof
from responsibleai.formula.errors import AuthorityExpansion, CrossTenantReference, InvalidDelegation


@dataclass(frozen=True, slots=True)
class PermissionProvenance:
    atom: PermissionAtom
    grant_id: str


def _purposes_for_union(g: AuthorityGrant) -> frozenset[str]:
    purposes = expand_dimension(g.purposes)
    return purposes


def grant_union(grants: Iterable[AuthorityGrant]) -> frozenset[AuthorityTuple]:
    out: set[AuthorityTuple] = set()
    for g in grants:
        actions = expand_dimension(g.actions)
        resources = expand_dimension(g.resources)
        purposes = _purposes_for_union(g)
        for action in actions:
            for resource in resources:
                for purpose in purposes:
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


def atoms_from_tuples(tuples: frozenset[AuthorityTuple]) -> frozenset[PermissionAtom]:
    return frozenset(t.atom() for t in tuples)


def grant_intersection(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    return tuple_intersection(a, b)


def grant_difference(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    return tuple_difference(a, b)


def grant_restriction(
    tuples: frozenset[AuthorityTuple], ceiling: OrgAuthorityCeilingModel
) -> frozenset[AuthorityTuple]:
    """Org ceiling: DROP tuples exceeding allowed dimensions (not clip)."""
    out: set[AuthorityTuple] = set()
    for t in tuples:
        if ceiling.allowed_actions is not None:
            if t.action == WILDCARD:
                if WILDCARD not in ceiling.allowed_actions:
                    continue
            elif t.action not in ceiling.allowed_actions:
                continue
        if ceiling.allowed_resources is not None:
            if t.resource == WILDCARD:
                if WILDCARD not in ceiling.allowed_resources:
                    continue
            elif t.resource not in ceiling.allowed_resources:
                continue
        if ceiling.max_risk_class is not None and t.risk_ceiling > ceiling.max_risk_class:
            continue
        out.add(t)
    return frozenset(out)


def apply_explicit_denies(
    tuples: frozenset[AuthorityTuple],
    denies: Iterable[ExplicitDeny],
    subject_id: str,
    tenant_id: str,
    at: datetime,
) -> frozenset[AuthorityTuple]:
    applicable = [
        d
        for d in denies
        if d.tenant_id == tenant_id
        and d.subject_id == subject_id
        and (d.expires_at is None or at < d.expires_at)
    ]
    concrete = materialize_wildcard_tuples(tuples, applicable)
    result = set(concrete)
    for deny in applicable:
        for t in list(result):
            if atom_covered_by_deny(t.atom(), deny):
                result.remove(t)
    return frozenset(result)


def context_subset(child: AuthorityContext, parent: AuthorityContext) -> bool:
    """AllowedContexts(child) ⊆ AllowedContexts(parent): child retains every parent restriction."""
    parent_attrs = parent.attributes
    child_attrs = child.attributes
    for key, value in parent_attrs.items():
        if child_attrs.get(key) != value:
            return False
    return True


def authority_subset(child: AuthorityGrant, parent: AuthorityGrant) -> bool:
    if child.tenant_id != parent.tenant_id:
        return False
    if not dimension_subset(child.actions, parent.actions):
        return False
    if not dimension_subset(child.resources, parent.resources):
        return False
    if not dimension_subset(child.purposes, parent.purposes):
        return False
    if effective_risk_ceiling(child) > effective_risk_ceiling(parent):
        return False
    if child.constraints.allow_delegation and not parent.constraints.allow_delegation:
        return False
    if not constraint_subset(child.constraints, parent.constraints):
        return False
    if child.not_before < parent.not_before:
        return False
    if child.expires_at > parent.expires_at:
        return False
    if not context_subset(child.context, parent.context):
        return False
    return True


def validate_delegation(parent: AuthorityGrant, child: AuthorityGrant) -> None:
    if parent.tenant_id != child.tenant_id:
        raise CrossTenantReference("delegation across tenants")
    if not parent.constraints.allow_delegation:
        raise InvalidDelegation("parent grant disallows delegation")
    if child.delegation_depth != parent.delegation_depth + 1:
        raise InvalidDelegation("delegation depth must increment by one")
    if not authority_subset(child, parent):
        raise AuthorityExpansion("delegation widens authority beyond parent")


def grant_contained_in_issuer_authority(
    new_grant: AuthorityGrant,
    issuer_grants: Iterable[AuthorityGrant],
    at: datetime,
    issuer_id: str,
) -> bool:
    for ig in issuer_grants:
        if ig.subject.subject_id != issuer_id:
            continue
        if ig.tenant_id != new_grant.tenant_id:
            continue
        if not ig.valid_at(at):
            continue
        if authority_subset(new_grant, ig):
            return True
    return False


@dataclass
class EffectiveAuthorityEvaluator:
    """Compose grants + ceiling + denies at evaluation time."""

    ceiling: OrgAuthorityCeilingModel | None = None

    def effective(
        self,
        grants: Iterable[AuthorityGrant],
        denies: Iterable[ExplicitDeny],
        subject_id: str,
        tenant_id: str,
        at: datetime,
        context: AuthorityContext | None = None,
        hard_proof: bool = False,
    ) -> frozenset[AuthorityTuple]:
        actual_ctx = context or AuthorityContext.from_mapping()
        active = [
            g
            for g in grants
            if g.subject.subject_id == subject_id
            and g.tenant_id == tenant_id
            and g.subject.tenant_id == tenant_id
            and g.valid_at(at)
            and grant_context_matches(g.context, actual_ctx)
            and (not hard_proof or is_authoritative_for_hard_proof(g.epistemic_status))
        ]
        tuples = grant_union(active)
        if self.ceiling is not None:
            if self.ceiling.tenant_id != tenant_id:
                raise CrossTenantReference("ceiling tenant mismatch")
            tuples = grant_restriction(tuples, self.ceiling)
        return apply_explicit_denies(tuples, denies, subject_id, tenant_id, at)


def conflict_resolution_denies_first(
    allows: frozenset[AuthorityTuple], denies: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    return grant_difference(allows, denies)
