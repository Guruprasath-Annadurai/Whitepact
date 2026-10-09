# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 SCIM replay, stale authority, and cross-tenant isolation."""

from __future__ import annotations

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    organizations,
    trust_fabric_principals,
)
from responsibleai.iam.scim import ScimService
from responsibleai.iam.session import SessionService


@pytest.fixture
async def scim_db() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_a",
                name="Org A",
                slug="org-a",
                monthly_budget_usd=1000.0,
                created_at="2026-10-01T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id="org_b",
                name="Org B",
                slug="org-b",
                monthly_budget_usd=1000.0,
                created_at="2026-10-01T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
    yield engine
    await engine.close()


@pytest.mark.asyncio
async def test_scim_deprovision_is_idempotent(scim_db: DatabaseEngine) -> None:
    scim = ScimService(scim_db)
    user = await scim.create_user(
        org_id="org_a",
        user_data={"userName": "repeat@corp.com", "role": "VIEWER"},
    )
    uid = user["id"]
    assert await scim.deprovision_user(org_id="org_a", scim_user_id=uid) is True
    # Repeat deprovision must not resurrect authority (idempotent suspend).
    assert await scim.deprovision_user(org_id="org_a", scim_user_id=uid) is True
    async with scim_db.raw.connect() as conn:
        state = (
            await conn.execute(
                select(trust_fabric_principals.c.lifecycle_state).where(
                    trust_fabric_principals.c.display_name == "repeat@corp.com"
                )
            )
        ).scalar_one()
    assert state == "SUSPENDED"


@pytest.mark.asyncio
async def test_scim_wrong_tenant_deprovision_denied(scim_db: DatabaseEngine) -> None:
    scim = ScimService(scim_db)
    user = await scim.create_user(
        org_id="org_a",
        user_data={"userName": "tenant@corp.com", "role": "VIEWER"},
    )
    assert await scim.deprovision_user(org_id="org_b", scim_user_id=user["id"]) is False


@pytest.mark.asyncio
async def test_scim_deprovision_revokes_active_session(scim_db: DatabaseEngine) -> None:
    scim = ScimService(scim_db)
    sessions = SessionService(scim_db)
    user = await scim.create_user(
        org_id="org_a",
        user_data={"userName": "session@corp.com", "role": "ADMIN"},
    )
    async with scim_db.raw.connect() as conn:
        principal_id = (
            await conn.execute(
                select(trust_fabric_principals.c.id).where(
                    trust_fabric_principals.c.display_name == "session@corp.com"
                )
            )
        ).scalar_one()
    sess_id, token = await sessions.create_session(org_id="org_a", principal_id=principal_id)
    assert await sessions.validate_session(org_id="org_a", session_id=sess_id, token=token)
    await scim.deprovision_user(org_id="org_a", scim_user_id=user["id"])
    assert await sessions.validate_session(org_id="org_a", session_id=sess_id, token=token) is False
