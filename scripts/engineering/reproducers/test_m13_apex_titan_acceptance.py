# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent counterexamples for pending TITAN security acceptance."""

from __future__ import annotations

import base64
import hashlib
import subprocess
import uuid
from contextlib import aclosing
from pathlib import Path
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.engine import create_engine, trust_fabric_identifiers, web_users
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.in_flight import _check_remote_worker_active
from responsibleai.rbac.models import Role
from responsibleai.trust_fabric.directory import normalize_identifier
from responsibleai.trust_fabric.enums import IdentifierType


def test_inspect_plugin_failure_does_not_prove_container_absence() -> None:
    backend = DockerContainerBackend()

    def docker_result(command, **kwargs):
        if command[1] == "inspect":
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="Error response from daemon: authorization plugin not found",
            )
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="daemon unavailable")

    with patch("subprocess.run", side_effect=docker_result):
        with pytest.raises(RuntimeError, match="containment unconfirmed"):
            backend._remove_containers(["wp_owned_execution"], stable_seconds=0, wait_seconds=0.01)


def test_directory_permission_failure_is_not_an_empty_registry(tmp_path: Path) -> None:
    registry = tmp_path / "registry"
    registry.mkdir()
    with (
        patch("responsibleai.isolation.in_flight._DISTRIBUTED_REGISTRY_DIR", registry),
        patch("os.scandir", side_effect=PermissionError("registry scan denied")),
    ):
        unresolved = _check_remote_worker_active("org_owned")
    assert unresolved, "A silently suppressed directory scan failure must not clear containment"


@pytest.mark.asyncio
@pytest.mark.parametrize("verify_email", [False, True], ids=["unverified", "canonical-idna"])
async def test_root_email_binding_requires_verified_canonical_claim(verify_email: bool) -> None:
    async with aclosing(isolated_pg_url("wp_apex_unverified_root")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            await _run_alembic(ini, _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            identities = WebIdentityRepository(engine)
            email = f"qualification-{uuid.uuid4().hex}@bücher.example"
            user_id, token = await identities.register(
                "Unverified owner",
                email,
                "Local-Only-Strong-42!",
            )
            if verify_email:
                await identities.verify_email(token)
            organization = await EnterpriseIAM(engine).create_workspace(
                actor_user_id=user_id,
                name="Unverified workspace",
                slug=f"unverified-{uuid.uuid4().hex}",
                kind="ORGANIZATION",
            )
            org_id = organization["id"] if isinstance(organization, dict) else organization.id
            actor = Actor(
                actor_type="USER",
                actor_id=user_id,
                user_id=user_id,
                org_id=org_id,
                role=Role.OWNER,
                membership_status="ACTIVE",
            )
            service = CustomerAuthorityService(engine)
            # API-supported default flags. These cannot prove email ownership.
            bootstrap = await service.initiate_root_bootstrap(actor, org_id=org_id)
            private_key = Ed25519PrivateKey.generate()
            signature = private_key.sign(
                f"WP_ROOT_POP:{org_id}:{bootstrap['nonce']}:{hashlib.sha256(bootstrap['token'].encode()).hexdigest()}".encode()
            )
            await service.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=bootstrap["token"],
                nonce=bootstrap["nonce"],
                root_public_key=private_key.public_key().public_bytes_raw().hex(),
                root_signature=base64.urlsafe_b64encode(signature).rstrip(b"=").decode(),
                scope_description="Local qualification",
                purpose="Email ownership regression",
                allowed_action_types=["test.harmless"],
                allowed_targets=["local:qualification"],
            )
            async with engine.raw.connect() as connection:
                verified_at = await connection.scalar(
                    select(web_users.c.email_verified_at).where(web_users.c.id == user_id)
                )
                assert (verified_at is not None) is verify_email
                identifier_state = await connection.scalar(
                    select(trust_fabric_identifiers.c.verification_state).where(
                        trust_fabric_identifiers.c.principal_id == user_id
                    )
                )
                if not verify_email:
                    assert identifier_state != "VERIFIED", (
                        "Root PoP must not verify an unverified EMAIL claim"
                    )
                else:
                    normalized = await connection.scalar(
                        select(trust_fabric_identifiers.c.normalized_value).where(
                            trust_fabric_identifiers.c.principal_id == user_id
                        )
                    )
                    assert normalized == normalize_identifier(IdentifierType.EMAIL, email)
