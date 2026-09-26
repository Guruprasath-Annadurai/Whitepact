# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Iterable

from responsibleai.formula.authority.atoms import AuthorityTuple, PermissionAtom
from responsibleai.formula.authority.models import ExplicitDeny
from responsibleai.formula.authority.wildcard import (
    FORMULA_V01_ACTIONS,
    FORMULA_V01_PURPOSES,
    FORMULA_V01_RESOURCES,
    WILDCARD,
)


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
    """Concrete atoms only; call after ``materialize_wildcard_tuples``."""
    action_ok = atom.action in deny.actions or WILDCARD in deny.actions
    resource_ok = atom.resource in deny.resources or WILDCARD in deny.resources
    return action_ok and resource_ok


def _action_universe(
    tuples: Iterable[AuthorityTuple], denies: Iterable[ExplicitDeny]
) -> frozenset[str]:
    universe = set(FORMULA_V01_ACTIONS)
    for t in tuples:
        if t.action != WILDCARD:
            universe.add(t.action)
    for d in denies:
        universe.update(a for a in d.actions if a != WILDCARD)
    return frozenset(universe)


def _resource_universe(
    tuples: Iterable[AuthorityTuple], denies: Iterable[ExplicitDeny]
) -> frozenset[str]:
    universe = set(FORMULA_V01_RESOURCES)
    for t in tuples:
        if t.resource != WILDCARD:
            universe.add(t.resource)
    for d in denies:
        universe.update(r for r in d.resources if r != WILDCARD)
    return frozenset(universe)


def _purpose_universe(
    tuples: Iterable[AuthorityTuple], denies: Iterable[ExplicitDeny]
) -> frozenset[str]:
    universe = set(FORMULA_V01_PURPOSES)
    for t in tuples:
        if t.purpose != WILDCARD:
            universe.add(t.purpose)
    return frozenset(universe)


def materialize_wildcard_tuples(
    tuples: frozenset[AuthorityTuple],
    denies: Iterable[ExplicitDeny],
) -> frozenset[AuthorityTuple]:
    """Expand wildcard allows into concrete atoms before deny subtraction."""
    if not tuples:
        return frozenset()
    deny_list = tuple(denies)
    actions = _action_universe(tuples, deny_list)
    resources = _resource_universe(tuples, deny_list)
    purposes = _purpose_universe(tuples, deny_list)
    out: set[AuthorityTuple] = set()
    for t in tuples:
        act_iter = actions if t.action == WILDCARD else frozenset({t.action})
        res_iter = resources if t.resource == WILDCARD else frozenset({t.resource})
        pur_iter = purposes if t.purpose == WILDCARD else frozenset({t.purpose})
        for action in act_iter:
            for resource in res_iter:
                for purpose in pur_iter:
                    out.add(
                        AuthorityTuple(
                            action,
                            resource,
                            purpose,
                            t.risk_ceiling,
                            t.grant_id,
                        )
                    )
    return frozenset(out)


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
