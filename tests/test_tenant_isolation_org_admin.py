# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial cross-tenant isolation tests for /api/orgs/{org_id} route family.

Proves that an authenticated user/API key in Organization A cannot read,
modify, delete, or steal credentials/MFA from Organization B across all
administrative endpoints under /api/orgs/{org_id}.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, settings
from responsibleai.rbac.models import Role


@pytest.fixture(autouse=True)
def _isolated_test_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.mark.asyncio
async def test_cross_tenant_isolation_on_org_endpoints():
    async with LifespanManager(app, startup_timeout=15):
        org_repo = app_module._org_repo

        # Setup Org A with an OWNER key
        org_a = await org_repo.create_org("Organization A", "org-a")
        key_a, raw_key_a = await org_repo.create_key(org_a.id, "key-a", Role.OWNER)

        # Setup Org B with an OWNER key
        org_b = await org_repo.create_org("Organization B", "org-b")
        key_b, raw_key_b = await org_repo.create_key(org_b.id, "key-b", Role.OWNER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {raw_key_a}"}

            # 1. Organization Read
            resp = await client.get(f"/api/orgs/{org_b.id}", headers=headers_a)
            assert resp.status_code == 404, (
                f"Cross-org get_org expected 404, got {resp.status_code}"
            )

            # 2. SSO Configuration
            resp = await client.put(
                f"/api/orgs/{org_b.id}/sso", headers=headers_a, json={"sso_required": False}
            )
            assert resp.status_code == 404, (
                f"Cross-org set_org_sso expected 404, got {resp.status_code}"
            )

            # 3. MFA Requirement Configuration
            resp = await client.put(
                f"/api/orgs/{org_b.id}/mfa", headers=headers_a, json={"mfa_required": True}
            )
            assert resp.status_code == 404, (
                f"Cross-org set_org_mfa expected 404, got {resp.status_code}"
            )

            # 4. Authority Ceiling Read
            resp = await client.get(f"/api/orgs/{org_b.id}/authority-ceiling", headers=headers_a)
            assert resp.status_code == 404, (
                f"Cross-org get_authority_ceiling expected 404, got {resp.status_code}"
            )

            # 5. Authority Ceiling Write
            resp = await client.put(
                f"/api/orgs/{org_b.id}/authority-ceiling",
                headers=headers_a,
                json={
                    "max_value_usd": 10.0,
                    "allowed_targets": ["target1"],
                    "denied_targets": [],
                    "max_delegation_depth": 1,
                    "allowed_action_types": ["action1"],
                    "require_approval_for": [],
                },
            )
            assert resp.status_code == 404, (
                f"Cross-org set_authority_ceiling expected 404, got {resp.status_code}"
            )

            # 6. Autonomy Budget Read
            resp = await client.get(f"/api/orgs/{org_b.id}/autonomy-budget", headers=headers_a)
            assert resp.status_code == 404, (
                f"Cross-org get_autonomy_budget expected 404, got {resp.status_code}"
            )

            # 7. Autonomy Budget Write
            resp = await client.put(
                f"/api/orgs/{org_b.id}/autonomy-budget",
                headers=headers_a,
                json={"max_autonomous_actions": 5, "window_minutes": 60},
            )
            assert resp.status_code == 404, (
                f"Cross-org set_autonomy_budget expected 404, got {resp.status_code}"
            )

            # 8. Autonomy Budget Delete
            resp = await client.delete(f"/api/orgs/{org_b.id}/autonomy-budget", headers=headers_a)
            assert resp.status_code == 404, (
                f"Cross-org delete_autonomy_budget expected 404, got {resp.status_code}"
            )

            # 9. MFA Enroll (secret theft prevention)
            resp = await client.post(
                f"/api/orgs/{org_b.id}/keys/{key_b.id}/mfa/enroll", headers=headers_a
            )
            assert resp.status_code == 404, (
                f"Cross-org enroll_mfa expected 404, got {resp.status_code}"
            )

            # 10. MFA Verify
            resp = await client.post(
                f"/api/orgs/{org_b.id}/keys/{key_b.id}/mfa/verify",
                headers=headers_a,
                json={"code": "123456"},
            )
            assert resp.status_code == 404, (
                f"Cross-org verify_mfa expected 404, got {resp.status_code}"
            )

            # 11. MFA Disable
            resp = await client.delete(
                f"/api/orgs/{org_b.id}/keys/{key_b.id}/mfa", headers=headers_a
            )
            assert resp.status_code == 404, (
                f"Cross-org disable_mfa expected 404, got {resp.status_code}"
            )

            # 12. Organization Delete
            resp = await client.delete(f"/api/orgs/{org_b.id}", headers=headers_a)
            assert resp.status_code == 404, (
                f"Cross-org delete_org expected 404, got {resp.status_code}"
            )

            # Confirm Org B was NOT deleted
            org_b_check = await org_repo.get_org(org_b.id)
            assert org_b_check is not None, "Org B should still exist"

            # ── Positive assertions: Org A operating on Org A must still work ──
            resp_self = await client.get(f"/api/orgs/{org_a.id}", headers=headers_a)
            assert resp_self.status_code == 200
            assert resp_self.json()["name"] == "Organization A"

            resp_self_mfa = await client.put(
                f"/api/orgs/{org_a.id}/mfa", headers=headers_a, json={"mfa_required": True}
            )
            assert resp_self_mfa.status_code == 200

            resp_self_ceil = await client.get(
                f"/api/orgs/{org_a.id}/authority-ceiling", headers=headers_a
            )
            assert resp_self_ceil.status_code == 200

            resp_self_enroll = await client.post(
                f"/api/orgs/{org_a.id}/keys/{key_a.id}/mfa/enroll", headers=headers_a
            )
            assert resp_self_enroll.status_code == 200
            totp_secret = resp_self_enroll.json()["secret"]
            import pyotp

            valid_code = pyotp.TOTP(totp_secret).now()

            resp_self_verify = await client.post(
                f"/api/orgs/{org_a.id}/keys/{key_a.id}/mfa/verify",
                headers=headers_a,
                json={"code": valid_code},
            )
            assert resp_self_verify.status_code == 200
            assert resp_self_verify.json()["enrolled"] is True

            resp_self_disable = await client.delete(
                f"/api/orgs/{org_a.id}/keys/{key_a.id}/mfa", headers=headers_a
            )
            assert resp_self_disable.status_code == 200

            resp_self_del = await client.delete(f"/api/orgs/{org_a.id}", headers=headers_a)
            assert resp_self_del.status_code == 200
            assert (await org_repo.get_org(org_a.id)) is None


@pytest.mark.asyncio
async def test_global_vendor_bootstrap_admin_cannot_silently_cross_or_administer_customer_tenants():
    """HARD INVARIANT (ANT-P0-001):
    A global/vendor-style administrative identity (flat bootstrap API key)
    must NOT possess an implicit backdoor to silently read, modify, delete,
    or harvest credentials from an existing customer organization.
    Only credentials scoped to that exact organization (_auth.org_id == target_org_id)
    may perform organizational administration.
    """
    async with LifespanManager(app, startup_timeout=15):
        org_repo = app_module._org_repo

        # Provision customer organization (even if provisioned by bootstrap key)
        org_cust = await org_repo.create_org(
            "Customer Enterprise",
            "customer-ent",
            provisioner_key_id="legacy:bootstrap-key-hash",
        )
        key_cust, raw_key_cust = await org_repo.create_key(org_cust.id, "cust-owner", Role.OWNER)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_bootstrap = {"Authorization": "Bearer bootstrap-key"}

            # 1. Global bootstrap key CANNOT read customer organization details
            r = await client.get(f"/api/orgs/{org_cust.id}", headers=headers_bootstrap)
            assert r.status_code in {403, 404}, (
                f"Bootstrap key get_org expected 404, got {r.status_code}"
            )

            # 2. Global bootstrap key CANNOT modify customer SSO settings
            r = await client.put(
                f"/api/orgs/{org_cust.id}/sso",
                headers=headers_bootstrap,
                json={"sso_required": False},
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key set_sso expected 404, got {r.status_code}"
            )

            # 3. Global bootstrap key CANNOT modify customer MFA policy
            r = await client.put(
                f"/api/orgs/{org_cust.id}/mfa",
                headers=headers_bootstrap,
                json={"mfa_required": True},
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key set_mfa expected 404, got {r.status_code}"
            )

            # 4. Global bootstrap key CANNOT read customer authority ceiling
            r = await client.get(
                f"/api/orgs/{org_cust.id}/authority-ceiling", headers=headers_bootstrap
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key get_authority_ceiling expected 404, got {r.status_code}"
            )

            # 5. Global bootstrap key CANNOT alter customer authority ceiling
            r = await client.put(
                f"/api/orgs/{org_cust.id}/authority-ceiling",
                headers=headers_bootstrap,
                json={"max_value_usd": 100.0, "allowed_targets": [], "denied_targets": []},
            )
            assert r.status_code in {403, 404}, f"Bootstrap key expected deny, got {r.status_code}"

            # 6. Global bootstrap key CANNOT read customer autonomy budget
            r = await client.get(
                f"/api/orgs/{org_cust.id}/autonomy-budget", headers=headers_bootstrap
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key get_autonomy_budget expected 404, got {r.status_code}"
            )

            # 7. Global bootstrap key CANNOT set customer autonomy budget
            r = await client.put(
                f"/api/orgs/{org_cust.id}/autonomy-budget",
                headers=headers_bootstrap,
                json={"max_autonomous_actions": 10, "window_minutes": 30},
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key set_autonomy_budget expected 404, got {r.status_code}"
            )

            # 8. Global bootstrap key CANNOT delete customer autonomy budget
            r = await client.delete(
                f"/api/orgs/{org_cust.id}/autonomy-budget", headers=headers_bootstrap
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key delete_autonomy_budget expected 404, got {r.status_code}"
            )

            # 9. Global bootstrap key CANNOT steal/enroll MFA for customer key
            r = await client.post(
                f"/api/orgs/{org_cust.id}/keys/{key_cust.id}/mfa/enroll", headers=headers_bootstrap
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key enroll_mfa expected 404, got {r.status_code}"
            )

            # 10. Global bootstrap key CANNOT verify MFA for customer key
            r = await client.post(
                f"/api/orgs/{org_cust.id}/keys/{key_cust.id}/mfa/verify",
                headers=headers_bootstrap,
                json={"code": "123456"},
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key verify_mfa expected 404, got {r.status_code}"
            )

            # 11. Global bootstrap key CANNOT disable MFA for customer key
            r = await client.delete(
                f"/api/orgs/{org_cust.id}/keys/{key_cust.id}/mfa", headers=headers_bootstrap
            )
            assert r.status_code in {403, 404}, (
                f"Bootstrap key disable_mfa expected 404, got {r.status_code}"
            )

            # 12. Global bootstrap key CANNOT delete customer organization
            r = await client.delete(f"/api/orgs/{org_cust.id}", headers=headers_bootstrap)
            assert r.status_code in {403, 404}, (
                f"Bootstrap key delete_org expected 404, got {r.status_code}"
            )

            # Confirm customer org is intact
            org_check = await org_repo.get_org(org_cust.id)
            assert org_check is not None, "Customer org must remain untouched"

            # Confirm legitimate customer admin CAN administer its own organization
            headers_cust = {"Authorization": f"Bearer {raw_key_cust}"}
            r_cust = await client.get(f"/api/orgs/{org_cust.id}", headers=headers_cust)
            assert r_cust.status_code == 200
            assert r_cust.json()["name"] == "Customer Enterprise"
