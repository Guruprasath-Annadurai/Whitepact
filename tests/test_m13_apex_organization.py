# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated rename regressions; fixture accounts do not qualify root authority."""

import asyncio

import pytest

from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.service import EnterpriseIAM
from responsibleai.rbac.models import Role

pytest_plugins = ["tests.test_m13p4_inventory_read_contract", "tests.test_m13_apex_directory"]


async def account(client, role=Role.OWNER):
    engine = get_enterprise_engine()
    identities = WebIdentityRepository(engine)
    user, verification = await identities.register(
        "Rename account", f"apex.rename.{role.value.lower()}@example.com", "StrongPassword123!@#"
    )
    await identities.verify_email(verification)
    creator = user
    if role != Role.OWNER:
        creator, proof = await identities.register(
            "Inviting owner", "apex.inviting.owner@example.com", "StrongPassword123!@#"
        )
        assert await identities.verify_email(proof)
    creation_token, creation_csrf = await identities.create_session(creator)
    org = await EnterpriseIAM(engine).create_workspace(
        actor_user_id=creator,
        name="Original",
        slug=f"rename-apex-{role.value.lower()}",
        kind="ORGANIZATION",
        session_token=creation_token,
        csrf=creation_csrf,
    )
    if role != Role.OWNER:
        _, invitation = await identities.create_invitation(
            org_id=org["id"],
            email=f"apex.rename.{role.value.lower()}@example.com",
            role=role,
            invited_by_user_id=creator,
        )
        assert await identities.accept_invitation(invitation, user) == org["id"]
    token, csrf = await identities.create_session(user, org_id=org["id"])
    client.cookies.set("wp_session", token)
    client.cookies.set("wp_csrf", csrf)
    return org["id"], user, {"X-WP-CSRF": csrf}


@pytest.mark.asyncio
async def test_all_workspace_preconditions_must_agree_and_no_conflict_mutates(inventory_client):
    client = inventory_client
    org, _, headers = await account(client)
    for body, extra in [
        ({"expected_organization_id": "other"}, {}),
        ({"organization_id": "other"}, {}),
        ({}, {"X-WhitePact-Org-ID": "other"}),
        ({"expected_name": "Stale"}, {}),
    ]:
        response = await client.patch(
            f"/api/web/organizations/{org}",
            headers={**headers, **extra},
            json={"name": "Wrong", **body},
        )
        assert response.status_code == 409
    current = await client.get("/api/web/session")
    assert current.json()["organization"]["name"] == "Original"
    valid = await client.patch(
        f"/api/web/organizations/{org}",
        headers=headers,
        json={"name": "Renamed", "expected_name": "Original", "expected_organization_id": org},
    )
    assert valid.status_code == 200 and valid.json()["name"] == "Renamed"
    stale = await client.patch(
        f"/api/web/organizations/{org}",
        headers=headers,
        json={"name": "Lost update", "expected_name": "Original"},
    )
    assert stale.status_code == 409


@pytest.mark.asyncio
async def test_rename_preserves_auth_csrf_and_role_requirements(inventory_client):
    client = inventory_client
    assert (
        await client.patch("/api/web/organization", json={"name": "Unauthorized"})
    ).status_code == 401
    org, user, headers = await account(client)
    assert (
        await client.patch("/api/web/organization", json={"name": "No CSRF"})
    ).status_code == 403
    _, _, headers = await account(client, Role.VIEWER)
    response = await client.patch(
        "/api/web/organization", headers=headers, json={"name": "Viewer rename"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_rename_compare_and_set_has_one_winner_on_real_database(directory):
    repository = OrgRepository(directory.db)
    outcomes = await asyncio.gather(
        repository.update_org_name("apex-org", "First", expected_name="APEX"),
        repository.update_org_name("apex-org", "Second", expected_name="APEX"),
    )
    assert sum(outcomes) == 1
    stored = await repository.get_org("apex-org")
    assert stored is not None and stored.name in {"First", "Second"}
