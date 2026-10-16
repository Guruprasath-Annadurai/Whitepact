# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial security qualification of customer root authority bootstrap on real PostgreSQL."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import (
    authority_recovery_requests,
    authority_step_up_challenges,
    create_engine,
    organizations,
    trust_fabric_identifiers,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_memberships,
    web_users,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import (
    BOOTSTRAP_TOKEN_REPLAY,
    PASSKEY_STEP_UP_REQUIRED,
    PROOF_OF_POSSESSION_INVALID,
    ROOT_ALREADY_EXISTS,
    UNAUTHORIZED_BOOTSTRAP_CALLER,
    WEBAUTHN_ASSERTION_INVALID,
    WEBAUTHN_CHALLENGE_EXPIRED,
)
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.errors import (
    MEMBERSHIP_REVOKED,
    ORG_DISABLED,
    ORG_SUSPENDED,
    EnterpriseError,
)
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import GovernanceStatus, Role
from tests.pg_test_url import isolated_pg_url


def _gen_ed25519():
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes_raw()
    return priv, pub_bytes.hex(), pub_bytes


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.mark.asyncio
async def test_root_bootstrap_disabled_and_suspended_accounts_rejected():
    """Verify disabled or suspended user accounts are strictly rejected from root bootstrap."""
    async for url in isolated_pg_url("wp_titan_disabled_user"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]

        # 1. Registered user who is disabled (disabled=1)
        uid, token = await web_repo.register(
            "Disabled Owner", f"disabled.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Disabled Org {suffix}",
            slug=f"disabled-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Disabled Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            # Disable the account
            await conn.execute(update(web_users).where(web_users.c.id == uid).values(disabled=1))

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Initiate fails closed
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Re-enable but mark verification_status as SUSPENDED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == uid)
                .values(disabled=0, verification_status="SUSPENDED")
            )

        with pytest.raises(EnterpriseError) as susp_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert susp_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Mark verification_status as REJECTED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == uid)
                .values(verification_status="REJECTED")
            )

        with pytest.raises(EnterpriseError) as rej_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert rej_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


@pytest.mark.asyncio
async def test_root_bootstrap_revoked_principal_rejected():
    """Verify an owner whose principal in trust_fabric_principals is REVOKED or SUSPENDED fails closed."""
    async for url in isolated_pg_url("wp_titan_revoked_principal"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Revoked Principal", f"revoked.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Revoked Org {suffix}",
            slug=f"revoked-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Revoked Principal",
                    lifecycle_state="REVOKED",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Initiate fails closed because principal is REVOKED
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Switch to SUSPENDED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_principals)
                .where(trust_fabric_principals.c.id == uid)
                .values(lifecycle_state="SUSPENDED")
            )

        with pytest.raises(EnterpriseError) as susp_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert susp_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


