# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Internal test fixtures for org-scoped keys. Not a hosted issuance path."""

from __future__ import annotations

from responsibleai.rbac.models import Role


async def seed_org_with_key(
    *,
    name: str,
    slug: str,
    key_name: str = "admin-key",
    role: Role = Role.ADMIN,
) -> tuple[str, str, str]:
    """Create an org + fixture key via OrgRepository after app lifespan started."""
    from responsibleai.dashboard.app import _org_repo

    if _org_repo is None:
        raise RuntimeError("dashboard lifespan has not initialized OrgRepository")
    org = await _org_repo.create_org(name, slug)
    rec, raw = await _org_repo.create_key(org.id, key_name, role, internal_unverified_fixture=True)
    return org.id, rec.id, raw
