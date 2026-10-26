# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Directory binding is not legal identity assurance.

Administrative SSO provisioning must not write IDENTITY_VERIFIED. This is a
component counterexample, not default-customer acceptance and not a provider
proofing simulation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select

from responsibleai.auth.tenant_admission import admit_sso_principal
from responsibleai.db import OrgRepository, WebIdentityRepository, create_engine
from responsibleai.db.engine import enterprise_environments, identity_verifications, organizations
from responsibleai.enterprise.errors import IDENTITY_VERIFICATION_REQUIRED
from responsibleai.enterprise.issuance import CredentialIssuancePolicy
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.rbac.models import Role


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _workspace(engine) -> tuple[str, str]:
    now = datetime.now(UTC).isoformat()
    org_id = str(uuid.uuid4())
    env_id = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Directory tenant",
                slug=f"sso-{uuid.uuid4().hex[:8]}",
                monthly_budget_usd=0,
                created_at=now,
                plan="FREE",
                governance_status="ACTIVE",
                workspace_kind="ORGANIZATION",
            )
        )
        await conn.execute(
            insert(enterprise_environments).values(
                id=env_id,
                org_id=org_id,
                type="DEVELOPMENT",
                name="development",
                status="ACTIVE",
                created_at=now,
                metadata_json="{}",
            )
        )
    return org_id, env_id


@pytest.mark.asyncio
async def test_new_directory_user_is_not_identity_verified(engine) -> None:
    org_id, env_id = await _workspace(engine)
    identity = WebIdentityRepository(engine)
    user_id = await identity.bind_sso_principal(
        org_id=org_id,
        issuer="https://idp.example",
        subject="directory-user",
        role=Role.ADMIN,
        email="directory.user@example.com",
    )
    binding = await identity.lookup_sso_binding(
        issuer="https://idp.example", subject="directory-user", org_id=org_id
    )
    assert binding is not None
    assert binding.user_verification_status == "BASIC_VERIFIED"
    assert binding.user_verification_status != "IDENTITY_VERIFIED"
    verification = VerificationService(engine, HmacVerificationProvider("not-a-provider-event"))
    human = await verification.get_human_status(user_id)
    assert human["status"] == "BASIC_VERIFIED"
    assert human["provider"] is None
    async with engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(identity_verifications.c.id).where(identity_verifications.c.user_id == user_id)
            )
        ).fetchall()
    assert rows == []
    decision = await CredentialIssuancePolicy(engine, verification).evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("governance:read",),
    )
    assert decision.allowed is False
    assert decision.reason_code == IDENTITY_VERIFICATION_REQUIRED
    admitted = await admit_sso_principal(
        org_repo=OrgRepository(engine),
        identity_repo=identity,
        claimed_org_id=org_id,
        issuer="https://idp.example",
        subject="directory-user",
        claimed_roles=["ADMIN"],
    )
    assert admitted.user_id == user_id
    assert admitted.role == Role.ADMIN
    assert admitted.org_id == org_id
    rebound = await identity.bind_sso_principal(
        org_id=org_id,
        issuer="https://idp.example",
        subject="directory-user-again",
        role=Role.ADMIN,
        email="directory.user@example.com",
    )
    assert rebound == user_id
    again = await identity.lookup_sso_binding(
        issuer="https://idp.example", subject="directory-user-again", org_id=org_id
    )
    assert again is not None
    assert again.user_verification_status == "BASIC_VERIFIED"


@pytest.mark.asyncio
async def test_rebind_does_not_elevate_an_existing_account(engine) -> None:
    org_id, _env_id = await _workspace(engine)
    identity = WebIdentityRepository(engine)
    user_id, _token = await identity.register(
        "Existing Human", "existing.human@example.com", "correct-horse-battery-staple-9"
    )
    bound = await identity.bind_sso_principal(
        org_id=org_id,
        issuer="https://idp.example",
        subject="existing-human",
        role=Role.ADMIN,
        email="existing.human@example.com",
    )
    assert bound == user_id
    binding = await identity.lookup_sso_binding(
        issuer="https://idp.example", subject="existing-human", org_id=org_id
    )
    assert binding is not None
    assert binding.user_verification_status == "UNVERIFIED"
    human = await VerificationService(
        engine, HmacVerificationProvider("not-a-provider-event")
    ).get_human_status(user_id)
    assert human["status"] != "IDENTITY_VERIFIED"