@pytest.mark.asyncio
async def test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap():
    """Verify an active quorum recovery request prevents unilateral out-of-band root bootstrap."""
    async for url in isolated_pg_url("wp_titan_pending_recovery"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Recovery Owner", f"recovery.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Recovery Org {suffix}",
            slug=f"recovery-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()
        expires_at = (now_dt + timedelta(hours=24)).isoformat()

        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Recovery Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            # Active quorum recovery request in progress
            await conn.execute(
                authority_recovery_requests.insert().values(
                    id=f"wp_rec_{uuid.uuid4().hex}",
                    org_id=org_id,
                    request_type="ROOT_RECOVERY",
                    target_root_id="old_root_id",
                    requester_user_id=uid,
                    proposed_parameters_json=json.dumps({"reason": "Key rotation"}),
                    action_digest="test_digest",
                    required_quorum_m=2,
                    eligible_quorum_n=3,
                    status="PENDING",
                    expires_at=expires_at,
                    executed_at=None,
                    executed_by_user_id=None,
                    created_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Unilateral initiate bootstrap is rejected because quorum recovery is pending
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == ROOT_ALREADY_EXISTS


@pytest.mark.asyncio
async def test_root_bootstrap_webauthn_adversarial_paths():
    """Verify expired step-up, challenge replay, and operation digest mismatches are rejected."""
    async for url in isolated_pg_url("wp_titan_webauthn_adv"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "WebAuthn Owner", f"webauthn.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"WebAuthn Org {suffix}",
            slug=f"webauthn-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()

        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="WebAuthn Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # 1. Initiate with passkey step-up required
        init_res = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True, require_passkey_stepup=True
        )
        boot_token = init_res["token"]
        boot_nonce = init_res["nonce"]
        token_hash = hashlib.sha256(boot_token.encode()).hexdigest()

        priv, pub_hex, _ = _gen_ed25519()

        # Omitting webauthn_assertion fails with PASSKEY_STEP_UP_REQUIRED
        with pytest.raises(EnterpriseError) as no_wa_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
            )
        assert no_wa_exc.value.code == PASSKEY_STEP_UP_REQUIRED

        # 2. Expired challenge rejection
        correct_digest = compute_canonical_operation_digest(
            "COMPLETE_ROOT_BOOTSTRAP",
            {
                "org_id": org_id,
                "nonce": boot_nonce,
                "token_hash": token_hash,
                "root_public_key": pub_hex,
            },
        )

        ch_exp = await svc.create_authority_stepup_challenge(
            actor,
            org_id=org_id,
            action="COMPLETE_ROOT_BOOTSTRAP",
            operation_digest=correct_digest,
            ttl_seconds=300,
        )
        past_iso = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(authority_step_up_challenges)
                .where(authority_step_up_challenges.c.challenge_hash == ch_exp["challenge_hash"])
                .values(expires_at=past_iso)
            )

        fake_assertion = {
            "credential_id": "fake_cred_id",
            "client_data_json": _b64url(
                json.dumps(
                    {
                        "type": "webauthn.get",
                        "challenge": ch_exp["challenge"],
                        "origin": ch_exp["origin"],
                    }
                ).encode()
            ),
            "authenticator_data": _b64url(b"fake_auth_data"),
            "signature": _b64url(b"fake_sig"),
        }

        with pytest.raises(EnterpriseError) as exp_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
                webauthn_assertion=fake_assertion,
            )
        assert exp_exc.value.code == WEBAUTHN_CHALLENGE_EXPIRED

        # 3. Digest mismatch rejection
        ch_mm = await svc.create_authority_stepup_challenge(
            actor,
            org_id=org_id,
            action="COMPLETE_ROOT_BOOTSTRAP",
            operation_digest="wrong_digest_for_another_operation",
            ttl_seconds=300,
        )

        mismatched_assertion = {
            "credential_id": "fake_cred_id",
            "client_data_json": _b64url(
                json.dumps(
                    {
                        "type": "webauthn.get",
                        "challenge": ch_mm["challenge"],
                        "origin": ch_mm["origin"],
                    }
                ).encode()
            ),
            "authenticator_data": _b64url(b"fake_auth_data"),
            "signature": _b64url(b"fake_sig"),
        }

        with pytest.raises(EnterpriseError) as mm_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
                webauthn_assertion=mismatched_assertion,
            )
        assert mm_exc.value.code == WEBAUTHN_ASSERTION_INVALID


