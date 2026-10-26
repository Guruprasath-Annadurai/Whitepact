# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tenant binding for governed agent admission. Not customer acceptance."""

import uuid

import pytest
from sqlalchemy import text

from responsibleai.governance.agent_admission import admit_registered_agent
from responsibleai.rbac.models import OrgContext, Role
from tests.test_stage3_controller_postgres import isolated_controller_context


def context(org_id, *, legacy=False):
    return OrgContext(
        key_id="key-under-test",
        role=Role.ADMIN,
        org_id=org_id,
        is_legacy=legacy,
    )


@pytest.mark.asyncio
async def test_agent_admission_refuses_malformed_and_legacy_credentials():
    auth = context("org-1")
    assert await admit_registered_agent(None, auth, None) is auth
    with pytest.raises(ValueError, match="AGENT_ID_MALFORMED"):
        await admit_registered_agent(None, auth, "agent_NOTHEX")
    with pytest.raises(ValueError, match="ORG_SCOPED_CREDENTIAL_REQUIRED"):
        await admit_registered_agent(None, context("org-1", legacy=True), "agent_" + "ab" * 6)


@pytest.mark.asyncio
async def test_agent_admission_is_limited_to_one_active_tenant_agent(tmp_path, monkeypatch):
    async with isolated_controller_context(tmp_path, monkeypatch, "wp_agent_admission") as (
        service,
        _,
        _,
        token,
        csrf,
    ):
        tenant = await service.create(
            session_token=token,
            csrf=csrf,
            request_id="agent-admission-home",
            name="Home",
            slug="agent-admission-home",
            attach_session=True,
        )
        other = await service.create(
            session_token=token,
            csrf=csrf,
            request_id="agent-admission-other",
            name="Other",
            slug="agent-admission-other",
            attach_session=False,
        )
        home_agent = "agent_" + uuid.uuid4().hex[:12]
        foreign_agent = "agent_" + uuid.uuid4().hex[:12]
        disabled_agent = "agent_" + uuid.uuid4().hex[:12]
        async with service.engine.raw.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO trust_fabric_principals"
                    "(id,org_id,principal_type,display_name,lifecycle_state,created_at,updated_at)"
                    " VALUES (:id,:org,'AI_AGENT',:name,:state,'2026-10-26T00:00:00Z',"
                    "'2026-10-26T00:00:00Z')"
                ),
                [
                    {"id": home_agent, "org": tenant, "name": "Home agent", "state": "ACTIVE"},
                    {
                        "id": foreign_agent,
                        "org": other,
                        "name": "Foreign agent",
                        "state": "ACTIVE",
                    },
                    {
                        "id": disabled_agent,
                        "org": tenant,
                        "name": "Disabled agent",
                        "state": "DISABLED",
                    },
                ],
            )
            admitted = await admit_registered_agent(connection, context(tenant), home_agent)
            assert admitted.key_id == home_agent
            assert admitted.org_id == tenant
            assert admitted.key_name == "Home agent"
            assert admitted.authentication_method == "api_key"
            with pytest.raises(LookupError, match="AGENT_NOT_ACTIVE_IN_ORGANIZATION"):
                await admit_registered_agent(connection, context(tenant), foreign_agent)
            with pytest.raises(LookupError, match="AGENT_NOT_ACTIVE_IN_ORGANIZATION"):
                await admit_registered_agent(connection, context(tenant), disabled_agent)
