# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and Lifecycle Tests for SCIM 2.0, Sessions, and API Key Lineage."""

from __future__ import annotations

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    iam_api_key_lineage,
    organizations,
    trust_fabric_principals,
)
from responsibleai.iam.api_key import ApiKeyService
from responsibleai.iam.scim import ScimService
from responsibleai.iam.session import SessionService
from responsibleai.rbac.models import Role


@pytest.fixture
async def test_db():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_lifecycle",
                name="Lifecycle Corp",
                slug="lifecycle-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
    yield engine
    await engine.close()


@pytest.mark.asyncio
async def test_session_lifecycle_and_revocation(test_db: DatabaseEngine):
    session_svc = SessionService(test_db)

    # 1. Create session
    sess_id, token = await session_svc.create_session(
        org_id="org_lifecycle",
        principal_id="user_alice",
        ttl_seconds=3600,
    )
    assert sess_id.startswith("sess_")
    assert token.startswith("wp_sess_")

    # 2. Validate session
    valid = await session_svc.validate_session(
        org_id="org_lifecycle",
        session_id=sess_id,
        token=token,
    )
    assert valid is True

    # 3. Revoke session
    revoked = await session_svc.revoke_session(
        org_id="org_lifecycle",
        session_id=sess_id,
    )
    assert revoked is True

    # 4. Re-validation must fail
    still_valid = await session_svc.validate_session(
        org_id="org_lifecycle",
        session_id=sess_id,
        token=token,
    )
    assert still_valid is False


@pytest.mark.asyncio
async def test_api_key_rotation_lineage(test_db: DatabaseEngine):
    key_svc = ApiKeyService(test_db)

    # 1. Create key
    key_id, raw_key, fprint = await key_svc.create_key(
        org_id="org_lifecycle",
        name="primary-worker",
        role=Role.ADMIN,
        environment="live",
    )
    assert raw_key.startswith("wp_live_")

    # 2. Rotate key
    new_key_id, new_raw, new_fprint = await key_svc.rotate_key(
        org_id="org_lifecycle",
        old_key_id=key_id,
    )
    assert new_key_id != key_id

    # Verify old key marked ROTATED and new key links back to parent
    async with test_db.raw.connect() as conn:
        old_row = (
            await conn.execute(
                select(iam_api_key_lineage).where(iam_api_key_lineage.c.id == key_id)
            )
        ).one()
        assert old_row.status == "ROTATED"

        new_row = (
            await conn.execute(
                select(iam_api_key_lineage).where(iam_api_key_lineage.c.id == new_key_id)
            )
        ).one()
        assert new_row.parent_key_id == key_id
        assert new_row.status == "ACTIVE"


@pytest.mark.asyncio
async def test_scim_provisioning_and_cascading_deprovisioning(test_db: DatabaseEngine):
    scim_svc = ScimService(test_db)
    session_svc = SessionService(test_db)

    # 1. Block SCIM root escalation
    with pytest.raises(ValueError, match="SCIM cannot provision root or owner authority"):
        await scim_svc.create_user(
            org_id="org_lifecycle",
            user_data={"userName": "mallory@corp.com", "role": "OWNER"},
        )

    # 2. Provision valid user
    user = await scim_svc.create_user(
        org_id="org_lifecycle",
        user_data={"userName": "bob@corp.com", "role": "ADMIN"},
    )
    scim_user_id = user["id"]

    # Lookup principal ID
    async with test_db.raw.connect() as conn:
        p_row = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.display_name == "bob@corp.com"
                )
            )
        ).one()
        principal_id = p_row.id
        assert p_row.lifecycle_state == "ACTIVE"

    # Create active session for Bob
    sess_id, token = await session_svc.create_session(
        org_id="org_lifecycle",
        principal_id=principal_id,
    )
    assert (
        await session_svc.validate_session(org_id="org_lifecycle", session_id=sess_id, token=token)
        is True
    )

    # 3. Deprovision Bob via SCIM
    deprovisioned = await scim_svc.deprovision_user(
        org_id="org_lifecycle",
        scim_user_id=scim_user_id,
    )
    assert deprovisioned is True

    # 4. Verify principal suspended and session immediately revoked!
    async with test_db.raw.connect() as conn:
        p_updated = (
            await conn.execute(
                select(trust_fabric_principals).where(trust_fabric_principals.c.id == principal_id)
            )
        ).one()
        assert p_updated.lifecycle_state == "SUSPENDED"

    session_valid = await session_svc.validate_session(
        org_id="org_lifecycle",
        session_id=sess_id,
        token=token,
    )
    assert session_valid is False
