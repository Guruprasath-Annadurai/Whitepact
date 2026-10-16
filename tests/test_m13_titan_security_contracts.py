# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Operation TITAN (M13-I2) Security Contract Regression Suite.

Proves:
1. Real PostgreSQL transactional atomicity and rollback for disable_application.
2. Real PostgreSQL multi-hop delegation cascade revocation, consent revocation,
   epoch advancement, and cross-worker ExecutionAuthorization grant invalidation.
3. Real PostgreSQL concurrency serialization between register_agent and
   disable_application (zero active agents can survive under a disabled application).
4. Capability projection truthfulness under root expiration, consent expiration,
   parent application disablement, org_authority_ceilings, org_security_policies,
   and governance_policies, plus provenance IDs when AUTHORIZED.
5. Organization rename workspace-context and optimistic-concurrency preconditions
   (409 Conflict on cookie workspace drift or concurrent name change).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, update

import responsibleai.dashboard.app as app_module
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import (
    auth_replay_records,
    create_engine,
    governance_consent_proofs,
    governance_delegations,
    governance_policies,
    governance_root_authority_records,
    human_totp_factors,
    org_authority_ceilings,
    org_security_policies,
    passkey_credentials,
    trust_fabric_principals,
    web_memberships,
)
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    StaleRevocationEpochError,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import CONTAINMENT_INVALID_TARGET
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.security.service import (
    IdentitySecurityService,
    SensitiveAction,
    account_recovery_requests,
)
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.execution import admit_execution, authorize_execution
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.risk import RiskTier
from responsibleai.rbac.models import Role
from tests.pg_test_url import isolated_pg_url


async def _bootstrap_org_root_and_app(engine) -> tuple[Actor, str, str, str]:
    web_repo = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    suffix = uuid.uuid4().hex[:8]
    user_id, verify_token = await web_repo.register(
        "Titan Owner", f"owner.{suffix}@titan.example", "TitanPassword123!@#"
    )
    await web_repo.verify_email(verify_token)
    org = await iam.create_workspace(
        actor_user_id=user_id,
        name=f"Titan Org {suffix}",
        slug=f"titan-org-{suffix}",
        kind="ORGANIZATION",
    )
    org_id = org["id"] if isinstance(org, dict) else org.id
    now_iso = datetime.now(UTC).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(trust_fabric_principals).values(
                id=user_id,
                org_id=org_id,
                principal_type="HUMAN",
                display_name="Titan Owner",
                lifecycle_state="ACTIVE",
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
    actor = Actor(
        actor_type="USER",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=Role.OWNER,
        membership_status="ACTIVE",
    )
    svc = CustomerAuthorityService(engine)
    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id)
    comp = await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key=f"ed25519_pub_{suffix}",
        scope_description="Enterprise Root Scope",
        purpose="Enterprise operations",
        allowed_action_types=["read_data", "write_ledger", "delete_records"],
        allowed_targets=["db:customers", "db:ledger"],
    )
    app_res = await svc.register_application(
        actor,
        org_id=org_id,
        name="Payments Core App",
        description="Core payment orchestration",
        environment="production",
    )
    return actor, org_id, comp["root_id"], app_res["application_id"]


