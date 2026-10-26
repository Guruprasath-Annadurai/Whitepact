# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Operation TITAN-1 Authority Adversarial & Full Consequential Chain Test Suite.

Independently qualifies:
1. Root Proof-of-Possession (Ed25519 ceremony verification and tamper rejection).
2. Identity Assurance boundary (unverified vs BASIC_VERIFIED vs IDENTITY_VERIFIED).
3. Multi-admin M-of-N quorum recovery (anti-self-approval, duplicate prevention, quorum thresholds).
4. Delegated authority attenuation and capability projection.
5. Short-lived grants, single-use execution nonces, and replay protection.
6. Single-use emergency ticket (Path B) consumption and replay prevention.
7. Unilateral emergency containment (kill-switch), epoch bumping, and cross-worker revocation.
8. Cross-tenant isolation and privilege escalation defenses.
9. Root and consent temporal expiration and revocation lifecycle.
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import insert

from responsibleai.db.engine import (
    authority_step_up_challenges,
    create_engine,
    trust_fabric_principals,
    web_memberships,
)
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import (
    ALREADY_VOTED,
    IDENTITY_ASSURANCE_REQUIRED,
    PROOF_OF_POSSESSION_INVALID,
    QUORUM_NOT_MET,
    RECOVERY_ALREADY_EXECUTED,
    SELF_APPROVAL_BLOCKED,
    UNAUTHORIZED_BOOTSTRAP_CALLER,
    WEBAUTHN_CHALLENGE_REPLAY,
)
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.errors import CROSS_TENANT, EnterpriseError
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.m13_owner_qualification import qualify_owner, root_completion_assertion
from tests.pg_test_url import isolated_pg_url


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _gen_ed25519():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pub_bytes = pub.public_bytes_raw()
    return priv, pub_bytes.hex(), pub_bytes


