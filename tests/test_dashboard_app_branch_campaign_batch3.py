# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-campaign batch 3: web console, org RBAC, billing webhooks, auth SSO,
governance extensions, leaderboard/trust-index, and ops audit paths in
``dashboard/app.py``."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.rbac.models import Role
from tests.org_http_fixtures import seed_org_with_key


@pytest.fixture()
async def client():
    orig_database_url = settings.database_url
    orig_db_path = settings.db_path
    orig_auto_migrate = settings.auto_migrate

    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url = orig_database_url
        settings.db_path = orig_db_path
        settings.auto_migrate = orig_auto_migrate


@pytest.fixture()
async def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    _auth_failure_limiter._failures.clear()

    async with LifespanManager(app, startup_timeout=15) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac

    _auth_failure_limiter._failures.clear()


@pytest.fixture()
async def web_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(settings, "web_session_secure", False)
    monkeypatch.setattr(settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=30, window_seconds=3600.0)
    )
    monkeypatch.setattr(limiter, "enabled", False)

    async with LifespanManager(app, startup_timeout=15) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def _paddle_sig(secret: str, body: bytes, ts: int | None = None) -> str:
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    signed = f"{ts}:".encode() + body
    h1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


async def _web_session_with_org(web_client: AsyncClient, email: str) -> tuple[str, str]:
    reg = await web_client.post(
        "/api/web/auth/register",
        json={
            "full_name": "Branch Campaign User",
            "email": email,
            "password": "Correct-Horse-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    assert (await web_client.post("/api/web/auth/verify", json={"token": token})).status_code == 200
    login = await web_client.post(
        "/api/web/auth/login",
        json={"email": email, "password": "Correct-Horse-42!"},
    )
    assert login.status_code == 200
    csrf = web_client.cookies.get("wp_csrf", "")
    onboard = await web_client.post(
        "/api/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Batch Three Org", "use_case": "coverage"},
    )
    assert onboard.status_code == 200
    return csrf, web_client.cookies.get("wp_session", "")


class TestWebAuthAndConsoleDeny:
    async def test_web_register_requires_delivery_or_dev_tokens(
        self, web_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "web_auth_dev_tokens", False)
        monkeypatch.setattr(settings, "web_verification_delivery_url", None)
        r = await web_client.post(
            "/api/web/auth/register",
            json={
                "full_name": "No Delivery",
                "email": "nodelivery@example.com",
                "password": "Correct-Horse-42!",
                "accepted_terms": True,
            },
        )
        assert r.status_code == 503

    async def test_web_register_rejects_disposable_email(self, web_client: AsyncClient) -> None:
        r = await web_client.post(
            "/api/web/auth/register",
            json={
                "full_name": "Disposable",
                "email": "user@mailinator.com",
                "password": "Correct-Horse-42!",
                "accepted_terms": True,
            },
        )
        assert r.status_code == 422

    async def test_web_register_rejects_weak_password(self, web_client: AsyncClient) -> None:
        r = await web_client.post(
            "/api/web/auth/register",
            json={
                "full_name": "Weak",
                "email": "weak@example.com",
                "password": "alllowercase",
                "accepted_terms": True,
            },
        )
        assert r.status_code == 422

    async def test_web_verify_invalid_token_is_400(self, web_client: AsyncClient) -> None:
        r = await web_client.post("/api/web/auth/verify", json={"token": "x" * 32})
        assert r.status_code == 400

    async def test_web_password_reset_unconfigured_is_503(
        self, web_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "web_auth_dev_tokens", False)
        r = await web_client.post(
            "/api/web/auth/password-reset",
            json={"email": "missing@example.com"},
        )
        assert r.status_code == 503

    async def test_web_password_reset_confirm_invalid_token(self, web_client: AsyncClient) -> None:
        r = await web_client.post(
            "/api/web/auth/password-reset/confirm",
            json={"token": "y" * 32, "password": "Correct-Horse-42!"},
        )
        assert r.status_code == 400

    async def test_web_login_invalid_credentials(self, web_client: AsyncClient) -> None:
        r = await web_client.post(
            "/api/web/auth/login",
            json={"email": "nobody@example.com", "password": "Correct-Horse-42!"},
        )
        assert r.status_code == 401

    async def test_web_session_without_cookie_is_401(self, web_client: AsyncClient) -> None:
        r = await web_client.get("/api/web/session")
        assert r.status_code == 401

    async def test_web_logout_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"logout-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post("/api/web/auth/logout")
        assert r.status_code == 403
        ok = await web_client.post("/api/web/auth/logout", headers={"X-WP-CSRF": csrf})
        assert ok.status_code == 200

    async def test_web_onboarding_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"onboard-csrf-{uuid.uuid4().hex}@example.com"
        reg = await web_client.post(
            "/api/web/auth/register",
            json={
                "full_name": "CSRF User",
                "email": email,
                "password": "Correct-Horse-42!",
                "accepted_terms": True,
            },
        )
        token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
        await web_client.post("/api/web/auth/verify", json={"token": token})
        await web_client.post(
            "/api/web/auth/login",
            json={"email": email, "password": "Correct-Horse-42!"},
        )
        r = await web_client.post(
            "/api/web/onboarding",
            json={"organization_name": "Needs CSRF", "use_case": "test"},
        )
        assert r.status_code == 403

    async def test_web_switch_org_unknown_membership_is_404(self, web_client: AsyncClient) -> None:
        email = f"switch-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/session/switch-organization",
            headers={"X-WP-CSRF": csrf},
            json={"organization_id": str(uuid.uuid4())},
        )
        assert r.status_code == 404

    async def test_web_dashboard_unknown_domain_is_404(self, web_client: AsyncClient) -> None:
        email = f"dash-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.get("/api/web/dashboard/not-a-real-section")
        assert r.status_code == 404

    async def test_web_dashboard_before_onboarding_is_409(self, web_client: AsyncClient) -> None:
        email = f"no-org-{uuid.uuid4().hex}@example.com"
        reg = await web_client.post(
            "/api/web/auth/register",
            json={
                "full_name": "No Org Yet",
                "email": email,
                "password": "Correct-Horse-42!",
                "accepted_terms": True,
            },
        )
        token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
        await web_client.post("/api/web/auth/verify", json={"token": token})
        await web_client.post(
            "/api/web/auth/login",
            json={"email": email, "password": "Correct-Horse-42!"},
        )
        r = await web_client.get("/api/web/dashboard/usage")
        assert r.status_code == 409

    async def test_web_patch_organization_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"patch-org-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.patch("/api/web/organization", json={"name": "Renamed Org"})
        assert r.status_code == 403

    async def test_web_patch_organization_name_too_short(self, web_client: AsyncClient) -> None:
        email = f"patch-short-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.patch(
            "/api/web/organization",
            headers={"X-WP-CSRF": csrf},
            json={"name": "X"},
        )
        assert r.status_code == 422

    async def test_web_approval_missing_is_404(self, web_client: AsyncClient) -> None:
        email = f"approval-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.get("/api/web/approvals/does-not-exist")
        assert r.status_code == 404

    async def test_web_evidence_missing_is_404(self, web_client: AsyncClient) -> None:
        email = f"evidence-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.get("/api/web/evidence/ev-missing")
        assert r.status_code == 404