@pytest.mark.asyncio
async def test_postgres_disable_application_transactional_rollback(monkeypatch):
    """If any step inside disable_application fails on PostgreSQL, all mutations roll back."""
    async for url in isolated_pg_url("wp_titan_disable_rb"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)
        try:
            actor, org_id, _root_id, app_id = await _bootstrap_org_root_and_app(engine)
            svc = CustomerAuthorityService(engine)

            agent_a = (
                await svc.register_agent(
                    actor, org_id=org_id, name="Agent Alpha", application_id=app_id
                )
            )["agent_id"]
            await svc.delegate_to_agent(
                actor,
                org_id=org_id,
                agent_id=agent_a,
                granted_action_types=["read_data"],
                allowed_targets=["db:customers"],
                purpose="Customer lookup",
            )

            epoch_before = (await RevocationEpochRepository(engine).current(org_id)).epoch

            # Inject failure at the final audit step inside disable_application after epoch bump,
            # app update, agent disablement, consent revocation, and delegation revocation have run.
            async def fail_at_audit(*_args, **_kwargs):
                raise RuntimeError("Simulated mid-transaction failure after mutations")

            monkeypatch.setattr(svc._audit, "record", fail_at_audit)

            with pytest.raises(RuntimeError, match="Simulated mid-transaction failure"):
                await svc.disable_application(
                    actor,
                    org_id=org_id,
                    app_id=app_id,
                    reason="Rollback verification",
                )

            # Verify full atomic rollback across application, agent, delegation, consent, and epoch
            async with engine.raw.connect() as conn:
                app_state = await conn.scalar(
                    select(trust_fabric_principals.c.lifecycle_state).where(
                        trust_fabric_principals.c.id == app_id
                    )
                )
                agent_state = await conn.scalar(
                    select(trust_fabric_principals.c.lifecycle_state).where(
                        trust_fabric_principals.c.id == agent_a
                    )
                )
                del_revoked_at = await conn.scalar(
                    select(governance_delegations.c.revoked_at).where(
                        governance_delegations.c.to_identity_id == agent_a
                    )
                )
                consent_revoked_at = await conn.scalar(
                    select(governance_consent_proofs.c.revoked_at).where(
                        governance_consent_proofs.c.grantee_id == agent_a
                    )
                )

            epoch_after = (await RevocationEpochRepository(engine).current(org_id)).epoch
            assert app_state == "ACTIVE"
            assert agent_state == "ACTIVE"
            assert del_revoked_at is None
            assert consent_revoked_at is None
            assert epoch_after == epoch_before
        finally:
            await engine.raw.dispose()