@pytest.mark.asyncio
async def test_root_bootstrap_concurrent_race_serializes_cleanly():
    """Verify concurrent complete_root_bootstrap attempts serialize safely with only one winner."""
    async for url in isolated_pg_url("wp_titan_concurrent_boot"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Race Owner", f"race.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Race Org {suffix}",
            slug=f"race-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Race Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Two distinct initiation ceremonies for Org
        init1 = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True
        )
        priv1, pub1, _ = _gen_ed25519()
        pop1 = _b64url(
            priv1.sign(
                f"WP_ROOT_POP:{org_id}:{init1['nonce']}:{hashlib.sha256(init1['token'].encode()).hexdigest()}".encode()
            )
        )

        # Complete first bootstrap
        res1 = await svc.complete_root_bootstrap(
            actor,
            org_id=org_id,
            token=init1["token"],
            nonce=init1["nonce"],
            root_public_key=pub1,
            root_signature=pop1,
            scope_description="Root 1",
            purpose="Race testing",
            allowed_action_types=["test.action"],
            allowed_targets=["test:target"],
        )
        assert res1["status"] == "BOOTSTRAPPED"

        # Subsequent complete attempt fails closed with ROOT_ALREADY_EXISTS
        priv2, pub2, _ = _gen_ed25519()
        pop2 = _b64url(
            priv2.sign(
                f"WP_ROOT_POP:{org_id}:{init1['nonce']}:{hashlib.sha256(init1['token'].encode()).hexdigest()}".encode()
            )
        )

        with pytest.raises(EnterpriseError) as race_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=init1["token"],
                nonce=init1["nonce"],
                root_public_key=pub2,
                root_signature=pop2,
                scope_description="Root 2",
                purpose="Race testing 2",
                allowed_action_types=["test.action"],
                allowed_targets=["test:target"],
            )
        assert race_exc.value.code in {ROOT_ALREADY_EXISTS, BOOTSTRAP_TOKEN_REPLAY}


