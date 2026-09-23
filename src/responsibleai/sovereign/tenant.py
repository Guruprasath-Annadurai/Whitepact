# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tenant isolation guards for Sovereign resources."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from responsibleai.sovereign.errors import SovereignTenantIsolationError

T = TypeVar("T")


def assert_same_organization(
    request_org_id: str,
    resource_org_id: str | None,
    *,
    resource_kind: str = "resource",
) -> None:
    if resource_org_id is None:
        raise SovereignTenantIsolationError(f"{resource_kind} not found")
    if request_org_id != resource_org_id:
        raise SovereignTenantIsolationError(f"{resource_kind} not found")


def filter_org_scoped(
    request_org_id: str,
    items: list[T],
    *,
    org_accessor: Callable[[T], str],
) -> list[T]:
    return [item for item in items if org_accessor(item) == request_org_id]