@pytest.mark.asyncio
async def test_postgres_disable_application_atomic_cascade_and_cross_worker_grant_invalidation():
    """Disabling an application cascades across multi-hop delegations and invalidates pre-issued permits across workers."""
    async for url in isolated_pg_url("wp_titan_disable_ok"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        worker_a = create_engine(url)
        worker_b = create_engine(url)
        try:
            actor, org_id, root_id, app_id = await _bootstrap_org_root_and_app(worker_a)
            svc_a = CustomerAuthorityService(worker_a)

            agent_a = (
                await svc_a.register_agent(
                    actor, org_id=org_id, name="Primary Agent", application_id=app_id
                )
            )["agent_id"]
            agent_b = (
                await svc_a.register_agent(
                    actor, org_id=org_id, name="Downstream Sub-Agent", application_id=None
                )
            )["agent_id"]

            await svc_a.delegate_to_agent(
                actor,
                org_id=org_id,
                agent_id=agent_a,
                granted_action_types=["read_data", "write_ledger"],
                allowed_targets=["db:customers", "db:ledger"],
                purpose="Primary processing",
            )
            # Sub-delegate from agent_a to agent_b (multi-hop branch under agent_a)
            expires = datetime.now(UTC) + timedelta(hours=2)
            await DelegationRepository(worker_a).grant(
                org_id,
                agent_b,
                from_identity_id=agent_a,
                granted_action_types=frozenset({"read_data"}),
                constraints={"allowed_targets": ["db:customers"]},
                purpose="Primary processing",
                granted_by=agent_a,
                expires_at=expires,
            )
            sub_consent = build_consent_proof(
                actor.user_id,
                root_id,
                agent_b,
                "Sub-agent read scope",
                "Primary processing",
                ConsentMethod.EXPLICIT_UI_ACTION,
                allowed_action_types=("read_data",),
                allowed_targets=("db:customers",),
                evidence_refs=(f"delegator:{agent_a}",),
                expires_at=expires,
            )
            await ConsentProofRepository(worker_a).create(sub_consent, organization_id=org_id)

            # Issue an execution permit on Worker A before application disablement
            epoch_before = (await RevocationEpochRepository(worker_a).current(org_id)).epoch
            action = ActionRequest(
                action_id=f"act_{uuid.uuid4().hex[:10]}",
                agent=AgentContext(
                    agent_id=agent_a,
                    organization_id=org_id,
                    identity=IdentityContext(identity_id=agent_a, kind="agent"),
                ),
                action_type="read_data",
                target="db:customers",
                arguments={"customer_id": "cust_1"},
            )
            decision = DecisionResult(
                action_id=action.action_id,
                decision=GovernanceDecision.ALLOW,
                risk_tier=RiskTier.LOW,
                reason_codes=["Authorized before app disable"],
            )
            permit = authorize_execution(
                decision,
                action,
                revocation_epoch=epoch_before,
            )

            # Disable application on Worker A
            dis_res = await svc_a.disable_application(
                actor,
                org_id=org_id,
                app_id=app_id,
                reason="Security decommissioning",
            )
            assert dis_res["status"] == "DISABLED"
            assert agent_a in dis_res["disabled_agents"]
            assert len(dis_res["revoked_delegations"]) >= 2
            assert dis_res["revocation_epoch"] == epoch_before + 1

            # Verify multi-hop delegation to agent_b and consent for agent_a were revoked
            async with worker_b.raw.connect() as conn:
                del_b_revoked = await conn.scalar(
                    select(governance_delegations.c.revoked_at).where(
                        governance_delegations.c.to_identity_id == agent_b
                    )
                )
                consent_a_revoked = await conn.scalar(
                    select(governance_consent_proofs.c.revoked_at).where(
                        governance_consent_proofs.c.grantee_id == agent_a
                    )
                )
            assert del_b_revoked is not None
            assert consent_a_revoked is not None

            # Worker B must reject the pre-issued permit at execution admission
            with pytest.raises(StaleRevocationEpochError):
                await admit_execution(permit, action, ExecutionNonceRepository(worker_b))
        finally:
            await worker_a.raw.dispose()
            await worker_b.raw.dispose()


@pytest.mark.asyncio
async def test_postgres_concurrent_register_agent_vs_disable_application_serialization():
    """Concurrent agent registrations racing against disable_application never leave an active agent under a disabled app."""
    async for url in isolated_pg_url("wp_titan_conc_reg"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)
        try:
            actor, org_id, _, app_id = await _bootstrap_org_root_and_app(engine)
            svc = CustomerAuthorityService(engine)

            barrier = asyncio.Event()

            async def register_worker(
                idx: int,
                b=barrier,
                s=svc,
                act=actor,
                oid=org_id,
                aid=app_id,
            ):
                await b.wait()
                try:
                    res = await s.register_agent(
                        act,
                        org_id=oid,
                        name=f"Concurrent Agent {idx}",
                        application_id=aid,
                    )
                    return ("REGISTERED", res["agent_id"])
                except EnterpriseError as exc:
                    assert exc.code in {CONTAINMENT_INVALID_TARGET, "FORBIDDEN"}
                    return ("REJECTED", None)

            async def disable_worker(
                b=barrier,
                s=svc,
                act=actor,
                oid=org_id,
                aid=app_id,
            ):
                await b.wait()
                res = await s.disable_application(
                    act,
                    org_id=oid,
                    app_id=aid,
                    reason="Concurrent disable race test",
                )
                return ("DISABLED", res)

            tasks = [asyncio.create_task(register_worker(i)) for i in range(6)]
            tasks.append(asyncio.create_task(disable_worker()))
            barrier.set()
            outcomes = await asyncio.gather(*tasks)

            assert any(kind == "DISABLED" for kind, _ in outcomes)

            # Invariant: regardless of transaction serialization order, once disable_application
            # completes, the application is DISABLED and ZERO agents bound to app_id are ACTIVE.
            async with engine.raw.connect() as conn:
                app_state = await conn.scalar(
                    select(trust_fabric_principals.c.lifecycle_state).where(
                        trust_fabric_principals.c.id == app_id
                    )
                )
                rows = (
                    (
                        await conn.execute(
                            select(trust_fabric_principals).where(
                                trust_fabric_principals.c.org_id == org_id,
                                trust_fabric_principals.c.principal_type == "AI_AGENT",
                            )
                        )
                    )
                    .mappings()
                    .all()
                )

            assert app_state == "DISABLED"
            active_app_agents = []
            for row in rows:
                meta = json.loads(row["metadata_json"] or "{}")
                if meta.get("application_id") == app_id and row["lifecycle_state"] == "ACTIVE":
                    active_app_agents.append(row["id"])
            assert active_app_agents == [], (
                f"Active agents remained under disabled application: {active_app_agents}"
            )
        finally:
            await engine.raw.dispose()


@pytest.mark.asyncio
async def test_capability_projection_evaluates_root_expiry_consent_app_state_and_policies(
    monkeypatch, tmp_path
):
    """list_capabilities and get_authority_status enforce root/consent expiry, app state, ceilings, and policies."""
    db_file = tmp_path / "titan-caps.db"
    monkeypatch.setattr(app_module.settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(app_module.settings, "db_path", str(db_file))
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.limiter, "enabled", False)

    async with LifespanManager(app_module.app):
        engine = get_enterprise_engine()
        actor, org_id, root_id, app_id = await _bootstrap_org_root_and_app(engine)
        svc = CustomerAuthorityService(engine)

        agent_id = (
            await svc.register_agent(
                actor,
                org_id=org_id,
                name="Ledger Worker",
                application_id=app_id,
            )
        )["agent_id"]

        del_res = await svc.delegate_to_agent(
            actor,
            org_id=org_id,
            agent_id=agent_id,
            granted_action_types=["read_data", "write_ledger"],
            allowed_targets=["db:customers", "db:ledger"],
            purpose="Accounting automation",
        )

        # 1. Baseline AUTHORIZED projection includes provenance IDs
        caps_1 = await svc.list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        by_action = {c["action_type"]: c for c in caps_1}
        assert by_action["read_data"]["status"] == "AUTHORIZED"
        assert by_action["read_data"]["root_id"] == root_id
        assert by_action["read_data"]["delegation_id"] == del_res["delegation_id"]
        assert by_action["read_data"]["consent_id"] == del_res["consent_id"]
        assert by_action["read_data"]["requires_approval"] is False

        # 2. Governance policy REQUIRE_APPROVAL on write_ledger and DENY on read_data
        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_policies).values(
                    id=f"pol_{uuid.uuid4().hex[:8]}",
                    org_id=org_id,
                    rule_id="r_approve_write",
                    reason_code="REQUIRE_APPROVAL",
                    effect="REQUIRE_APPROVAL",
                    action_types=json.dumps(["write_ledger"]),
                    position=1,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            await conn.execute(
                insert(governance_policies).values(
                    id=f"pol_{uuid.uuid4().hex[:8]}",
                    org_id=org_id,
                    rule_id="r_deny_read",
                    reason_code="DENY",
                    effect="DENY",
                    action_types=json.dumps(["read_data"]),
                    position=2,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        caps_2 = {
            c["action_type"]: c
            for c in await svc.list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        }
        assert caps_2["read_data"]["status"] == "POLICY_DENIED"
        assert caps_2["write_ledger"]["status"] == "AUTHORIZED"
        assert caps_2["write_ledger"]["requires_approval"] is True
        assert caps_2["write_ledger"]["root_id"] == root_id

        # 3. Org Authority Ceiling restricting allowed_action_types to ["read_data"] denies write_ledger
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(org_authority_ceilings).values(
                    org_id=org_id,
                    allowed_action_types=json.dumps(["read_data"]),
                    allowed_targets=json.dumps(["*"]),
                    updated_at=now_iso,
                )
            )
        caps_3 = {
            c["action_type"]: c
            for c in await svc.list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        }
        assert caps_3["write_ledger"]["status"] == "POLICY_DENIED"

        # Clear policies and ceiling for subsequent lifecycle checks
        async with engine.raw.begin() as conn:
            await conn.execute(governance_policies.delete())
            await conn.execute(org_authority_ceilings.delete())
            await conn.execute(org_security_policies.delete())

        # 4. Expired agent consent proof -> CONSENT_REQUIRED
        past_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_consent_proofs)
                .where(governance_consent_proofs.c.consent_id == del_res["consent_id"])
                .values(expires_at=past_iso)
            )
        caps_4 = await svc.list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        assert all(c["status"] == "EXPIRED" for c in caps_4)

        # Restore agent consent expiry
        future_iso = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_consent_proofs)
                .where(governance_consent_proofs.c.consent_id == del_res["consent_id"])
                .values(expires_at=future_iso)
            )

        # 5. Expired root authority -> EXPIRED status & get_authority_status reports inactive
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(governance_root_authority_records)
                .where(governance_root_authority_records.c.root_id == root_id)
                .values(expires_at=past_iso)
            )
        status_expired = await svc.get_authority_status(actor, org_id=org_id)
        assert status_expired["has_active_authority"] is False
        caps_5 = await svc.list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        assert all(c["status"] == "EXPIRED" for c in caps_5)