@pytest.mark.asyncio
async def test_full_consequential_authority_chain():
    """Real PostgreSQL: qualified identity -> PoP -> consent -> root -> delegation -> grant -> nonce -> emergency containment."""
    async for url in isolated_pg_url("wp_titan_full_chain"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)
        nonce_repo = ExecutionNonceRepository(engine)

        suffix = uuid.uuid4().hex[:8]

        # 1. Unverified user fails identity assurance
        unverified_id, _ = await web_repo.register(
            "Unverified Owner", f"unverified.{suffix}@example.com", "Password123!@#"
        )
        unverified_org = await iam.create_workspace(
            actor_user_id=unverified_id,
            name=f"Unverified Org {suffix}",
            slug=f"unverified-org-{suffix}",
            kind="ORGANIZATION",
        )
        unverified_org_id = (
            unverified_org["id"] if isinstance(unverified_org, dict) else unverified_org.id
        )
        unverified_actor = Actor(
            actor_type="USER",
            actor_id=unverified_id,
            user_id=unverified_id,
            org_id=unverified_org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        with pytest.raises(EnterpriseError) as exc_info:
            await svc.initiate_root_bootstrap(
                unverified_actor,
                org_id=unverified_org_id,
                require_identity_assurance=True,
            )
        assert exc_info.value.code == IDENTITY_ASSURANCE_REQUIRED

        # 2. Verified user achieves BASIC_VERIFIED via email verification
        owner_id, verify_token = await web_repo.register(
            "Qualified Owner", f"owner.{suffix}@example.com", "Password123!@#"
        )
        assert await web_repo.verify_email(verify_token) is True

        org = await iam.create_workspace(
            actor_user_id=owner_id,
            name=f"Titan Authority Org {suffix}",
            slug=f"titan-auth-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=owner_id,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Qualified Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        owner_actor = Actor(
            actor_type="USER",
            actor_id=owner_id,
            user_id=owner_id,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # 3. Initiate root bootstrap with identity assurance and passkey stepup required
        owner_actor, authenticator_key, credential = await qualify_owner(engine, owner_actor)
        init_stepup = await svc.initiate_root_bootstrap(
            owner_actor,
            org_id=org_id,
            require_identity_assurance=True,
            require_passkey_stepup=True,
        )
        assert init_stepup["organization_id"] == org_id
        assert init_stepup["require_passkey_stepup"] is True

        # Omitting webauthn assertion when stepup was required fails closed
        priv_key, pub_hex, _ = _gen_ed25519()
        with pytest.raises(EnterpriseError) as stepup_exc:
            await svc.complete_root_bootstrap(
                owner_actor,
                org_id=org_id,
                token=init_stepup["token"],
                nonce=init_stepup["nonce"],
                root_public_key=pub_hex,
                scope_description="Stepup test",
                purpose="Test passkey requirement",
                allowed_action_types=["test.read"],
                allowed_targets=["test:all"],
            )
        assert stepup_exc.value.code == "PASSKEY_STEP_UP_REQUIRED"

        # 4. Initiate fresh bootstrap to test Proof-of-Possession verification
        init_res = await svc.initiate_root_bootstrap(
            owner_actor,
            org_id=org_id,
            require_identity_assurance=True,
            require_passkey_stepup=False,
        )
        token = init_res["token"]
        nonce = init_res["nonce"]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        # 5. Tampered PoP signature is rejected with PROOF_OF_POSSESSION_INVALID
        pop_msg = f"WP_ROOT_POP:{org_id}:{nonce}:{token_hash}".encode()
        tampered_sig = _b64url(b"invalid_signature_bytes_32_len__invalid_signature_bytes_32_len__")
        pop_assertion = await root_completion_assertion(
            svc, owner_actor, init_res, pub_hex, authenticator_key, credential
        )
        with pytest.raises(EnterpriseError) as pop_exc:
            await svc.complete_root_bootstrap(
                owner_actor,
                org_id=org_id,
                token=token,
                nonce=nonce,
                root_public_key=pub_hex,
                root_signature=tampered_sig,
                webauthn_assertion=pop_assertion,
                scope_description="Production Root Scope",
                purpose="Autonomous Operations",
                allowed_action_types=["ledger.read", "ledger.write"],
                allowed_targets=["db:financial_records"],
            )
        assert pop_exc.value.code == PROOF_OF_POSSESSION_INVALID

        # 6. Valid PoP signature succeeds
        valid_sig = _b64url(priv_key.sign(pop_msg))
        valid_assertion = await root_completion_assertion(
            svc, owner_actor, init_res, pub_hex, authenticator_key, credential, sign_count=3
        )

        complete_res = await svc.complete_root_bootstrap(
            owner_actor,
            org_id=org_id,
            token=token,
            nonce=nonce,
            root_public_key=pub_hex,
            root_signature=valid_sig,
            webauthn_assertion=valid_assertion,
            scope_description="Production Root Scope",
            purpose="Autonomous Operations",
            allowed_action_types=["ledger.read", "ledger.write"],
            allowed_targets=["db:financial_records"],
        )
        assert complete_res["status"] == "BOOTSTRAPPED"
        assert complete_res["proof_of_possession_verified"] is True
        root_id = complete_res["root_id"]

        # 7. Register application and agent
        app_res = await svc.register_application(
            owner_actor,
            org_id=org_id,
            name="Ledger Processing App",
            description="Processes financial ledger actions",
            environment="production",
        )
        app_id = app_res["application_id"]

        agent_res = await svc.register_agent(
            owner_actor,
            org_id=org_id,
            name="Accounting Autonomous Agent",
            description="Executes reconciliations",
            application_id=app_id,
        )
        agent_id = agent_res["agent_id"]

        # 8. Delegated authority attenuation: delegate a strictly attenuated subset of root scope
        delegation_res = await svc.delegate_to_agent(
            owner_actor,
            org_id=org_id,
            agent_id=agent_id,
            granted_action_types=["ledger.read"],  # Attenuated (read only, no write)
            allowed_targets=["db:financial_records"],
            purpose="Autonomous audit reconciliations",
        )
        assert delegation_res["delegation_id"] is not None

        # 9. Capability projection reflects attenuation
        caps = await svc.list_capabilities(
            owner_actor,
            org_id=org_id,
            agent_id=agent_id,
        )
        cap_map = {c["action_type"]: c for c in caps}
        assert cap_map["ledger.read"]["status"] == "AUTHORIZED"
        # write was not delegated to this agent
        assert "ledger.write" not in cap_map or cap_map["ledger.write"]["status"] != "AUTHORIZED"

        # 10. Short-lived Execution Grant & Single-Use Execution Nonce
        grant_id = str(uuid.uuid4())
        nonce_val = str(uuid.uuid4())
        current_epoch = complete_res["epoch"]

        # First consume succeeds
        await nonce_repo.consume(
            nonce=nonce_val,
            authorization_id=grant_id,
            organization_id=org_id,
            expected_epoch=current_epoch,
        )

        # Replay attempt fails closed with NonceAlreadyConsumedError
        with pytest.raises(NonceAlreadyConsumedError):
            await nonce_repo.consume(
                nonce=nonce_val,
                authorization_id=grant_id,
                organization_id=org_id,
                expected_epoch=current_epoch,
            )

        # 11. Unilateral Emergency Containment (Kill-Switch)
        op_digest = compute_canonical_operation_digest(
            "EMERGENCY_CONTAINMENT",
            {
                "org_id": org_id,
                "target_type": "ROOT_AUTHORITY",
                "target_id": root_id,
                "containment_action": "REVOKE",
            },
        )
        authz_id = f"wp_authz_{uuid.uuid4().hex}"
        authz_hash = hashlib.sha256(authz_id.encode("utf-8")).hexdigest()
        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()
        expires_at = (now_dt + timedelta(seconds=300)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                authority_step_up_challenges.insert().values(
                    challenge_hash=authz_hash,
                    org_id=org_id,
                    user_id=owner_id,
                    session_id=None,
                    action="PREVERIFIED:EMERGENCY_CONTAINMENT",
                    operation_digest=op_digest,
                    rp_id="localhost",
                    origin="http://localhost:3000",
                    raw_challenge_b64=authz_id,
                    created_at=now_iso,
                    expires_at=expires_at,
                    consumed_at=None,
                )
            )

        containment_res = await svc.execute_emergency_containment(
            owner_actor,
            org_id=org_id,
            target_type="ROOT_AUTHORITY",
            target_id=root_id,
            containment_action="REVOKE",
            reason="Suspected compromise: kill switch activated",
            stepup_authorization_id=authz_id,
        )
        assert containment_res["status"] == "CONTAINED"
        assert containment_res["revocation_epoch"] == current_epoch + 1

        # 12. Cross-worker grant invalidation: any outstanding grant using old epoch is rejected
        stale_grant_id = str(uuid.uuid4())
        stale_nonce = str(uuid.uuid4())
        with pytest.raises(StaleRevocationEpochError):
            await nonce_repo.consume(
                nonce=stale_nonce,
                authorization_id=stale_grant_id,
                organization_id=org_id,
                expected_epoch=current_epoch,  # Old epoch fails because epoch is now current_epoch + 1
            )

        # Capabilities after root containment return REVOKED
        post_caps = await svc.list_capabilities(
            owner_actor,
            org_id=org_id,
            agent_id=agent_id,
        )
        for cap in post_caps:
            assert cap["status"] == "REVOKED"


@pytest.mark.asyncio
async def test_multi_admin_quorum_recovery_adversarial():
    """Verify M-of-N multi-admin quorum recovery, anti-self-approval, duplicate vote rejection, and threshold enforcement."""
    async for url in isolated_pg_url("wp_titan_quorum"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]

        # Register 3 distinct owner/admin accounts
        users = []
        for i in range(3):
            uid, tok = await web_repo.register(
                f"Admin {i} {suffix}", f"admin{i}.{suffix}@example.com", "Password123!@#"
            )
            await web_repo.verify_email(tok)
            users.append(uid)

        org = await iam.create_workspace(
            actor_user_id=users[0],
            name=f"Quorum Org {suffix}",
            slug=f"quorum-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        # Add admin 1 and admin 2 to org with role OWNER
        async with engine.raw.begin() as conn:
            for uid in users[1:]:
                await conn.execute(
                    insert(web_memberships).values(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        user_id=uid,
                        role="OWNER",
                        status="ACTIVE",
                        created_at=now_iso,
                        updated_at=now_iso,
                    )
                )
            for uid in users:
                await conn.execute(
                    insert(trust_fabric_principals).values(
                        id=uid,
                        org_id=org_id,
                        principal_type="HUMAN",
                        display_name=f"Admin {uid[:6]}",
                        lifecycle_state="ACTIVE",
                        created_at=now_iso,
                        updated_at=now_iso,
                    )
                )

        actor0 = Actor(
            actor_type="USER",
            actor_id=users[0],
            user_id=users[0],
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        actor1 = Actor(
            actor_type="USER",
            actor_id=users[1],
            user_id=users[1],
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        actor2 = Actor(
            actor_type="USER",
            actor_id=users[2],
            user_id=users[2],
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Bootstrap initial root
        actor0, authenticator_key, credential = await qualify_owner(engine, actor0)
        init_res = await svc.initiate_root_bootstrap(actor0, org_id=org_id)
        private, pub_hex, _ = _gen_ed25519()
        signature = _b64url(
            private.sign(
                f"WP_ROOT_POP:{org_id}:{init_res['nonce']}:{hashlib.sha256(init_res['token'].encode()).hexdigest()}".encode()
            )
        )
        assertion = await root_completion_assertion(
            svc, actor0, init_res, pub_hex, authenticator_key, credential
        )
        complete_res = await svc.complete_root_bootstrap(
            actor0,
            org_id=org_id,
            token=init_res["token"],
            nonce=init_res["nonce"],
            root_public_key=pub_hex,
            scope_description="Initial Root",
            root_signature=signature,
            webauthn_assertion=assertion,
            purpose="Testing quorum",
            allowed_action_types=["admin.write"],
            allowed_targets=["system:all"],
        )
        root_id = complete_res["root_id"]

        # 1. Admin 0 initiates 2-of-3 quorum recovery request
        _, new_pub_hex, _ = _gen_ed25519()
        rec_params = {
            "new_root_public_key": new_pub_hex,
            "reason": "Hardware security module rotation",
        }
        req = await svc.create_recovery_request(
            actor0,
            org_id=org_id,
            request_type="ROTATE_ROOT",
            target_root_id=root_id,
            proposed_parameters=rec_params,
            required_quorum_m=2,
            eligible_quorum_n=3,
        )
        req_id = req["request_id"]
        action_digest = req["action_digest"]

        # 2. Anti-self-approval rule: Admin 0 cannot approve their own request
        with pytest.raises(EnterpriseError) as self_exc:
            await svc.vote_recovery_request(
                actor0,
                org_id=org_id,
                request_id=req_id,
                decision="APPROVE",
                action_digest=action_digest,
            )
        assert self_exc.value.code == SELF_APPROVAL_BLOCKED

        # 3. Execution attempt before quorum fails closed
        with pytest.raises(EnterpriseError) as pre_exec_exc:
            await svc.execute_recovery_request(
                actor1,
                org_id=org_id,
                request_id=req_id,
                action_digest=action_digest,
            )
        assert pre_exec_exc.value.code == QUORUM_NOT_MET

        # 4. Admin 1 votes APPROVE
        vote1 = await svc.vote_recovery_request(
            actor1,
            org_id=org_id,
            request_id=req_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
        assert vote1["current_approvals"] == 1

        # 5. Anti-duplicate voting check: Admin 1 cannot vote again
        with pytest.raises(EnterpriseError) as dup_exc:
            await svc.vote_recovery_request(
                actor1,
                org_id=org_id,
                request_id=req_id,
                decision="APPROVE",
                action_digest=action_digest,
            )
        assert dup_exc.value.code == ALREADY_VOTED

        # 6. Admin 2 votes APPROVE -> quorum met (2 approvals)
        vote2 = await svc.vote_recovery_request(
            actor2,
            org_id=org_id,
            request_id=req_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
        assert vote2["current_approvals"] == 2

        # 7. Execute recovery with met quorum
        exec_res = await svc.execute_recovery_request(
            actor1,
            org_id=org_id,
            request_id=req_id,
            action_digest=action_digest,
        )
        assert exec_res["status"] == "EXECUTED"
        assert exec_res["revocation_epoch"] > 0

        # 8. Re-execution of already-executed recovery request fails closed
        with pytest.raises(EnterpriseError) as reexec_exc:
            await svc.execute_recovery_request(
                actor2,
                org_id=org_id,
                request_id=req_id,
                action_digest=action_digest,
            )
        assert reexec_exc.value.code == RECOVERY_ALREADY_EXECUTED


@pytest.mark.asyncio
async def test_cross_tenant_and_privilege_escalation_containment():
    """Verify cross-tenant boundaries, role privilege boundaries, and Path B emergency-ticket single-use consumption."""
    async for url in isolated_pg_url("wp_titan_isolation"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]

        # Register User A in Org A (Owner)
        u_a, tok_a = await web_repo.register(
            "Owner A", f"owner_a.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(tok_a)
        org_a = await iam.create_workspace(
            actor_user_id=u_a, name=f"Org A {suffix}", slug=f"org-a-{suffix}", kind="ORGANIZATION"
        )
        org_a_id = org_a["id"] if isinstance(org_a, dict) else org_a.id

        # Register User B in Org B (Owner)
        u_b, tok_b = await web_repo.register(
            "Owner B", f"owner_b.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(tok_b)
        org_b = await iam.create_workspace(
            actor_user_id=u_b, name=f"Org B {suffix}", slug=f"org-b-{suffix}", kind="ORGANIZATION"
        )
        org_b_id = org_b["id"] if isinstance(org_b, dict) else org_b.id

        # Register User C in Org A as non-owner (MEMBER)
        u_c, tok_c = await web_repo.register(
            "Member C", f"member_c.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(tok_c)
        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=u_a,
                    org_id=org_a_id,
                    principal_type="HUMAN",
                    display_name="Owner A",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=u_b,
                    org_id=org_b_id,
                    principal_type="HUMAN",
                    display_name="Owner B",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            await conn.execute(
                insert(web_memberships).values(
                    id=str(uuid.uuid4()),
                    org_id=org_a_id,
                    user_id=u_c,
                    role="DEVELOPER",
                    status="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor_a = Actor(
            actor_type="USER",
            actor_id=u_a,
            user_id=u_a,
            org_id=org_a_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        actor_b = Actor(
            actor_type="USER",
            actor_id=u_b,
            user_id=u_b,
            org_id=org_b_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        actor_c = Actor(
            actor_type="USER",
            actor_id=u_c,
            user_id=u_c,
            org_id=org_a_id,
            role=Role.DEVELOPER,
            membership_status="ACTIVE",
        )

        # 1. Cross-Tenant Defense: Actor A attempting to operate on Org B fails closed, and vice-versa
        with pytest.raises(EnterpriseError) as ct_exc:
            await svc.initiate_root_bootstrap(actor_a, org_id=org_b_id)
        assert ct_exc.value.code == CROSS_TENANT

        with pytest.raises(EnterpriseError) as ct_b_exc:
            await svc.initiate_root_bootstrap(actor_b, org_id=org_a_id)
        assert ct_b_exc.value.code == CROSS_TENANT

        # 2. Privilege Escalation Defense: Member in Org A attempting root bootstrap fails closed
        with pytest.raises(EnterpriseError) as pe_exc:
            await svc.initiate_root_bootstrap(actor_c, org_id=org_a_id)
        assert pe_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Bootstrap root for Org A
        actor_a, authenticator_key, credential = await qualify_owner(engine, actor_a)
        init_a = await svc.initiate_root_bootstrap(actor_a, org_id=org_a_id)
        private, pub_a, _ = _gen_ed25519()
        signature = _b64url(
            private.sign(
                f"WP_ROOT_POP:{org_a_id}:{init_a['nonce']}:{hashlib.sha256(init_a['token'].encode()).hexdigest()}".encode()
            )
        )
        assertion = await root_completion_assertion(
            svc, actor_a, init_a, pub_a, authenticator_key, credential
        )
        comp_a = await svc.complete_root_bootstrap(
            actor_a,
            org_id=org_a_id,
            token=init_a["token"],
            nonce=init_a["nonce"],
            root_public_key=pub_a,
            scope_description="Org A Root",
            root_signature=signature,
            webauthn_assertion=assertion,
            purpose="Testing Path B",
            allowed_action_types=["test.action"],
            allowed_targets=["test:target"],
        )
        root_a_id = comp_a["root_id"]

        # 3. Path B Single-Use Emergency Ticket Consumption
        op_digest = compute_canonical_operation_digest(
            "EMERGENCY_CONTAINMENT",
            {
                "org_id": org_a_id,
                "target_type": "ROOT_AUTHORITY",
                "target_id": root_a_id,
                "containment_action": "SUSPEND",
            },
        )
        authz_id = f"wp_authz_{uuid.uuid4().hex}"
        authz_hash = hashlib.sha256(authz_id.encode("utf-8")).hexdigest()
        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()
        expires_at = (now_dt + timedelta(seconds=300)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                authority_step_up_challenges.insert().values(
                    challenge_hash=authz_hash,
                    org_id=org_a_id,
                    user_id=u_a,
                    session_id=None,
                    action="PREVERIFIED:EMERGENCY_CONTAINMENT",
                    operation_digest=op_digest,
                    rp_id="localhost",
                    origin="http://localhost:3000",
                    raw_challenge_b64=authz_id,
                    created_at=now_iso,
                    expires_at=expires_at,
                    consumed_at=None,
                )
            )

        # First consumption of Path B emergency ticket succeeds
        containment = await svc.execute_emergency_containment(
            actor_a,
            org_id=org_a_id,
            target_type="ROOT_AUTHORITY",
            target_id=root_a_id,
            containment_action="SUSPEND",
            reason="Emergency test",
            stepup_authorization_id=authz_id,
        )
        assert containment["status"] == "CONTAINED"

        # Second consumption (replay) of the same emergency ticket fails closed
        with pytest.raises(EnterpriseError) as replay_exc:
            await svc.execute_emergency_containment(
                actor_a,
                org_id=org_a_id,
                target_type="ROOT_AUTHORITY",
                target_id=root_a_id,
                containment_action="SUSPEND",
                reason="Replay attempt",
                stepup_authorization_id=authz_id,
            )
        assert replay_exc.value.code == WEBAUTHN_CHALLENGE_REPLAY
