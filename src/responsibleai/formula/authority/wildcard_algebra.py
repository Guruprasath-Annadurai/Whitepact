# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.authority.atoms import AuthorityTuple, PermissionAtom
from responsibleai.formula.authority.models import ExplicitDeny
from responsibleai.formula.authority.wildcard import WILDCARD


def _dim_intersect(a: str, b: str) -> str | None:
    if a == b:
        return a
    if a == WILDCARD:
        return b
    if b == WILDCARD:
        return a
    return None


def intersect_atoms(a: PermissionAtom, b: PermissionAtom) -> PermissionAtom | None:
    action = _dim_intersect(a.action, b.action)
    resource = _dim_intersect(a.resource, b.resource)
    purpose = _dim_intersect(a.purpose, b.purpose)
    if action is None or resource is None or purpose is None:
        return None
    return PermissionAtom(action, resource, purpose, min(a.risk_ceiling, b.risk_ceiling))


def atoms_compatible(a: PermissionAtom, b: PermissionAtom) -> bool:
    return intersect_atoms(a, b) is not None


def atom_covered_by_deny(atom: PermissionAtom, deny: ExplicitDeny) -> bool:
    action_ok = atom.action in deny.actions or WILDCARD in deny.actions
    resource_ok = atom.resource in deny.resources or WILDCARD in deny.resources
    return action_ok and resource_ok


def tuple_intersection(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    out: set[AuthorityTuple] = set()
    for ta in a:
        for tb in b:
            merged = intersect_atoms(ta.atom(), tb.atom())
            if merged is None:
                continue
            grant_id = ta.grant_id if ta.grant_id == tb.grant_id else f"{ta.grant_id}+{tb.grant_id}"
            out.add(
                AuthorityTuple(
                    merged.action,
                    merged.resource,
                    merged.purpose,
                    merged.risk_ceiling,
                    grant_id,
                )
            )
    return frozenset(out)


def tuple_difference(
    a: frozenset[AuthorityTuple], b: frozenset[AuthorityTuple]
) -> frozenset[AuthorityTuple]:
    out: set[AuthorityTuple] = set()
    for ta in a:
        covered = any(atoms_compatible(ta.atom(), tb.atom()) for tb in b)
        if not covered:
            out.add(ta)
    return frozenset(out)
