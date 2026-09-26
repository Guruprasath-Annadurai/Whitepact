# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.authority.models import AuthorityContext


def grant_context_matches(
    grant_context: AuthorityContext, actual_context: AuthorityContext | None
) -> bool:
    """Every grant-required key must exist in actual context with equal value."""
    required = grant_context.attributes
    if not required:
        return True
    if actual_context is None:
        return False
    actual = actual_context.attributes
    for key, value in required.items():
        if key not in actual:
            return False
        if actual[key] != value:
            return False
    return True
