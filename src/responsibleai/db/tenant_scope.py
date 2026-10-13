# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tenant predicates. A missing organization is the NULL tenant, never every tenant."""

from __future__ import annotations

from typing import Any


def org_scope(column: Any, org_id: str | None) -> Any:
    """SQL predicate for one tenant.

    ``org_id is None`` matches ``column IS NULL``. It does not omit the predicate.
    """
    if org_id is None:
        return column.is_(None)
    return column == org_id