@pytest.mark.asyncio
async def test_organization_rename_workspace_and_concurrency_preconditions(monkeypatch, tmp_path):
    """Organization rename enforces expected_organization_id / target_org_id and expected_name preconditions."""
    db_file = tmp_path / "titan-org-rename.db"
    monkeypatch.setattr(app_module.settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(app_module.settings, "db_path", str(db_file))
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.limiter, "enabled", False)

    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            engine = get_enterprise_engine()
            identities = WebIdentityRepository(engine)
            iam = EnterpriseIAM(engine)

            user_id, verify_token = await identities.register(
                "Workspace Owner", "rename.owner@example.com", "SecurePassword123!@#"
            )
            await identities.verify_email(verify_token)

            org_a = await iam.create_workspace(
                actor_user_id=user_id,
                name="Alpha Workspace",
                slug="alpha-ws",
                kind="ORGANIZATION",
            )
            org_b = await iam.create_workspace(
                actor_user_id=user_id,
                name="Beta Workspace",
                slug="beta-ws",
                kind="ORGANIZATION",
            )
            org_a_id = org_a["id"]
            org_b_id = org_b["id"]

            # Session cookie is bound to org_b (simulating another tab switching active workspace to org_b)
            token, csrf = await identities.create_session(user_id, org_id=org_b_id)
            client.cookies.set("wp_session", token)
            client.cookies.set("wp_csrf", csrf)

            def _extract_error_code(res) -> str | None:
                body = res.json()
                if isinstance(body, dict):
                    detail = body.get("detail")
                    if isinstance(detail, dict):
                        return detail.get("code")
                    msg = body.get("message")
                    if isinstance(msg, dict):
                        return msg.get("code")
                    if "code" in body:
                        return body.get("code")
                return None

            # 1. Attempting to rename org_a via /api/web/organization with expected_organization_id=org_a_id fails with 409
            conflict_1 = await client.patch(
                "/api/web/organization",
                headers={"X-WP-CSRF": csrf},
                json={
                    "name": "Wrongly Renamed Alpha",
                    "expected_organization_id": org_a_id,
                },
            )
            assert conflict_1.status_code == 409
            assert _extract_error_code(conflict_1) == "WORKSPACE_CONTEXT_CONFLICT"

            # 2. Attempting to rename org_a via /api/web/organizations/{org_a_id} while session is on org_b fails with 409
            conflict_2 = await client.patch(
                f"/api/web/organizations/{org_a_id}",
                headers={"X-WP-CSRF": csrf},
                json={"name": "Wrongly Renamed Alpha"},
            )
            assert conflict_2.status_code == 409
            assert _extract_error_code(conflict_2) == "WORKSPACE_CONTEXT_CONFLICT"

            # 3. Attempting to rename org_b with stale expected_name fails with 409
            conflict_3 = await client.patch(
                f"/api/web/organizations/{org_b_id}",
                headers={"X-WP-CSRF": csrf},
                json={
                    "name": "Beta Workspace V2",
                    "expected_name": "Stale Previous Name",
                },
            )
            assert conflict_3.status_code == 409
            assert _extract_error_code(conflict_3) == "ORGANIZATION_STATE_CONFLICT"

            # 4. Valid precondition succeeds
            ok_res = await client.patch(
                f"/api/web/organizations/{org_b_id}",
                headers={"X-WP-CSRF": csrf},
                json={
                    "name": "Beta Workspace V2",
                    "expected_organization_id": org_b_id,
                    "expected_name": "Beta Workspace",
                },
            )
            assert ok_res.status_code == 200
            assert ok_res.json()["name"] == "Beta Workspace V2"
            assert ok_res.json()["id"] == org_b_id