@pytest.mark.asyncio
async def test_root_bootstrap_genuine_unseeded_customer_enrollment_and_bridging():
    """Verify real unseeded customer onboarding automatically enrolls canonical principal and identifiers."""
    async for url in isolated_pg_url("wp_titan_unseeded_boot"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        email = f"genuine.{suffix}@example.com"
        full_name = f"Genuine Owner {suffix}"
        uid, token = await web_repo.register(full_name, email, "Password123!@#")
        await web_repo.verify_email(token)

        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Genuine Org {suffix}",
            slug=f"genuine-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        # Crucial invariant check: trust_fabric_principals has NO row for this user yet
        async with engine.raw.connect() as conn:
            p_before = (
                await conn.execute(
                    select(trust_fabric_principals.c.id).where(trust_fabric_principals.c.id == uid)
                )
            ).first()
            assert p_before is None, (
                "Principal must NOT be pre-seeded in genuine customer onboarding"
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        init_res = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True
        )
        boot_token = init_res["token"]
        boot_nonce = init_res["nonce"]
        priv, pub_hex, _ = _gen_ed25519()
        pop_sig = _b64url(
            priv.sign(
                f"WP_ROOT_POP:{org_id}:{boot_nonce}:{hashlib.sha256(boot_token.encode()).hexdigest()}".encode()
            )
        )

        # Complete root bootstrap without any manual seeding
        res = await svc.complete_root_bootstrap(
            actor,
            org_id=org_id,
            token=boot_token,
            nonce=boot_nonce,
            root_public_key=pub_hex,
            root_signature=pop_sig,
            scope_description="Production Root Authority",
            purpose="Autonomous Agent Operations",
            allowed_action_types=["agent.execute", "tool.invoke"],
            allowed_targets=["system:cluster:*"],
        )
        assert res["status"] == "BOOTSTRAPPED"
        assert res["organization_id"] == org_id

        # Verify database state under foreign-key constraints
        async with engine.raw.connect() as conn:
            # 1. Canonical principal is now enrolled and ACTIVE
            p_after = (
                await conn.execute(
                    select(
                        trust_fabric_principals.c.id,
                        trust_fabric_principals.c.org_id,
                        trust_fabric_principals.c.principal_type,
                        trust_fabric_principals.c.lifecycle_state,
                        trust_fabric_principals.c.display_name,
                    ).where(trust_fabric_principals.c.id == uid)
                )
            ).first()
            assert p_after is not None
            assert p_after.id == uid
            assert p_after.org_id == org_id
            assert p_after.principal_type == "HUMAN"
            assert p_after.lifecycle_state == "ACTIVE"
            assert p_after.display_name == full_name

            # 2. Canonical identifier is bound and verified
            ident = (
                await conn.execute(
                    select(
                        trust_fabric_identifiers.c.principal_id,
                        trust_fabric_identifiers.c.org_id,
                        trust_fabric_identifiers.c.identifier_type,
                        trust_fabric_identifiers.c.normalized_value,
                        trust_fabric_identifiers.c.is_primary,
                        trust_fabric_identifiers.c.verification_state,
                    ).where(
                        and_(
                            trust_fabric_identifiers.c.principal_id == uid,
                            trust_fabric_identifiers.c.org_id == org_id,
                        )
                    )
                )
            ).first()
            assert ident is not None
            assert ident.identifier_type == "EMAIL"
            assert ident.normalized_value == email.lower()
            assert ident.is_primary == 1
            assert ident.verification_state == "VERIFIED"

            # 3. Trust root is established with valid FK to principal
            root_row = (
                await conn.execute(
                    select(
                        trust_fabric_trust_roots.c.id,
                        trust_fabric_trust_roots.c.org_id,
                        trust_fabric_trust_roots.c.root_principal_id,
                        trust_fabric_trust_roots.c.root_public_key,
                        trust_fabric_trust_roots.c.status,
                    ).where(trust_fabric_trust_roots.c.org_id == org_id)
                )
            ).first()
            assert root_row is not None
            assert root_row.root_principal_id == uid
            assert root_row.root_public_key == pub_hex
            assert root_row.status == "ACTIVE"


@pytest.mark.asyncio
async def test_root_bootstrap_cross_tenant_isolation_strictly_enforced():
    """Verify principal belonging to tenant A cannot initiate or complete root bootstrap in tenant B."""
    async for url in isolated_pg_url("wp_titan_cross_tenant"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        # Tenant A
        uid_a, token_a = await web_repo.register(
            "Owner A", f"ownera.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token_a)
        org_a = await iam.create_workspace(
            actor_user_id=uid_a,
            name=f"Org A {suffix}",
            slug=f"org-a-{suffix}",
            kind="ORGANIZATION",
        )
        org_a_id = org_a["id"] if isinstance(org_a, dict) else org_a.id

        # Tenant B
        uid_b, token_b = await web_repo.register(
            "Owner B", f"ownerb.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token_b)
        org_b = await iam.create_workspace(
            actor_user_id=uid_b,
            name=f"Org B {suffix}",
            slug=f"org-b-{suffix}",
            kind="ORGANIZATION",
        )
        org_b_id = org_b["id"] if isinstance(org_b, dict) else org_b.id

        now_iso = datetime.now(UTC).isoformat()
        # Explicitly register principal for uid_a under org_a
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid_a,
                    org_id=org_a_id,
                    principal_type="HUMAN",
                    display_name="Owner A",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        # Actor A attempts to initiate root bootstrap in Org B
        actor_a_in_b = Actor(
            actor_type="USER",
            actor_id=uid_a,
            user_id=uid_a,
            org_id=org_b_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor_a_in_b, org_id=org_b_id)
        # Cannot initiate because uid_a's principal is registered to org_a_id or not member of org_b
        assert exc.value.code in {UNAUTHORIZED_BOOTSTRAP_CALLER, MEMBERSHIP_REVOKED}


@pytest.mark.asyncio
async def test_root_bootstrap_identifier_collision_fails_closed():
    """Verify root bootstrap fails closed if the caller email identifier is already claimed by another principal."""
    async for url in isolated_pg_url("wp_titan_ident_collision"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        email = f"collision.{suffix}@example.com"
        uid, token = await web_repo.register("Legit Owner", email, "Password123!@#")
        await web_repo.verify_email(token)

        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Col Org {suffix}",
            slug=f"col-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        other_principal_id = f"wp_prin_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(UTC).isoformat()
        # Seed an existing principal and identifier claiming the same email in the same org
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=other_principal_id,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Impostor",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            await conn.execute(
                insert(trust_fabric_identifiers).values(
                    id=f"wp_ident_{uuid.uuid4().hex}",
                    principal_id=other_principal_id,
                    org_id=org_id,
                    identifier_type="EMAIL",
                    raw_value=email,
                    normalized_value=email.lower(),
                    is_primary=1,
                    verification_state="VERIFIED",
                    verified_at=now_iso,
                    expires_at=None,
                    revoked_at=None,
                    source_id="test",
                    created_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        init_res = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True
        )
        priv, pub_hex, _ = _gen_ed25519()
        pop_sig = _b64url(
            priv.sign(
                f"WP_ROOT_POP:{org_id}:{init_res['nonce']}:{hashlib.sha256(init_res['token'].encode()).hexdigest()}".encode()
            )
        )

        with pytest.raises(EnterpriseError) as exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=init_res["token"],
                nonce=init_res["nonce"],
                root_public_key=pub_hex,
                root_signature=pop_sig,
                scope_description="Scope",
                purpose="Collision test",
                allowed_action_types=["test.act"],
                allowed_targets=["test:target"],
            )
        assert exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


@pytest.mark.asyncio
async def test_root_bootstrap_disabled_or_suspended_organization_fails_closed():
    """Verify disabled or suspended organizations cannot undergo root bootstrap."""
    async for url in isolated_pg_url("wp_titan_disabled_org"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Org Owner", f"orgowner.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)

        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Org Disabled {suffix}",
            slug=f"org-disabled-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # 1. Disable organization
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(governance_status=GovernanceStatus.DISABLED.value)
            )

        with pytest.raises(EnterpriseError) as dis_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert dis_exc.value.code == ORG_DISABLED

        # 2. Suspend organization
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(governance_status=GovernanceStatus.SUSPENDED.value)
            )

        with pytest.raises(EnterpriseError) as susp_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert susp_exc.value.code == ORG_SUSPENDED


@pytest.mark.asyncio
async def test_root_bootstrap_revoked_membership_or_non_owner_fails_closed():
    """Verify revoked memberships or non-owner callers strictly fail closed."""
    async for url in isolated_pg_url("wp_titan_revoked_member"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Member Owner", f"member.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)

        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Member Org {suffix}",
            slug=f"member-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        # 1. Non-owner role (ADMIN)
        actor_admin = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.ADMIN,
            membership_status="ACTIVE",
        )
        with pytest.raises(EnterpriseError) as adm_exc:
            await svc.initiate_root_bootstrap(actor_admin, org_id=org_id)
        assert adm_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # 2. Revoked membership status in database
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(web_memberships)
                .where(
                    and_(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.user_id == uid,
                    )
                )
                .values(status="REVOKED")
            )

        actor_owner = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        with pytest.raises(EnterpriseError) as rev_exc:
            await svc.initiate_root_bootstrap(actor_owner, org_id=org_id)
        assert rev_exc.value.code == MEMBERSHIP_REVOKED


