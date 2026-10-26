# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial proof for protected component tenant prerequisites.

These are fixture-qualification checks, not customer acceptance or bootstrap.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update

from responsibleai.data_governance.tenant_client import TenantCreationDeniedError
from responsibleai.db.engine import web_users
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import WRONG_TENANT, EnterpriseError
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Plan, Role
from tests.protected_component_tenant import (
    authorized_workspace,
    component_controller,
    provision_component_organization,
)


@pytest.mark.asyncio
async def test_protected_prerequisites_keep_creation_denials_and_tenant_boundary(
    tmp_path, monkeypatch
) -> None:
    async with component_controller(tmp_path, monkeypatch, "wp_component_proof") as controller:
        engine = controller.engine
        with pytest.raises(TenantCreationDeniedError, match="paid entitlement"):
            await OrgRepository(engine).create_org("Paid", "paid-direct", plan=Plan.ENTERPRISE)
        with pytest.raises(TenantCreationDeniedError, match="CSRF"):
            await OrgRepository(engine).create_org("Bare", f"bare-{uuid.uuid4().hex[:8]}")

        identities = WebIdentityRepository(engine)
        alice, alice_proof = await identities.register(
            "Alice", f"alice-{uuid.uuid4().hex[:8]}@example.test", "Independent-Test-Only-42!"
        )
        bob, bob_proof = await identities.register(
            "Bob", f"bob-{uuid.uuid4().hex[:8]}@example.test", "Independent-Test-Only-42!"
        )
        assert await identities.verify_email(alice_proof)
        assert await identities.verify_email(bob_proof)
        iam = EnterpriseIAM(engine)
        with pytest.raises(TenantCreationDeniedError, match="creator mismatch"):
            await iam.create_workspace(
                actor_user_id=alice,
                name="No Session",
                slug=f"nosess-{uuid.uuid4().hex[:8]}",
                kind="ORGANIZATION",
            )
        bob_token, bob_csrf = await identities.create_session(bob)
        with pytest.raises(TenantCreationDeniedError, match="creator mismatch"):
            await iam.create_workspace(
                actor_user_id=alice,
                name="Cross Creator",
                slug=f"cross-{uuid.uuid4().hex[:8]}",
                kind="ORGANIZATION",
                session_token=bob_token,
                csrf=bob_csrf,
            )

        alice_org = await authorized_workspace(
            engine, alice, name="Alice Co", slug=f"alice-{uuid.uuid4().hex[:8]}"
        )
        bob_org = await provision_component_organization(
            engine, name="Bob Paid", slug=f"bob-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE
        )
        assert bob_org.plan is Plan.ENTERPRISE
        reloaded = await OrgRepository(engine).get_org(alice_org["id"])
        assert reloaded is not None and reloaded.plan is Plan.FREE
        actor = Actor(
            actor_type="human",
            actor_id=alice,
            user_id=alice,
            org_id=alice_org["id"],
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        with pytest.raises(EnterpriseError) as cross:
            await iam.authorize(actor, Permission.ORG_UPDATE_SETTINGS, org_id=bob_org.id)
        assert cross.value.code == WRONG_TENANT

        async with engine.raw.begin() as connection:
            await connection.execute(
                update(web_users).where(web_users.c.id == alice).values(disabled=1)
            )
        with pytest.raises(EnterpriseError) as disabled:
            await iam.create_workspace(
                actor_user_id=alice,
                name="Disabled",
                slug=f"disabled-{uuid.uuid4().hex[:8]}",
                kind="ORGANIZATION",
                session_token=bob_token,
                csrf=bob_csrf,
            )
        assert disabled.value.code == "FORBIDDEN"