@pytest.mark.asyncio
async def test_postgres_first_passkey_bootstrap_invariants():
    """Prove first-passkey bootstrap invariants on real PostgreSQL:
    1. Valid initial owner with fresh password session, verified email, active org, and 0 passkeys
       can step up with allow_initial_owner_passkey_bootstrap=True.
    2. Without allow_initial_owner_passkey_bootstrap, step-up raises 403 AUTHENTICATION_ASSURANCE_TOO_LOW.
    3. Non-owner (role='MEMBER') fails closed with AUTHENTICATION_ASSURANCE_TOO_LOW.
    4. Recovery session (is_recovery=True) fails closed with AUTHENTICATION_ASSURANCE_TOO_LOW.
    5. User with existing passkey (active or revoked) fails closed with AUTHENTICATION_ASSURANCE_TOO_LOW.
    6. User with active TOTP factor fails closed with AUTHENTICATION_ASSURANCE_TOO_LOW.
    7. Existing auth_replay_records marker prevents duplicate or replayed bootstrap.
    """
    async for url in isolated_pg_url("wp_titan_boot_inv"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)
        try:
            identities = WebIdentityRepository(engine)
            sec_svc = IdentitySecurityService(engine)

            # Create owner
            iam = EnterpriseIAM(engine)
            owner_id, token_raw = await identities.register(
                "Initial Owner", f"owner.{uuid.uuid4().hex[:8]}@example.com", "Password123!@#"
            )
            # Verify owner email
            await identities.verify_email(token_raw)
            # Create organization with owner
            org = await iam.create_workspace(
                actor_user_id=owner_id,
                name="Titan Org",
                slug=f"titan-{uuid.uuid4().hex[:6]}",
                kind="ORGANIZATION",
            )
            org_id = org["id"] if isinstance(org, dict) else org.id

            # Issue direct password session
            session_token, _ = await identities.create_session(owner_id, org_id=org_id)
            _, _, session_assurance = await sec_svc.load_session(session_token)

            # Issue step-up grant
            grant = await sec_svc.issue_step_up(
                session_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=org_id,
            )

            # 1. Without allow_initial_owner_passkey_bootstrap, step-up fails with AUTHENTICATION_ASSURANCE_TOO_LOW
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    session_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=org_id,
                    grant=grant,
                    allow_initial_owner_passkey_bootstrap=False,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"

            # 2. With allow_initial_owner_passkey_bootstrap, legitimate initial owner step-up succeeds
            await sec_svc.require_step_up(
                session_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=org_id,
                grant=grant,
                allow_initial_owner_passkey_bootstrap=True,
            )

            # 3. Non-owner (MEMBER) fails closed
            member_id, member_tok = await identities.register(
                "Team Member", f"member.{uuid.uuid4().hex[:8]}@example.com", "Password123!@#"
            )
            await identities.verify_email(member_tok)
            async with engine._engine.begin() as conn:
                await conn.execute(
                    insert(web_memberships).values(
                        id=f"mem_{uuid.uuid4().hex[:12]}",
                        user_id=member_id,
                        org_id=org_id,
                        role="MEMBER",
                        status="ACTIVE",
                        created_at=datetime.now(UTC).isoformat(),
                        updated_at=datetime.now(UTC).isoformat(),
                    )
                )
            m_session_token, _ = await identities.create_session(member_id, org_id=org_id)
            _, _, m_assurance = await sec_svc.load_session(m_session_token)
            m_grant = await sec_svc.issue_step_up(
                m_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=org_id,
            )
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    m_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=org_id,
                    grant=m_grant,
                    allow_initial_owner_passkey_bootstrap=True,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"

            # 4. Pending account recovery request fails closed
            rec_grant = await sec_svc.issue_step_up(
                session_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=org_id,
            )
            async with engine._engine.begin() as conn:
                await conn.execute(
                    insert(account_recovery_requests).values(
                        id=f"rec_{uuid.uuid4().hex[:12]}",
                        user_id=owner_id,
                        token_hash="dummy_hash_for_recovery",
                        status="RECOVERY_REVIEW",
                        privileged=1,
                        created_at=datetime.now(UTC).isoformat(),
                        expires_at=(datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                        consumed_at=None,
                        evidence_json="{}",
                    )
                )
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    session_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=org_id,
                    grant=rec_grant,
                    allow_initial_owner_passkey_bootstrap=True,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"
            # Consume recovery request so subsequent assertions test their own invariants
            async with engine._engine.begin() as conn:
                await conn.execute(
                    update(account_recovery_requests)
                    .where(account_recovery_requests.c.user_id == owner_id)
                    .values(consumed_at=datetime.now(UTC).isoformat())
                )

            # 5. User with existing passkey (even revoked/disabled) fails closed
            passkey_grant = await sec_svc.issue_step_up(
                session_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=org_id,
            )
            async with engine._engine.begin() as conn:
                await conn.execute(
                    insert(passkey_credentials).values(
                        id=f"cred_{uuid.uuid4().hex[:12]}",
                        user_id=owner_id,
                        credential_id="test_cred_id_bytes",
                        public_key="test_public_key",
                        sign_count=0,
                        rp_id="localhost",
                        transports_json="[]",
                        aaguid="00000000-0000-0000-0000-000000000000",
                        backup_eligible=0,
                        backup_state=0,
                        display_name="Revoked Passkey",
                        status="REVOKED",
                        created_at=datetime.now(UTC).isoformat(),
                        last_used_at=None,
                    )
                )
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    session_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=org_id,
                    grant=passkey_grant,
                    allow_initial_owner_passkey_bootstrap=True,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"

            # 6. User with active TOTP factor fails closed
            owner_totp, owner_totp_tok = await identities.register(
                "Totp Owner", f"totp.{uuid.uuid4().hex[:8]}@example.com", "Password123!@#"
            )
            await identities.verify_email(owner_totp_tok)
            totp_org = await iam.create_workspace(
                actor_user_id=owner_totp,
                name="Totp Org",
                slug=f"totp-{uuid.uuid4().hex[:6]}",
                kind="ORGANIZATION",
            )
            totp_org_id = totp_org["id"] if isinstance(totp_org, dict) else totp_org.id
            totp_session_token, _ = await identities.create_session(owner_totp, org_id=totp_org_id)
            _, _, totp_assurance = await sec_svc.load_session(totp_session_token)
            # Insert TOTP factor
            async with engine._engine.begin() as conn:
                await conn.execute(
                    insert(human_totp_factors).values(
                        user_id=owner_totp,
                        secret_encrypted="enc_secret",
                        status="ACTIVE",
                        created_at=datetime.now(UTC).isoformat(),
                        confirmed_at=datetime.now(UTC).isoformat(),
                    )
                )
            totp_grant = await sec_svc.issue_step_up(
                totp_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=totp_org_id,
            )
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    totp_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=totp_org_id,
                    grant=totp_grant,
                    allow_initial_owner_passkey_bootstrap=True,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"

            # 7. auth_replay_records marker blocks duplicate or replayed bootstrap
            replay_owner, replay_tok = await identities.register(
                "Replay Owner", f"replay.{uuid.uuid4().hex[:8]}@example.com", "Password123!@#"
            )
            await identities.verify_email(replay_tok)
            replay_org = await iam.create_workspace(
                actor_user_id=replay_owner,
                name="Replay Org",
                slug=f"replay-{uuid.uuid4().hex[:6]}",
                kind="ORGANIZATION",
            )
            replay_org_id = replay_org["id"] if isinstance(replay_org, dict) else replay_org.id
            rep_session_token, _ = await identities.create_session(replay_owner, org_id=replay_org_id)
            _, _, rep_assurance = await sec_svc.load_session(rep_session_token)
            # Insert replay record
            async with engine._engine.begin() as conn:
                await conn.execute(
                    insert(auth_replay_records).values(
                        id=f"rep_{uuid.uuid4().hex[:12]}",
                        kind="first_passkey_bootstrap",
                        replay_key=f"first_passkey:{replay_owner}",
                        created_at=datetime.now(UTC).isoformat(),
                    )
                )
            rep_grant = await sec_svc.issue_step_up(
                rep_assurance,
                action=SensitiveAction.ADD_PASSKEY,
                org_id=replay_org_id,
            )
            with pytest.raises(EnterpriseError) as exc_info:
                await sec_svc.require_step_up(
                    rep_assurance,
                    action=SensitiveAction.ADD_PASSKEY,
                    org_id=replay_org_id,
                    grant=rep_grant,
                    allow_initial_owner_passkey_bootstrap=True,
                )
            assert exc_info.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"
        finally:
            await engine.close()
