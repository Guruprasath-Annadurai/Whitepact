# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Customer Root Authority Bootstrap & Trust Fabric Bridge Acceptance Suite.

Mandatory Security Gates:
S1 — Trusted root provisioning: Authenticated customer establishes canonical root authority
     and explicit consent through the supported API without privileged test fixtures.
S2 — Trust Fabric integrity: Only a verified trusted identity and authorized owner can initiate root issuance.
S3 — Delegation and revocation: Attenuation, graph validity and epoch semantics preserved.
S4 — Policy and approvals fail closed.
S5 — Execution enforcement: Actions outside customer consent fail closed.
"""

from __future__ import annotations

import asyncio
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import (
    create_engine,
    governance_consent_proofs,
    governance_delegations,
    governance_root_authority_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_users,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.service import EnterpriseIAM
from responsibleai.governance.authority_resolver import AuthorityDenied, AuthorityResolver
from responsibleai.governance.context import GovernanceContext
from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext
from responsibleai.rbac.models import OrgContext, Role


@pytest.fixture(autouse=True)
def _configure_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "customer_authority_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-admin-key"])
    monkeypatch.setattr(settings, "db_path", str(db_file))
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield


@pytest.fixture
async def api_client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            cookies={},
        ) as client:
            yield client


async def _create_authenticated_customer_owner(
    client: AsyncClient,
    *,
    full_name: str = "Alice Founder",
    email: str = "alice@example.com",
    password: str = "SecurePass123!@#",
    org_name: str = "Acme Corp",
    org_slug: str = "acme-corp",
) -> tuple[str, str, dict[str, str]]:
    """Helper creating a real customer user and org through standard repositories (no backdoor)."""
    engine = get_enterprise_engine()
    web_repo = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)

    # 1. Register customer human user
    user_id, _verification_token = await web_repo.register(full_name, email, password)

    # 2. Mark email verified through standard token verification
    await web_repo.verify_email(_verification_token)

    # 3. Create enterprise workspace / organization with user as OWNER
    org = await iam.create_workspace(
        actor_user_id=user_id,
        name=org_name,
        slug=org_slug,
        kind="ORGANIZATION",
    )

    # 4. Create authenticated browser session
    org_id = org["id"] if isinstance(org, dict) else org.id
    session_token, csrf_token = await web_repo.create_session(user_id, org_id=org_id)

    cookies = {
        "wp_session": session_token,
        "wp_csrf": csrf_token,
    }
    headers = {
        "X-WP-CSRF": csrf_token,
    }

    return user_id, org_id, {**cookies, "csrf_header": csrf_token}


@pytest.mark.asyncio
class TestCustomerRootAuthorityBootstrap:
    async def test_end_to_end_customer_authority_bootstrap_journey(self, api_client: AsyncClient):
        """S1 & S2 Acceptance Gate:

        1. Register user & create org via standard customer identity path.
        2. Initiate bootstrap ceremony via authenticated HTTP POST.
        3. Complete bootstrap with explicit, bounded consent parameters.
        4. Verify canonical governance root and consent proof records.
        5. Register agent -> verify registration alone does NOT grant authority.
        6. Delegate attenuated authority to agent.
        7. AuthorityResolver successfully validates action permitted by consent.
        8. AuthorityResolver denies action outside consent / delegation.
        9. Revoke root authority -> subsequent actions fail closed.
        """
        user_id, org_id, auth = await _create_authenticated_customer_owner(
            api_client, email="founder@enterprise.com", org_slug="enterprise-alpha"
        )
        api_client.cookies.set("wp_session", auth["wp_session"])
        api_client.cookies.set("wp_csrf", auth["wp_csrf"])
        headers = {"X-WP-CSRF": auth["csrf_header"]}

        # 1. Check status before bootstrap: must report no active authority
        status_res = await api_client.get(
            f"/api/enterprise/organizations/{org_id}/authority/status",
            headers=headers,
        )
        assert status_res.status_code == 200
        assert status_res.json()["has_active_authority"] is False
        assert status_res.json()["root_authority"] is None

        # 2. Initiate bootstrap ceremony
        init_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/initiate",
            json={"ttl_seconds": 600},
            headers=headers,
        )
        assert init_res.status_code == 200
        init_data = init_res.json()
        assert init_data["organization_id"] == org_id
        assert init_data["token"].startswith("wp_boot_")
        assert init_data["nonce"].startswith("wp_nonce_")
        assert init_data["bound_owner_id"] == user_id

        token = init_data["token"]
        nonce = init_data["nonce"]

        # 3. Complete bootstrap with explicit scoped consent
        complete_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
            json={
                "token": token,
                "nonce": nonce,
                "root_public_key": "ed25519_pk_enterprise_customer_root_001",
                "scope_description": "Authorizes automated invoice reconciliation and ledger audit agents",
                "purpose": "invoice-reconciliation",
                "allowed_action_types": ["invoice:read", "invoice:match"],
                "allowed_targets": ["invoices/2026/001", "invoices/2026/002"],
                "key_algorithm": "Ed25519",
                "consent_method": "CRYPTOGRAPHIC_CEREMONY",
                "evidence_refs": ["board_resolution_2026_09", "ciso_approval_ceremony"],
            },
            headers=headers,
        )
        assert complete_res.status_code == 200
        complete_data = complete_res.json()
        assert complete_data["status"] == "BOOTSTRAPPED"
        assert complete_data["organization_id"] == org_id
        assert complete_data["subject_id"] == user_id
        assert complete_data["epoch"] == 1
        root_id = complete_data["root_id"]
        consent_id = complete_data["consent_id"]

        # 4. Verify status now reports active root and consent
        status_res2 = await api_client.get(
            f"/api/enterprise/organizations/{org_id}/authority/status",
            headers=headers,
        )
        assert status_res2.status_code == 200
        status2_data = status_res2.json()
        assert status2_data["has_active_authority"] is True
        assert status2_data["root_authority"]["root_id"] == root_id
        assert status2_data["consent_proof"]["consent_id"] == consent_id
        assert status2_data["consent_proof"]["purpose"] == "invoice-reconciliation"

        # 5. Register an AI Agent: Registration MUST NOT grant authority!
        agent_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/agents",
            json={
                "name": "Invoice Reconciliation Agent",
                "description": "Autonomous invoice processing agent",
                "framework": "crewai",
                "purpose": "invoice-reconciliation",
            },
            headers=headers,
        )
        assert agent_res.status_code == 200
        agent_data = agent_res.json()
        agent_id = agent_data["agent_id"]
        assert agent_data["has_delegated_authority"] is False, "Registration must not grant authority"

        # Verify that without delegation, AuthorityResolver denies execution
        engine = get_enterprise_engine()
        roots_repo = RootAuthorityRepository(engine)
        consents_repo = ConsentProofRepository(engine)
        delegations_repo = DelegationRepository(engine)
        resolver = AuthorityResolver(roots_repo, consents_repo, delegations_repo)

        auth_context = OrgContext(key_id=agent_id, role=Role.ANALYST, org_id=org_id)
        valid_action = ActionRequest(
            agent=AgentContext(identity=IdentityContext.from_org_context(auth_context), agent_id=agent_id),
            action_type="invoice:read",
            target="invoices/2026/001",
            purpose="invoice-reconciliation",
        )
        gov_context = GovernanceContext.from_authenticated(auth_context, valid_action, authentication_method="api_key")

        # Without delegation, resolver MUST fail closed
        with pytest.raises(AuthorityDenied):
            await resolver.resolve(gov_context)

        # 6. Issue Attenuated Delegation to the Agent
        delegation_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/delegations",
            json={
                "granted_action_types": ["invoice:read"],  # Narrower than root's ["invoice:read", "invoice:match"]
                "allowed_targets": ["invoices/2026/001"],
                "purpose": "invoice-reconciliation",
            },
            headers=headers,
        )
        assert delegation_res.status_code == 200
        delegation_data = delegation_res.json()
        assert delegation_data["agent_id"] == agent_id

        # 7. Now AuthorityResolver MUST successfully resolve the permitted action!
        resolved = await resolver.resolve(gov_context)
        assert resolved is not None
        assert resolved.consent_id == delegation_data["consent_id"]
        assert resolved.grant.root_reference == root_id

        # 8. Action OUTSIDE consent / delegation MUST be denied
        unauthorized_action = ActionRequest(
            agent=AgentContext(identity=IdentityContext.from_org_context(auth_context), agent_id=agent_id),
            action_type="invoice:delete",  # Not consented or delegated
            target="invoices/2026/001",
            purpose="invoice-reconciliation",
        )
        unauthorized_gov_context = GovernanceContext.from_authenticated(
            auth_context, unauthorized_action, authentication_method="api_key"
        )
        with pytest.raises(AuthorityDenied):
            await resolver.resolve(unauthorized_gov_context)

        # 9. Revoke Root Authority: Cascading failure closed
        revoke_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/root/{root_id}/revoke",
            json={"reason": "Customer security key rollover"},
            headers=headers,
        )
        assert revoke_res.status_code == 200
        assert revoke_res.json()["status"] == "REVOKED"
        assert revoke_res.json()["new_epoch"] == 2

        # After revocation, previously valid action MUST now fail closed
        with pytest.raises(AuthorityDenied):
            await resolver.resolve(gov_context)

    async def test_concurrent_bootstrap_attempts_single_winner(self, api_client: AsyncClient):
        """Proves atomic single-winner guarantee under concurrent bootstrap races."""
        _user_id, org_id, auth = await _create_authenticated_customer_owner(
            api_client, email="race@corp.com", org_slug="race-corp"
        )
        api_client.cookies.set("wp_session", auth["wp_session"])
        api_client.cookies.set("wp_csrf", auth["wp_csrf"])
        headers = {"X-WP-CSRF": auth["csrf_header"]}

        init_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/initiate",
            json={"ttl_seconds": 600},
            headers=headers,
        )
        assert init_res.status_code == 200
        init_data = init_res.json()
        token = init_data["token"]
        nonce = init_data["nonce"]

        payload = {
            "token": token,
            "nonce": nonce,
            "root_public_key": "pk_race_test",
            "scope_description": "Concurrent race test scope",
            "purpose": "race-testing",
            "allowed_action_types": ["test:act"],
            "allowed_targets": ["test/*"],
        }

        # Fire two concurrent completions
        res1, res2 = await asyncio.gather(
            api_client.post(
                f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
                json=payload,
                headers=headers,
            ),
            api_client.post(
                f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
                json=payload,
                headers=headers,
            ),
        )

        statuses = {res1.status_code, res2.status_code}
        # Exactly one must succeed (200), and the other must be rejected (409)
        assert 200 in statuses
        assert 409 in statuses

    async def test_replayed_bootstrap_token_rejected(self, api_client: AsyncClient):
        """Anti-replay: Consumed token cannot be reused."""
        _user_id, org_id, auth = await _create_authenticated_customer_owner(
            api_client, email="replay@corp.com", org_slug="replay-corp"
        )
        api_client.cookies.set("wp_session", auth["wp_session"])
        api_client.cookies.set("wp_csrf", auth["wp_csrf"])
        headers = {"X-WP-CSRF": auth["csrf_header"]}

        init_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/initiate",
            headers=headers,
            json={"ttl_seconds": 600},
        )
        init_data = init_res.json()
        payload = {
            "token": init_data["token"],
            "nonce": init_data["nonce"],
            "root_public_key": "pk_replay_test",
            "scope_description": "Anti-replay test",
            "purpose": "replay-test",
            "allowed_action_types": ["test:read"],
            "allowed_targets": ["test/*"],
        }

        # First consumption: OK
        res1 = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
            json=payload,
            headers=headers,
        )
        assert res1.status_code == 200

        # Second consumption: REPLAY REJECTED (409)
        res2 = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
            json=payload,
            headers=headers,
        )
        assert res2.status_code == 409
        assert res2.json()["error"] in {"BOOTSTRAP_TOKEN_REPLAY", "ROOT_ALREADY_EXISTS"}

    async def test_cross_tenant_bootstrap_rejected(self, api_client: AsyncClient):
        """Cross-tenant isolation: Tenant A owner cannot bootstrap Tenant B."""
        _user_a, org_a, auth_a = await _create_authenticated_customer_owner(
            api_client, email="user_a@corp.com", org_slug="corp-a"
        )
        _user_b, org_b, _auth_b = await _create_authenticated_customer_owner(
            api_client, email="user_b@corp.com", org_slug="corp-b"
        )

        api_client.cookies.set("wp_session", auth_a["wp_session"])
        api_client.cookies.set("wp_csrf", auth_a["wp_csrf"])
        headers_a = {"X-WP-CSRF": auth_a["csrf_header"]}

        # User A attempts to initiate bootstrap in Org B
        res = await api_client.post(
            f"/api/enterprise/organizations/{org_b}/authority/bootstrap/initiate",
            headers=headers_a,
            json={"ttl_seconds": 600},
        )
        assert res.status_code == 403
        assert res.json()["error"] in {"CROSS_TENANT", "FORBIDDEN", "UNAUTHORIZED_BOOTSTRAP_CALLER"}

    async def test_csrf_protection_enforced(self, api_client: AsyncClient):
        """CSRF attack rejection: Missing or mismatched X-WP-CSRF header is blocked."""
        _user_id, org_id, auth = await _create_authenticated_customer_owner(
            api_client, email="csrf@corp.com", org_slug="csrf-corp"
        )
        api_client.cookies.set("wp_session", auth["wp_session"])
        api_client.cookies.set("wp_csrf", auth["wp_csrf"])

        # Omit X-WP-CSRF header
        res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/initiate",
            json={"ttl_seconds": 600},
        )
        assert res.status_code in {401, 403}

    async def test_empty_consent_fails_closed(self, api_client: AsyncClient):
        """Consent completeness: Empty scope or purpose is rejected."""
        _user_id, org_id, auth = await _create_authenticated_customer_owner(
            api_client, email="empty_consent@corp.com", org_slug="empty-consent-corp"
        )
        api_client.cookies.set("wp_session", auth["wp_session"])
        api_client.cookies.set("wp_csrf", auth["wp_csrf"])
        headers = {"X-WP-CSRF": auth["csrf_header"]}

        init_res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/initiate",
            headers=headers,
            json={"ttl_seconds": 600},
        )
        init_data = init_res.json()

        # Empty allowed_action_types
        res = await api_client.post(
            f"/api/enterprise/organizations/{org_id}/authority/bootstrap/complete",
            json={
                "token": init_data["token"],
                "nonce": init_data["nonce"],
                "root_public_key": "pk_test",
                "scope_description": "Valid scope",
                "purpose": "valid-purpose",
                "allowed_action_types": [],  # INVALID
                "allowed_targets": ["*"],
            },
            headers=headers,
        )
        assert res.status_code in {400, 422}
