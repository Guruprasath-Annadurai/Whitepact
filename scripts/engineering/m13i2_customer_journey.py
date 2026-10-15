#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reusable actual HTTP/PG customer acceptance attempt; no authentication seeds.

Backend-generated verification mail is received by a real local HTTP webhook.
No external messages are sent. An incomplete golden journey always exits 2.
The M13-I1 harness and its configured-origin failure remain unchanged.
"""
from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import contextmanager
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import httpx
from scripts.engineering.m13i1_customer_journey import serve
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from tests.pg_test_url import isolated_pg_url

import responsibleai.dashboard.app as dashboard
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic

DOWNSTREAM = (
    "passkey_finish", "consent", "root_bootstrap", "application", "agent_registration",
    "delegation", "approval", "controlled_action", "execution_evidence", "authority_revocation",
)


class JourneyStoppedError(RuntimeError):
    """An expectation failed; response bodies and credentials are never included."""


@dataclass
class JourneyEvidence:
    phases: list[dict] = field(default_factory=list)

    def check(self, phase: str, response: httpx.Response, expected: int, invariant=True):
        try:
            invariant = invariant() if callable(invariant) else invariant
        except Exception as cause:
            self.phases.append({"phase": phase, "result": "BLOCKED",
                                "http_status": response.status_code,
                                "expected_status": expected, "invariant_confirmed": False,
                                "reason": type(cause).__name__})
            raise JourneyStoppedError(f"{phase}: semantic contract could not be parsed") from None
        accepted = response.status_code == expected and invariant is True
        self.phases.append({"phase": phase, "result": "CONFIRMED" if accepted else "BLOCKED",
                            "http_status": response.status_code,
                            "expected_status": expected, "invariant_confirmed": invariant is True})
        if not accepted:
            raise JourneyStoppedError(f"{phase}: HTTP status or semantic contract not confirmed")

    def report(self) -> dict:
        return {"kind": "ACTUAL_HTTP_POSTGRESQL_CUSTOMER_JOURNEY_ATTEMPT",
                "acceptance": "BLOCKED", "production": "GLOBAL PRODUCTION NO-GO",
                "phases": self.phases, "not_executed": list(DOWNSTREAM),
                "limitations": ["Local email capture is not external deliverability",
                                "No fake authenticator, auth success or seeded authority",
                                "Session revocation is not authority revocation"]}


@contextmanager
def configured_settings(changes):
    previous = {key: getattr(dashboard.settings, key) for key in changes}
    try:
        for key, value in changes.items():
            setattr(dashboard.settings, key, value)
        yield
    finally:
        for key, value in previous.items():
            setattr(dashboard.settings, key, value)


async def run_journey() -> dict:
    evidence = JourneyEvidence()
    mail = []
    delivery_secret = secrets.token_urlsafe(32)

    async def deliver(request):
        if request.headers.get("authorization") != f"Bearer {delivery_secret}":
            return Response(status_code=403)
        mail.append(await request.json())
        return Response(status_code=204)

    try:
        async for database in isolated_pg_url("wp_m13i2_actual_journey"):
            ini = _find_alembic_ini()
            if ini is None:
                raise JourneyStoppedError("Migration configuration unavailable")
            await _run_alembic(ini, _migration_env(database), "upgrade", "head")
            evidence.phases.append({"phase": "fresh_postgresql_migration", "result": "CONFIRMED"})
            async with serve(Starlette(routes=[Route("/deliver", deliver, methods=["POST"])])) as mailbox:
                changes = {
                    "database_url": database, "auto_migrate": False, "auth_enabled": True,
                    "api_keys": [], "environment": "development", "web_auth_dev_tokens": False,
                    "web_session_secure": False,
                    "web_verification_delivery_url": f"{mailbox}/deliver",
                    "web_verification_delivery_token": delivery_secret,
                }
                with configured_settings(changes):
                    async with serve(dashboard.app) as origin:
                        async with httpx.AsyncClient(base_url=origin, timeout=30) as client:
                            await account_and_organization(client, mail, evidence)
                            await passkey_boundary_and_revocation(client, origin, evidence)
    except Exception as cause:
        evidence.phases.append({"phase": "harness_stop", "result": "BLOCKED",
                                "reason": type(cause).__name__})
    return evidence.report()


async def account_and_organization(client, mail, evidence):
    credentials = {"full_name": "Actual I2 Customer",
                   "email": f"m13i2-{secrets.token_hex(6)}@example.com",
                   "password": f"Actual-Journey-{secrets.token_urlsafe(24)}-42!"}
    response = await client.get("/api/v1/web/session")
    evidence.check("unauthenticated_session", response, 401)
    response = await client.post("/api/v1/web/auth/register",
                                 json={**credentials, "accepted_terms": True})
    evidence.check("signup", response, 202,
                   lambda: response.json().get("status") == "verification_required"
                   and "verification_url" not in response.json() and len(mail) == 1)
    token = parse_qs(urlparse(mail[0]["verification_url"]).query)["token"][0]
    response = await client.post("/api/v1/web/auth/verify", json={"token": token})
    evidence.check("backend_generated_email_verification", response, 200,
                   lambda: response.json().get("status") == "verified")
    response = await client.post("/api/v1/web/auth/login", json=credentials)
    evidence.check("password_login", response, 200,
                   bool(client.cookies.get("wp_csrf") and client.cookies.get("wp_session")))
    response = await client.get("/api/v1/web/session")
    evidence.check("first_run_session", response, 200,
                   lambda: response.json().get("organization") is None
                   and response.json().get("user", {}).get("email") == credentials["email"])
    response = await client.post("/api/v1/web/onboarding",
                                 headers={"X-WP-CSRF": client.cookies.get("wp_csrf")},
                                 json={"organization_name": "Actual I2 Customer Org",
                                       "use_case": "Local integration acceptance", "plan": "FREE"})
    evidence.check("organization_onboarding", response, 200,
                   lambda: response.json().get("next") == "/dashboard")


async def passkey_boundary_and_revocation(client, origin, evidence):
    response = await client.get("/api/v1/web/session")
    evidence.check("authenticated_owner_session", response, 200,
                   lambda: response.json().get("organization", {}).get("role") == "OWNER"
                   and bool(response.json().get("organization", {}).get("id")))
    organization = response.json()["organization"]
    org_id = organization["id"]
    response = await client.get("/api/v1/web/session")
    evidence.check("safe_session_reload", response, 200,
                   lambda: response.json().get("organization", {}).get("id") == org_id)
    base = f"/api/enterprise/organizations/{org_id}/authority"
    response = await client.get(f"{base}/status")
    evidence.check("root_status_read", response, 200,
                   lambda: response.json().get("has_active_authority") is False)
    response = await client.get(f"{base}/agents")
    evidence.check("agent_inventory_read", response, 200, lambda: response.json().get("agents") == [])
    csrf = client.cookies.get("wp_csrf")
    response = await client.post("/api/enterprise/passkeys/register/begin",
                                 headers={"X-WhitePact-CSRF": csrf})
    evidence.check("passkey_registration_challenge", response, 200,
                   lambda: bool(response.json().get("challenge")))
    expected_origin = response.json().get("origin")
    reason = ("WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN"
              if expected_origin != origin else "REAL_AUTHENTICATOR_CEREMONY_NOT_COMPLETED")
    evidence.phases.append({"phase": "passkey_registration", "result": "BLOCKED",
                            "reason": reason, "application_origin": origin,
                            "server_expected_origin": expected_origin})
    # A blocked privileged ceremony does not prevent genuine account revocation checks.
    session_token = client.cookies.get("wp_session")
    response = await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": csrf})
    evidence.check("actual_session_revocation", response, 200,
                   lambda: response.json().get("status") == "signed_out")
    response = await client.get("/api/v1/web/session")
    evidence.check("revoked_session_refused", response, 401)
    response = await client.get("/api/v1/web/session", headers={"Cookie": f"wp_session={session_token}"})
    evidence.check("revoked_cookie_replay_refused", response, 401)


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_journey()), indent=2))
    raise SystemExit(2)
