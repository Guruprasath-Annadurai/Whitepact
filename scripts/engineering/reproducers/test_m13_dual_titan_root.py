# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run the immutable authority boundary with explicit optional flag values."""

import base64
import hashlib
import uuid
from contextlib import aclosing

import asyncpg
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.reproducers.test_m13_corrective_authority import (
    test_unverified_owner_cannot_activate_root_with_default_flags as assert_unverified_denied,
)
from tests.m13_owner_qualification import qualify_owner, root_completion_assertion
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role


@pytest.mark.asyncio
@pytest.mark.parametrize("require_identity_assurance", [False, True])
async def test_unverified_owner_denied_with_explicit_assurance_flag(
    monkeypatch, require_identity_assurance: bool
) -> None:
    original = CustomerAuthorityService.initiate_root_bootstrap

    async def initiate(self, actor, **kwargs):
        return await original(
            self, actor, **kwargs, require_identity_assurance=require_identity_assurance
        )

    monkeypatch.setattr(CustomerAuthorityService, "initiate_root_bootstrap", initiate)
    await assert_unverified_denied()


@pytest.mark.asyncio
@pytest.mark.parametrize("revoked_boundary", ["email", "membership", "organization"])
async def test_completion_rechecks_persisted_owner_qualification(revoked_boundary: str) -> None:
    """Real PostgreSQL lifecycle regression; SQL revocation is not a customer receipt."""
    async with aclosing(isolated_pg_url("wp_dual_root_recheck")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            await _run_alembic(ini, _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            identities = WebIdentityRepository(engine)
            user_id, token = await identities.register(
                "Verified customer", f"dual-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
            )
            await identities.verify_email(token)
            org = await EnterpriseIAM(engine).create_workspace(
                actor_user_id=user_id,
                name="Qualification",
                slug=f"dual-{uuid.uuid4().hex}",
                kind="ORGANIZATION",
            )
            org_id = org["id"] if isinstance(org, dict) else org.id
            actor = Actor(
                actor_type="USER",
                actor_id=user_id,
                user_id=user_id,
                org_id=org_id,
                role=Role.OWNER,
                membership_status="ACTIVE",
            )
            service = CustomerAuthorityService(engine)
            actor, owner_key, credential = await qualify_owner(engine, actor)
            ceremony = await service.initiate_root_bootstrap(actor, org_id=org_id)
            key = Ed25519PrivateKey.generate()
            public_key = key.public_key().public_bytes_raw().hex()
            assertion = await root_completion_assertion(
                service, actor, ceremony, public_key, owner_key, credential
            )
            connection = await asyncpg.connect(database)
            try:
                if revoked_boundary == "email":
                    await connection.execute(
                        "UPDATE web_users SET email_verified_at=NULL,verification_status='UNVERIFIED' WHERE id=$1",
                        user_id,
                    )
                elif revoked_boundary == "membership":
                    await connection.execute(
                        "UPDATE web_memberships SET status='REVOKED' WHERE user_id=$1 AND org_id=$2",
                        user_id,
                        org_id,
                    )
                else:
                    await connection.execute(
                        "UPDATE organizations SET governance_status='SUSPENDED' WHERE id=$1", org_id
                    )
                message = f"WP_ROOT_POP:{org_id}:{ceremony['nonce']}:{hashlib.sha256(ceremony['token'].encode()).hexdigest()}"
                with pytest.raises(EnterpriseError):
                    await service.complete_root_bootstrap(
                        actor,
                        org_id=org_id,
                        token=ceremony["token"],
                        nonce=ceremony["nonce"],
                        root_public_key=public_key,
                        webauthn_assertion=assertion,
                        root_signature=base64.urlsafe_b64encode(key.sign(message.encode()))
                        .rstrip(b"=")
                        .decode(),
                        scope_description="Qualification",
                        purpose="Persisted revocation denial",
                        allowed_action_types=["test.harmless"],
                        allowed_targets=["local:qualification"],
                    )
                for table in (
                    "governance_root_authority_records",
                    "governance_consent_proofs",
                    "trust_fabric_principals",
                ):
                    assert await connection.fetchval(f"SELECT count(*) FROM {table}") == 0
            finally:
                await connection.close()
