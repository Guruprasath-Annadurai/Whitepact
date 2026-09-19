# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL concurrency proofs for Enterprise SaaS Layer 1."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_ent_l1"):
        engine = create_engine(url)
        try:
            await engine.init()
        finally:
            await engine.close()
        yield url


async def _user(web: WebIdentityRepository, email: str) -> str:
    user_id, token = await web.register("User", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


def _actor(user_id: str, org_id: str, role: Role) -> Actor:
    return Actor(
        actor_type="human",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status="ACTIVE",
    )


@pytest.mark.asyncio
async def test_postgres_concurrent_invitation_acceptance(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        web = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        owner = await _user(web, "pg-own@example.com")
        invitee = await _user(web, "pg-inv@example.com")
        org = await iam.create_workspace(
            actor_user_id=owner, name="PG Org", slug=f"pg-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
        )
        actor = _actor(owner, org["id"], Role.OWNER)
        _id, token = await iam.invite_member(actor, org["id"], email="pg-inv@example.com", role=Role.DEVELOPER)

        async def accept() -> str | Exception:
            try:
                return await iam.accept_invitation(token=token, user_id=invitee)
            except Exception as exc:  # noqa: BLE001 — both outcomes are asserted
                return exc

        first, second = await asyncio.gather(accept(), accept())
        successes = [r for r in (first, second) if isinstance(r, str)]
        failures = [r for r in (first, second) if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], EnterpriseError)
        members = await iam.list_members(actor, org["id"])
        active = [m for m in members if m["status"] == "ACTIVE" and m["user_id"] == invitee]
        assert len(active) == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_postgres_concurrent_ownership_transfer(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        web = WebIdentityRepository(engine_a)
        iam_a = EnterpriseIAM(engine_a)
        iam_b = EnterpriseIAM(engine_b)
        owner = await _user(web, "pg-to@example.com")
        member = await _user(web, "pg-tm@example.com")
        org = await iam_a.create_workspace(
            actor_user_id=owner, name="Xfer", slug=f"xf-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
        )
        actor = _actor(owner, org["id"], Role.OWNER)
        _id, token = await iam_a.invite_member(actor, org["id"], email="pg-tm@example.com", role=Role.ADMIN)
        await iam_a.accept_invitation(token=token, user_id=member)

        async def transfer() -> bool | Exception:
            try:
                await iam_a.transfer_ownership(
                    actor, org["id"], new_owner_user_id=member, confirmation="TRANSFER_OWNERSHIP"
                )
                return True
            except Exception as exc:  # noqa: BLE001
                return exc

        async def transfer_b() -> bool | Exception:
            try:
                await iam_b.transfer_ownership(
                    actor, org["id"], new_owner_user_id=member, confirmation="TRANSFER_OWNERSHIP"
                )
                return True
            except Exception as exc:  # noqa: BLE001
                return exc

        results = await asyncio.gather(transfer(), transfer_b())
        assert any(r is True for r in results)
        members = await iam_a.list_members(actor, org["id"])
        owners = [m for m in members if m["role"] == Role.OWNER.value and m["status"] == "ACTIVE"]
        assert len(owners) == 1
        assert owners[0]["user_id"] == member
    finally:
        await engine_a.close()
        await engine_b.close()


@pytest.mark.asyncio
async def test_postgres_concurrent_api_key_rotation(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        web = WebIdentityRepository(engine_a)
        iam_a = EnterpriseIAM(engine_a)
        iam_b = EnterpriseIAM(engine_b)
        owner = await _user(web, "pg-rot@example.com")
        org = await iam_a.create_workspace(
            actor_user_id=owner, name="Rot", slug=f"rt-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL"
        )
        actor = _actor(owner, org["id"], Role.OWNER)
        envs = {e["type"]: e for e in await iam_a.list_environments(actor, org["id"])}
        rec, old_secret = await iam_a.create_api_key(
            actor,
            org["id"],
            name="dev",
            environment_id=envs["DEVELOPMENT"]["id"],
            scopes=("usage:read",),
            expires_at=None,
        )

        async def rotate(iam: EnterpriseIAM) -> tuple[str, str] | Exception:
            try:
                new_rec, secret = await iam.rotate_api_key(actor, org["id"], rec["id"], overlap_seconds=60)
                return new_rec["id"], secret
            except Exception as exc:  # noqa: BLE001
                return exc

        left, right = await asyncio.gather(rotate(iam_a), rotate(iam_b))
        oks = [r for r in (left, right) if isinstance(r, tuple)]
        errs = [r for r in (left, right) if isinstance(r, Exception)]
        assert len(oks) >= 1
        # At most one winner under FOR UPDATE; the other may fail closed.
        assert len(oks) + len(errs) == 2
        new_secret = oks[0][1]
        await iam_a.authenticate_api_key(new_secret, expected_org_id=org["id"])
        await iam_a.revoke_api_key(actor, org["id"], rec["id"])
        with pytest.raises(EnterpriseError):
            await iam_a.authenticate_api_key(old_secret, expected_org_id=org["id"])
    finally:
        await engine_a.close()
        await engine_b.close()
