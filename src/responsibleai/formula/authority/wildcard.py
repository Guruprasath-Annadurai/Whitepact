# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

WILDCARD = "*"

# Finite v0.1 universe for materializing wildcard grants/denies into concrete atoms.
FORMULA_V01_ACTIONS: frozenset[str] = frozenset(
    {"read", "write", "execute", "delete", "invoke", "admin"}
)
FORMULA_V01_RESOURCES: frozenset[str] = frozenset(
    {"x", "y", "account-1", "account-2", "z"}
)
FORMULA_V01_PURPOSES: frozenset[str] = frozenset({"ops", "audit", "billing"})


def dimension_subset(child: frozenset[str], parent: frozenset[str]) -> bool:
    """specific ⊆ wildcard (parent); wildcard ⊆ specific (child) is false."""
    if WILDCARD in child:
        return WILDCARD in parent
    if WILDCARD in parent:
        return True
    return child.issubset(parent)


def expand_dimension(values: frozenset[str]) -> frozenset[str]:
    if not values:
        raise ValueError("empty dimension set is invalid; use frozenset({WILDCARD}) for wildcard")
    return values
