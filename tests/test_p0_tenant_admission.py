# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""P0/P1 tenant admission: unknown, deleted, suspended, forged, mismatched,
cross-tenant, invalid role, expired session, and revoked identity."""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

import responsibleai.dashboard.app as app_module
from responsibleai.auth.oidc import JWTClaims
from responsibleai.auth.saml import SAMLAssertionClaims, SAMLConfig, mint_session_token
from responsibleai.auth.tenant_admission import TenantAdmissionDeniedError, admit_sso_principal
from responsibleai.dashboard.app import _resolve_oidc_context, _resolve_saml_context
from responsibleai.db import OrgRepository, WebIdentityRepository, create_engine
from responsibleai.rbac.models import GovernanceStatus, Role


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _org(repo: OrgRepository, slug: str):
    return await repo.create_org(slug, f"{slug}-{uuid.uuid4().hex[:8]}")


async def _bind(engine, org_id: str, subject: str, role: Role = Role.VIEWER):
    return await WebIdentityRepository(engine).bind_sso_principal(
        org_id=org_id,
        issuer="https://idp.example",
        subject=subject,
        role=role,
        email=f"{subject}-{org_id[:8]}@example.com",
    )


def _oidc(org_id: str | None, roles: list[str], sub: str = "user-1") -> MagicMock:
    provider = MagicMock()
    provider.issuer = "https://idp.example"
    provider.validate_token = AsyncMock(return_value=JWTClaims(sub=sub, org_id=org_id, roles=roles))
    return provider


@pytest.mark.asyncio
async def test_oidc_unknown_organization_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc("missing-org", ["ADMIN"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_deleted_organization_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "deleted")
    await _bind(engine, org.id, "user-1", Role.ADMIN)
    await repo.deactivate_org(org.id)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["ADMIN"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_suspended_organization_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "suspended")
    await _bind(engine, org.id, "user-1", Role.ADMIN)
    assert await repo.set_governance_status(org.id, GovernanceStatus.SUSPENDED)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["ADMIN"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_forged_org_claim_without_binding_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "forged")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["OWNER"], sub="intruder"))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_mismatched_organization_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    home = await _org(repo, "home")
    other = await _org(repo, "other")
    await _bind(engine, home.id, "user-1", Role.ADMIN)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(other.id, ["ADMIN"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_cross_tenant_session_stays_on_bound_org(engine) -> None:
    repo = OrgRepository(engine)
    home = await _org(repo, "home")
    other = await _org(repo, "other")
    await _bind(engine, home.id, "user-1", Role.ANALYST)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(home.id, ["ANALYST"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    ctx = await _resolve_oidc_context("jwt")
    assert ctx is not None
    assert ctx.org_id == home.id
    assert ctx.org_id != other.id
    assert ctx.role == Role.ANALYST
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_invalid_role_claim_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "roles")
    await _bind(engine, org.id, "user-1", Role.VIEWER)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["not-a-role"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_role_elevation_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "elevate")
    await _bind(engine, org.id, "user-1", Role.VIEWER)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["OWNER"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_oidc_revoked_identity_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "revoked")
    user_id = await _bind(engine, org.id, "user-1", Role.ADMIN)
    await WebIdentityRepository(engine).suspend_user(user_id)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_oidc_provider", _oidc(org.id, ["ADMIN"]))
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_oidc_context("jwt") is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_saml_expired_session_is_rejected(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "saml-exp")
    identity = WebIdentityRepository(engine)
    await identity.bind_sso_principal(
        org_id=org.id,
        issuer="test-idp",
        subject="alice",
        role=Role.ADMIN,
        email=f"alice-{org.id[:8]}@example.com",
    )
    config = SAMLConfig(
        idp_entity_id="test-idp",
        idp_sso_url="https://idp.example/sso",
        idp_x509_cert="cert",
        sp_entity_id="https://whitepact.example/saml",
        acs_url="https://whitepact.example/acs",
        session_secret="test-secret",
    )
    claims = SAMLAssertionClaims(sub="alice", org_id=org.id, roles=["ADMIN"])
    token = mint_session_token(config, claims)
    monkeypatch.setattr(app_module, "_saml_config", config)
    monkeypatch.setattr(app_module, "_org_repo", repo)
    issued_at = time.time()
    monkeypatch.setattr("responsibleai.auth.saml.time.time", lambda: issued_at + 7200)
    assert await _resolve_saml_context(token) is None


@pytest.mark.asyncio
async def test_saml_revoked_membership_is_rejected(engine) -> None:
    repo = OrgRepository(engine)
    org = await _org(repo, "saml-rev")
    identity = WebIdentityRepository(engine)
    await identity.bind_sso_principal(
        org_id=org.id,
        issuer="test-idp",
        subject="alice",
        role=Role.ADMIN,
        email=f"alice-{org.id[:8]}@example.com",
    )
    assert await identity.revoke_sso_membership(issuer="test-idp", subject="alice", org_id=org.id)
    config = SAMLConfig(
        idp_entity_id="test-idp",
        idp_sso_url="https://idp.example/sso",
        idp_x509_cert="cert",
        sp_entity_id="https://whitepact.example/saml",
        acs_url="https://whitepact.example/acs",
        session_secret="test-secret",
    )
    claims = SAMLAssertionClaims(sub="alice", org_id=org.id, roles=["ADMIN"])
    token = mint_session_token(config, claims)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_saml_config", config)
    monkeypatch.setattr(app_module, "_org_repo", repo)
    assert await _resolve_saml_context(token) is None
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_admission_reasons_are_specific(engine) -> None:
    repo = OrgRepository(engine)
    identity = WebIdentityRepository(engine)
    with pytest.raises(TenantAdmissionDeniedError) as missing:
        await admit_sso_principal(
            org_repo=repo,
            identity_repo=identity,
            claimed_org_id=None,
            issuer="https://idp.example",
            subject="user-1",
            claimed_roles=[],
        )
    assert missing.value.reason == "unknown_organization"