class TestWebDashboardDomains:
    @pytest.mark.parametrize(
        "domain",
        [
            "agents",
            "approvals",
            "evidence",
            "usage",
            "policies",
            "mcp",
            "organization",
            "members",
            "billing",
            "settings",
            "security",
        ],
    )
    async def test_onboarded_user_can_load_dashboard_domain(
        self, web_client: AsyncClient, domain: str
    ) -> None:
        email = f"dash-{domain}-{uuid.uuid4().hex[:8]}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.get(f"/api/web/dashboard/{domain}")
        assert r.status_code == 200
        body = r.json()
        assert body.get("domain") == domain
        assert "items" in body or domain == "security"


class TestOrgRbacAndKeysDeny:
    async def test_list_keys_cross_tenant_returns_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Keys Tenant",
            slug=f"keys-tenant-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.get(f"/api/orgs/{org_id}/keys", headers=_bearer(raw))
        assert r.status_code == 200
        other = str(uuid.uuid4())
        r2 = await auth_client.get(f"/api/orgs/{other}/keys", headers=_bearer(raw))
        assert r2.status_code == 404

    async def test_create_key_without_accountable_human_is_403(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Issue Keys Co",
            slug=f"issue-keys-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "child-key", "role": "ANALYST"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403
        assert r.json()["error"] == "API_KEY_ISSUANCE_NOT_ALLOWED"

    async def test_revoke_missing_key_is_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Revoke Co",
            slug=f"revoke-co-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(
            f"/api/orgs/{org_id}/keys/missing-key-id",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_mfa_enroll_missing_key_is_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="MFA Co",
            slug=f"mfa-co-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys/missing-key/mfa/enroll",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_mfa_verify_without_enroll_is_400(self, auth_client: AsyncClient) -> None:
        org_id, key_id, raw = await seed_org_with_key(
            name="MFA Verify Co",
            slug=f"mfa-verify-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify",
            json={"code": "123456"},
            headers=_bearer(raw),
        )
        assert r.status_code == 400
        assert "enroll" in r.json()["message"].lower()

    async def test_mfa_disable_missing_key_is_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="MFA Off Co",
            slug=f"mfa-off-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(
            f"/api/orgs/{org_id}/keys/missing-key/mfa",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_set_sso_without_oidc_provider_is_400(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO Co",
            slug=f"sso-co-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/sso",
            json={"sso_required": True},
            headers=_bearer(raw),
        )
        assert r.status_code == 400
        assert "OIDC" in r.json()["message"]

    async def test_viewer_cannot_set_org_mfa(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="MFA Policy Co",
            slug=f"mfa-policy-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/mfa",
            json={"mfa_required": True},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_delete_org(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Delete Guard Co",
            slug=f"delete-guard-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.delete(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_signup_dwell_time_too_short_is_400(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/signup",
            json={
                "name": "Fast Signup",
                "slug": f"fast-signup-{uuid.uuid4().hex[:8]}",
                "email": "founder@example.com",
                "website": "",
                "page_loaded_at_ms": int(time.time() * 1000),
            },
        )
        assert r.status_code == 400

    async def test_signup_disposable_email_is_400(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/signup",
            json={
                "name": "Disposable Org",
                "slug": f"disp-signup-{uuid.uuid4().hex[:8]}",
                "email": "bot@mailinator.com",
                "website": "",
                "page_loaded_at_ms": int(time.time() * 1000) - 5000,
            },
        )
        assert r.status_code == 400


class TestPaddleStripeWebhookValidation:
    async def test_paddle_invalid_timestamp_in_signature(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=b"{}",
            headers={"Paddle-Signature": "ts=not-a-number;h1=abc"},
        )
        assert r.status_code == 400
        assert "timestamp" in r.json()["message"].lower()

    async def test_paddle_expired_signature(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        monkeypatch.setattr(settings, "paddle_signature_tolerance_seconds", 60)
        old_ts = int(datetime.now(UTC).timestamp()) - 120
        body = b'{"event_id":"e1"}'
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body, ts=old_ts)},
        )
        assert r.status_code == 400
        assert "expired" in r.json()["message"].lower()

    async def test_paddle_invalid_hmac(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        ts = int(datetime.now(UTC).timestamp())
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=b'{"event_id":"e1"}',
            headers={"Paddle-Signature": f"ts={ts};h1=deadbeef"},
        )
        assert r.status_code == 400
        assert "signature" in r.json()["message"].lower()

    async def test_paddle_invalid_json_body(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        body = b"not-json"
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 400

    async def test_paddle_missing_event_id(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        body = json.dumps(
            {"event_type": "subscription.updated", "occurred_at": "2024-01-01T00:00:00Z"}
        ).encode()
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 400
        assert "event_id" in r.json()["message"].lower()

    async def test_paddle_missing_occurred_at(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch3-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        body = json.dumps({"event_id": "evt-1", "event_type": "subscription.updated"}).encode()
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 400
        assert "occurred_at" in r.json()["message"].lower()

    async def test_stripe_webhook_bad_signature_when_configured(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        from responsibleai.billing.stripe_service import StripeBillingError

        mock_stripe = MagicMock()
        mock_stripe.verify_and_parse_webhook.side_effect = StripeBillingError("bad sig")
        monkeypatch.setattr("responsibleai.dashboard.app._stripe_service", mock_stripe)
        r = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "v1,deadbeef"},
        )
        assert r.status_code == 400

    async def test_billing_portal_requires_stripe_customer(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from unittest.mock import MagicMock

        monkeypatch.setattr(app_module, "_stripe_service", MagicMock())
        _org_id, _kid, raw = await seed_org_with_key(
            name="Portal Co",
            slug=f"portal-co-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post("/api/billing/portal", json={}, headers=_bearer(raw))
        assert r.status_code == 404


class TestAuthSsoAndLoginKey:
    async def test_auth_login_unknown_provider_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/login/unknown-provider")
        assert r.status_code == 404

    async def test_auth_login_oidc_unconfigured_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/login/oidc")
        assert r.status_code == 404

    async def test_auth_callback_oidc_unconfigured_is_501(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/callback", params={"code": "c", "state": "s"})
        assert r.status_code == 501

    async def test_saml_metadata_unconfigured_is_501(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/saml/metadata")
        assert r.status_code == 501

    async def test_saml_acs_unconfigured_is_501(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/acs", data={"SAMLResponse": "x"})
        assert r.status_code == 501

    async def test_auth_login_key_invalid_when_auth_enabled(self, auth_client: AsyncClient) -> None:
        r = await auth_client.post("/api/auth/login-key", json={"api_key": "not-a-real-key"})
        assert r.status_code == 401

    async def test_auth_login_key_ok_when_auth_disabled(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/login-key", json={"api_key": "anything"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    async def test_auth_providers_lists_api_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/providers")
        assert r.status_code == 200
        assert r.json()["count"] >= 1


class TestGovernanceExtendedDeny:
    async def test_delegation_revoke_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/delegations/agent-1/revoke",
            json={"reason": "probe"},
        )
        assert r.status_code == 400

    async def test_delegation_descendants_requires_org_scoped_key(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/api/governance/delegations/agent-1/descendants")
        assert r.status_code == 400

    async def test_delegation_graph_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/delegations/graph")
        assert r.status_code == 400

    async def test_intent_contract_empty_agent_id_is_422(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Intent Co",
            slug=f"intent-co-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/intent-contracts",
            json={"agent_id": "", "goal": "do work"},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_authority_passport_no_ceiling_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Passport Co",
            slug=f"passport-co-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/authority-passports",
            json={"principal_id": "agent-1", "source": "org_ceiling"},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_authority_passport_get_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Passport Co 2",
            slug=f"passport-co2-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/authority-passports/missing-passport",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_authority_passport_revoke_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Passport Co 3",
            slug=f"passport-co3-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/authority-passports/missing/revoke",
            json={"reason": "cleanup"},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_upstream_trust_scan_unknown_server_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Trust Scan Co",
            slug=f"trust-scan-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers/unknown/trust/scan",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_upstream_trust_override_unknown_server_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Trust Override Co",
            slug=f"trust-ovr-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers/unknown/trust/override",
            json={"tier": "TRUSTED", "reason": "manual review"},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_upstream_trust_override_empty_reason_is_422(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Trust Reason Co",
            slug=f"trust-reason-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers/any/trust/override",
            json={"tier": "TRUSTED", "reason": ""},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_governance_evidence_verify_requires_org_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/evidence/verify")
        assert r.status_code == 400

    async def test_governance_attestation_missing_evidence_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Attest Co",
            slug=f"attest-co-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/evidence/ev-missing/attestation",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_governance_approval_votes_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Votes Co",
            slug=f"votes-co-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/approvals/missing-id/votes",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_governance_test_counter_requires_org_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/test-counter")
        assert r.status_code == 400

    async def test_governance_delegation_grant_empty_purpose_is_422(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Deleg Co",
            slug=f"deleg-co-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/delegations",
            json={
                "to_identity_id": "worker-1",
                "granted_action_types": ["read"],
                "purpose": "",
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 422


class TestLeaderboardTrustEvaluateOps:
    async def test_leaderboard_history_unknown_model_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/leaderboard/unknown-model/unknown-provider/history")
        assert r.status_code == 404

    async def test_leaderboard_diagnostic_requires_pro_plan(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Diag Co",
            slug=f"diag-co-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get(
            "/api/leaderboard/some-model/openai/diagnostic",
            headers=_bearer(raw),
        )
        assert r.status_code == 402

    async def test_leaderboard_models_requires_super_admin(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="LB Models Co",
            slug=f"lb-models-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get("/api/leaderboard/models", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_leaderboard_run_requires_super_admin(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="LB Run Co",
            slug=f"lb-run-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post("/api/leaderboard/run", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_leaderboard_run_legacy_bootstrap_key_is_forbidden(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.post(
            "/api/leaderboard/run",
            params={"model": "missing", "provider": "mock"},
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_trust_index_assess_validation_error(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/trust-index/assess",
            json={"model_name": "", "provider": "openai"},
        )
        assert r.status_code == 422

    async def test_trust_index_verify_unknown_passport_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/trust-index/verify/does-not-exist")
        assert r.status_code == 404

    async def test_trust_index_badge_unknown_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/trust-index/badge/does-not-exist.svg")
        assert r.status_code == 404

    async def test_incident_db_check_requires_pro_plan(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="IDB Check Co",
            slug=f"idb-check-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get(
            "/api/incident-db/check",
            params={"model": "gpt-4", "provider": "openai"},
            headers=_bearer(raw),
        )
        assert r.status_code == 402

    async def test_evaluate_empty_model_name_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/evaluate",
            json={"model_name": "", "provider": "openai"},
        )
        assert r.status_code == 422

    async def test_evaluate_happy_path_records_passport(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/evaluate",
            json={
                "model_name": "batch3-model",
                "provider": "openai",
                "fairness": 0.8,
                "privacy": 0.8,
                "security": 0.8,
                "robustness": 0.8,
                "compliance": 0.8,
                "authenticity": 0.8,
                "record_drift": False,
            },
        )
        assert r.status_code == 200
        assert "passport_id" in r.json()

    async def test_billing_usage_days_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage", params={"days": 0})
        assert r.status_code == 422

    async def test_audit_verify_requires_super_admin(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Verify Co",
            slug=f"audit-verify-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get("/api/audit/verify", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_audit_export_viewer_forbidden(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Export Co",
            slug=f"audit-export-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/audit/export", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_alerts_webhook_skips_non_firing_alerts(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "alerts_webhook_token", "alerts-batch3-token")
        r = await client.post(
            "/api/alerts/webhook",
            json={"alerts": [{"status": "resolved", "labels": {}, "annotations": {}}]},
            headers={"Authorization": "Bearer alerts-batch3-token"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["alerts_skipped"] == 1
        assert body["incidents_created"] == []

    async def test_health_endpoint_returns_modules(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert "modules" in body
        assert "billing" in body["modules"]

    async def test_branding_is_public(self, client: AsyncClient) -> None:
        r = await client.get("/api/branding")
        assert r.status_code == 200
        assert "brand_name" in r.json()

    async def test_support_status_operational(self, client: AsyncClient) -> None:
        r = await client.get("/api/support/status")
        assert r.status_code == 200
        assert r.json()["status"] in ("operational", "degraded")
