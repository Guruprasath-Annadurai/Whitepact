"""Positive control for the authenticator used before persisted-revocation probes."""

import uuid

import pytest

from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.m13_owner_qualification import qualify_owner, root_completion_assertion
from tests.test_m12fs_root_hardening import _configure_test_env as _configure_test_env
from tests.test_m12fs_root_hardening import _fresh_root_proof


@pytest.mark.asyncio
async def test_verified_owner_can_complete_exact_bound_operation(_configure_test_env):
    verified_engine = _configure_test_env
    identities = WebIdentityRepository(verified_engine)
    user, token = await identities.register(
        "Qualification owner", f"owner-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
    )
    await identities.verify_email(token)
    org = await EnterpriseIAM(verified_engine).create_workspace(
        actor_user_id=user, name="Qualification", slug=uuid.uuid4().hex, kind="ORGANIZATION"
    )
    actor = Actor(
        actor_type="USER",
        actor_id=user,
        user_id=user,
        org_id=org["id"],
        role=Role.OWNER,
        membership_status="ACTIVE",
    )
    actor, key, credential = await qualify_owner(verified_engine, actor)
    service = CustomerAuthorityService(verified_engine)
    ceremony = await service.initiate_root_bootstrap(actor, org_id=actor.org_id)
    public, signature = _fresh_root_proof(actor.org_id, ceremony)
    assertion = await root_completion_assertion(service, actor, ceremony, public, key, credential)
    result = await service.complete_root_bootstrap(
        actor,
        org_id=actor.org_id,
        token=ceremony["token"],
        nonce=ceremony["nonce"],
        root_public_key=public,
        root_signature=signature,
        webauthn_assertion=assertion,
        scope_description="Qualification",
        purpose="Positive control",
        allowed_action_types=["test.harmless"],
        allowed_targets=["local:qualification"],
    )
    assert result
