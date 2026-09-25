# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

WILDCARD = "*"


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
