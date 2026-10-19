# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Ownership mutation rechecks on real PostgreSQL, without root fixtures."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select, update

from responsibleai.db.engine import create_engine, organizations, web_memberships
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.test_enterprise_saas_layer1_pg import _actor, _user
from tests.test_enterprise_saas_layer1_pg import pg_url as pg_url


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["suspended", "disabled", "owner_revoked", "target_revoked"])
@pytest.mark.parametrize("entry", ["enterprise", "web"])
async def test_transfer_rechecks_authority_after_authorize(pg_url, change, entry):
    engine = create_engine(pg_url)
    await engine.init()
    try:
        web = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        owner = await _user(web, "iron-owner@example.com")
        target = await _user(web, "iron-target@example.com")
        org = await iam.create_workspace(
            actor_user_id=owner, name="Ironclad", slug="ironclad", kind="ORGANIZATION"
        )
        actor = _actor(owner, org["id"], Role.OWNER)
        _, token = await iam.invite_member(
            actor, org["id"], email="iron-target@example.com", role=Role.ADMIN
        )
        await iam.accept_invitation(token=token, user_id=target)

        class ChangedAfterAuthorization(EnterpriseIAM):
            async def authorize(self, *args, **kwargs):
                await super().authorize(*args, **kwargs)
                # A committed independent change after the initial authority read.
                async with engine.raw.begin() as conn:
                    if change in {"suspended", "disabled"}:
                        await conn.execute(
                            update(organizations)
                            .where(organizations.c.id == org["id"])
                            .values(governance_status=change.upper())
                        )
                    else:
                        revoked = owner if change == "owner_revoked" else target
                        await conn.execute(
                            update(web_memberships)
                            .where(
                                web_memberships.c.org_id == org["id"],
                                web_memberships.c.user_id == revoked,
                            )
                            .values(status="REVOKED")
                        )

        changed = ChangedAfterAuthorization(engine)
        if entry == "enterprise":
            with pytest.raises(EnterpriseError):
                await changed.transfer_ownership(
                    actor, org["id"], new_owner_user_id=target, confirmation="TRANSFER_OWNERSHIP"
                )
        else:
            # The web endpoint already authorized the caller before repository entry.
            from responsibleai.enterprise.roles import Permission

            await changed.authorize(actor, Permission.ORG_TRANSFER_OWNERSHIP, org_id=org["id"])
            assert not await web.transfer_organization_ownership(
                org_id=org["id"], current_owner_id=owner, new_owner_id=target
            )
        async with engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(web_memberships).where(web_memberships.c.org_id == org["id"])
                )
            ).all()
            roles = {row.user_id: row.role for row in rows}
            assert roles == {owner: Role.OWNER.value, target: Role.ADMIN.value}
            assert (
                await conn.scalar(
                    select(organizations.c.owner_user_id).where(organizations.c.id == org["id"])
                )
                == owner
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["enterprise", "web"])
async def test_transfer_waits_for_organization_before_memberships(pg_url, entry):
    """A competing organization-first transaction must retain membership access."""
    engine = create_engine(pg_url)
    await engine.init()
    transfer = None
    try:
        web = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        owner = await _user(web, "lock-owner@example.com")
        target = await _user(web, "lock-target@example.com")
        org = await iam.create_workspace(
            actor_user_id=owner, name="Locks", slug="locks", kind="ORGANIZATION"
        )
        actor = _actor(owner, org["id"], Role.OWNER)
        _, token = await iam.invite_member(
            actor, org["id"], email="lock-target@example.com", role=Role.ADMIN
        )
        await iam.accept_invitation(token=token, user_id=target)
        from sqlalchemy import text

        async with engine.raw.begin() as conn:
            await conn.execute(
                select(organizations).where(organizations.c.id == org["id"]).with_for_update()
            )
            if entry == "enterprise":
                transfer = asyncio.create_task(
                    iam.transfer_ownership(
                        actor,
                        org["id"],
                        new_owner_user_id=target,
                        confirmation="TRANSFER_OWNERSHIP",
                    )
                )
            else:
                transfer = asyncio.create_task(
                    web.transfer_organization_ownership(
                        org_id=org["id"], current_owner_id=owner, new_owner_id=target
                    )
                )
            # Observe the actual competing PostgreSQL statement waiting on a lock,
            # rather than assuming that a sleep reached the critical section.
            for _ in range(100):
                async with engine.raw.connect() as observer:
                    waiting = await observer.scalar(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE datname=current_database() AND pid<>pg_backend_pid() "
                            "AND wait_event_type='Lock' AND query LIKE '%organizations%')"
                        )
                    )
                if waiting:
                    break
                await asyncio.sleep(0.02)
            assert waiting, "Transfer never reached the organization lock"
            await conn.execute(text("SET LOCAL lock_timeout='500ms'"))
            await conn.execute(
                select(web_memberships)
                .where(web_memberships.c.org_id == org["id"])
                .with_for_update()
            )
        await asyncio.wait_for(transfer, 10)
        async with engine.raw.connect() as conn:
            assert (
                await conn.scalar(
                    select(organizations.c.owner_user_id).where(organizations.c.id == org["id"])
                )
                == target
            )
            rows = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.org_id == org["id"],
                        web_memberships.c.role == Role.OWNER.value,
                    )
                )
            ).all()
            assert [row.user_id for row in rows] == [target]
    finally:
        if transfer is not None:
            await asyncio.gather(transfer, return_exceptions=True)
        await engine.close()