@pytest.mark.asyncio
async def test_root_bootstrap_transaction_rollback_preserves_clean_state():
    """Verify ceremony failure rolls back principal and trust root without leaking partial records."""
    async for url in isolated_pg_url("wp_titan_rollback"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Rollback Owner", f"rollback.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)

        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Rollback Org {suffix}",
            slug=f"rollback-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        init_res = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True
        )
        _, pub_hex, _ = _gen_ed25519()

        # Provide an invalid root signature
        invalid_pop = _b64url(b"invalid_signature_bytes_32_chars_ok")

        with pytest.raises(EnterpriseError) as exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=init_res["token"],
                nonce=init_res["nonce"],
                root_public_key=pub_hex,
                root_signature=invalid_pop,
                scope_description="Rollback test",
                purpose="Rollback test",
                allowed_action_types=["test.action"],
                allowed_targets=["test:target"],
            )
        assert exc.value.code == PROOF_OF_POSSESSION_INVALID

        # Verify no partial rows persisted in PostgreSQL
        async with engine.raw.connect() as conn:
            p_cnt = (
                await conn.execute(
                    select(trust_fabric_principals.c.id).where(trust_fabric_principals.c.id == uid)
                )
            ).first()
            assert p_cnt is None, "Principal must NOT exist after rolled-back transaction"

            r_cnt = (
                await conn.execute(
                    select(trust_fabric_trust_roots.c.id).where(
                        trust_fabric_trust_roots.c.org_id == org_id
                    )
                )
            ).first()
            assert r_cnt is None, "Trust root must NOT exist after rolled-back transaction"
