#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Attempt actual HTTP customer onboarding on disposable PostgreSQL; no authority seed.

Email delivery uses a real local webhook receiver, not a mocked provider or
development-token response. This does not qualify external email delivery.
Exit 2 records an incomplete mandatory golden journey; it is never a success.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import socket
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route
from tests.pg_test_url import isolated_pg_url

import responsibleai.dashboard.app as dashboard
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic


@asynccontextmanager
async def serve(app):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(30):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("Local application stopped before startup")
                await asyncio.sleep(0.01)
        yield f"http://localhost:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 30)
        listener.close()


async def attempt() -> dict:
    steps = []
    mail = []
    delivery_secret = secrets.token_urlsafe(32)

    async def deliver(request):
        if request.headers.get("authorization") != f"Bearer {delivery_secret}":
            return Response(status_code=403)
        mail.append(await request.json())
        return Response(status_code=204)

    def confirmed(name, response, expected):
        steps.append({"step": name, "http_status": response.status_code})
        if response.status_code != expected:
            raise RuntimeError(f"{name}: expected HTTP {expected}, got {response.status_code}")
        steps[-1]["result"] = "CONFIRMED"

    async for database in isolated_pg_url("wp_m13i1_real_journey"):
        ini = _find_alembic_ini()
        if ini is None:
            raise RuntimeError("Migration configuration unavailable")
        await _run_alembic(ini, _migration_env(database), "upgrade", "head")
        steps.append({"step": "fresh_postgresql_migration", "result": "CONFIRMED"})
        async with serve(
            Starlette(routes=[Route("/deliver", deliver, methods=["POST"])])
        ) as mailbox:
            changes = {
                "database_url": database,
                "auto_migrate": False,
                "auth_enabled": True,
                "api_keys": [],
                "environment": "development",
                "web_auth_dev_tokens": False,
                "web_session_secure": False,
                "web_verification_delivery_url": f"{mailbox}/deliver",
                "web_verification_delivery_token": delivery_secret,
            }
            previous = {key: getattr(dashboard.settings, key) for key in changes}
            try:
                for key, value in changes.items():
                    setattr(dashboard.settings, key, value)
                async with serve(dashboard.app) as origin:
                    credentials = {
                        "full_name": "Independent Customer",
                        "email": f"m13i1-{secrets.token_hex(6)}@example.com",
                        "password": f"Local-Journey-{secrets.token_urlsafe(24)}-42!",
                    }
                    async with httpx.AsyncClient(base_url=origin, timeout=30) as client:
                        response = await client.post(
                            "/api/v1/web/auth/register",
                            json={**credentials, "accepted_terms": True},
                        )
                        confirmed("signup", response, 202)
                        if "verification_url" in response.json() or len(mail) != 1:
                            raise RuntimeError("Expected genuine local email delivery only")
                        token = parse_qs(urlparse(mail[0]["verification_url"]).query)["token"][0]
                        response = await client.post(
                            "/api/v1/web/auth/verify", json={"token": token}
                        )
                        confirmed("backend_generated_email_verification", response, 200)
                        response = await client.post("/api/v1/web/auth/login", json=credentials)
                        confirmed("password_login", response, 200)
                        csrf = client.cookies.get("wp_csrf")
                        if not csrf or not client.cookies.get("wp_session"):
                            raise RuntimeError("Actual authenticated cookies unavailable")
                        response = await client.post(
                            "/api/v1/web/onboarding",
                            headers={"X-WP-CSRF": csrf},
                            json={
                                "organization_name": "Independent Customer Org",
                                "use_case": "M13 integration qualification",
                                "plan": "FREE",
                            },
                        )
                        confirmed("organization_onboarding", response, 200)
                        response = await client.get("/api/v1/web/session")
                        confirmed("authenticated_owner_session", response, 200)
                        session = response.json()
                        organization = session.get("organization") or {}
                        if organization.get("role") != "OWNER" or not organization.get("id"):
                            raise RuntimeError("Server did not confirm actual owner membership")
                        base = f"/api/enterprise/organizations/{organization['id']}/authority"
                        for name, path in [
                            ("root_status_read", f"{base}/status"),
                            ("agent_inventory_read", f"{base}/agents"),
                        ]:
                            response = await client.get(path)
                            confirmed(name, response, 200)
                        response = await client.post(
                            "/api/enterprise/passkeys/register/begin",
                            headers={"X-WhitePact-CSRF": csrf},
                        )
                        confirmed("passkey_registration_challenge", response, 200)
                        expected_origin = response.json().get("origin")
                        blocker = "REAL_AUTHENTICATOR_CEREMONY_NOT_COMPLETED"
                        if expected_origin != origin:
                            blocker = "WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN"
                        steps.append(
                            {
                                "step": "passkey_registration",
                                "result": "BLOCKED",
                                "reason": blocker,
                                "application_origin": origin,
                                "server_expected_origin": expected_origin,
                            }
                        )
                        response = await client.post(
                            "/api/v1/web/auth/logout", headers={"X-WP-CSRF": csrf}
                        )
                        confirmed("actual_session_revocation", response, 200)
                        response = await client.get("/api/v1/web/session")
                        confirmed("revoked_session_refused", response, 401)
            finally:
                for key, value in previous.items():
                    setattr(dashboard.settings, key, value)
    return {
        "kind": "ACTUAL_HTTP_POSTGRESQL_CUSTOMER_JOURNEY_ATTEMPT",
        "acceptance": "BLOCKED",
        "production": "GLOBAL PRODUCTION NO-GO",
        "steps": steps,
        "not_executed": [
            "passkey_finish",
            "consent",
            "root_bootstrap",
            "application",
            "agent_registration",
            "delegation",
            "approval",
            "controlled_action",
            "execution_evidence",
            "authority_revocation",
        ],
        "limitations": [
            "Local webhook email receipt is not external email deliverability",
            "No root, passkey, consent, delegation or execution is seeded or mocked",
            "Session revocation is not authority revocation",
        ],
    }


if __name__ == "__main__":
    try:
        result = asyncio.run(attempt())
    except Exception as error:
        # Never print response bodies, credentials, mail URLs or verification tokens.
        result = {
            "acceptance": "BLOCKED",
            "error_type": type(error).__name__,
            "reason": str(error)
            if isinstance(error, RuntimeError)
            else "Execution failed; inspect local diagnostics without exposing credentials",
        }
    print(json.dumps(result, indent=2))
    raise SystemExit(2)
