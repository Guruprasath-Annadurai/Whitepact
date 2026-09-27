# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations


def merge_capability_routes(
    outer_route: tuple[str, ...], inner_route: tuple[str, ...]
) -> tuple[str, ...]:
    """Merge prerequisite routes at the composition junction."""
    if not outer_route:
        return inner_route
    if not inner_route:
        return outer_route
    if outer_route[-1] == inner_route[0]:
        return outer_route + inner_route[1:]
    return outer_route + inner_route


def route_derivation_depth(route: tuple[str, ...]) -> int:
    if len(route) < 2:
        return 0
    return len(route) - 1
