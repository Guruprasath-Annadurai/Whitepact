# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Two simultaneous HTTP application replicas sharing PostgreSQL."""

from __future__ import annotations

import base64
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from tests.pg_test_url import isolated_pg_url
from tests.test_saml import _signed_response
from tests.test_v1_customer_journey import STRONG, _sign_idv

PORT_A = 18781
PORT_B = 18782
PORT_IDP = 18780
URL_A = f"http://127.0.0.1:{PORT_A}"
URL_B = f"http://127.0.0.1:{PORT_B}"


def _b64url(payload: dict) -> str:
    return (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _unsigned_jwt(nonce: str) -> str:
    return f"{_b64url({'alg': 'none', 'typ': 'JWT'})}.{_b64url({'sub': 'oidc-user', 'email': 'oidc.user@example.com', 'name': 'OIDC User', 'nonce': nonce})}."


def _wait_ready(url: str, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            response = httpx.get(f"{url}/ready", timeout=2.0)
            if response.status_code == 200:
                return
            last = response.status_code
        except Exception as exc:  # noqa: BLE001
            last = exc
        time.sleep(0.25)
    raise AssertionError(f"{url} did not become ready: {last}")


def _cert_pair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-idp")])
    import datetime

    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return key_pem, cert.public_bytes(serialization.Encoding.PEM).decode()


def _replica_env(
    database_url: str, cert_pem: str, session_secret: str, extra: dict[str, str] | None = None
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "WHITEPACT_DATABASE_URL": database_url,
            "RAI_DATABASE_URL": database_url,
            "WHITEPACT_AUTO_MIGRATE": "false",
            "RAI_AUTO_MIGRATE": "false",
            "WHITEPACT_AUTH_ENABLED": "true",
            "RAI_AUTH_ENABLED": "true",
            "WHITEPACT_WEB_AUTH_DEV_TOKENS": "true",
            "RAI_WEB_AUTH_DEV_TOKENS": "true",
            "WHITEPACT_WEB_SESSION_SECURE": "false",
            "RAI_WEB_SESSION_SECURE": "false",
            "WHITEPACT_ENV": "development",
            "WHITEPACT_LOG_LEVEL": "WARNING",
            "RAI_LOG_LEVEL": "WARNING",
            "PHASE7A_DISPATCHER_ENABLED": "false",
            "WHITEPACT_OIDC_ISSUER": f"http://127.0.0.1:{PORT_IDP}",
            "WHITEPACT_OIDC_CLIENT_ID": "whitepact-test",
            "WHITEPACT_OIDC_CLIENT_SECRET": "oidc-secret",
            "WHITEPACT_OIDC_SKIP_VERIFICATION": "true",
            "WHITEPACT_OIDC_REDIRECT_URI": f"{URL_A}/api/auth/callback",
            "WHITEPACT_SAML_IDP_ENTITY_ID": "test-idp",
            "WHITEPACT_SAML_IDP_SSO_URL": "https://idp.example/sso",
            "WHITEPACT_SAML_IDP_X509_CERT": cert_pem,
            "WHITEPACT_SAML_SP_ENTITY_ID": "https://whitepact.com/saml/metadata",
            "WHITEPACT_SAML_ACS_URL": f"{URL_A}/api/auth/acs",
            "WHITEPACT_SAML_SESSION_SECRET": session_secret,
            "WHITEPACT_PADDLE_WEBHOOK_SECRET": "paddle-test-placeholder",
        }
    )
    if extra:
        env.update(extra)
    return env


def _start(port: int, env: dict[str, str], log_path: Path) -> subprocess.Popen[bytes]:
    log = log_path.open("ab")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(Path(__file__).resolve().parents[1]),
        env=env,
        stdout=log,
        stderr=log,
    )


def _start_idp() -> subprocess.Popen[bytes]:
    code = r"""
from urllib.parse import parse_qs
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
app = FastAPI()
@app.get("/.well-known/openid-configuration")
async def disc():
    return {
        "issuer": "http://127.0.0.1:18780",
        "authorization_endpoint": "http://127.0.0.1:18780/authorize",
        "token_endpoint": "http://127.0.0.1:18780/token",
        "jwks_uri": "http://127.0.0.1:18780/jwks",
    }
@app.post("/token")
async def token(request: Request):
    raw = (await request.body()).decode()
    code = parse_qs(raw).get("code", [""])[0]
    return JSONResponse({"id_token": code, "access_token": "oidc-access"})
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18780, log_level="warning")
"""
    return subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parents[1]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


async def _upgrade(url: str) -> None:
    from tests.test_v1_customer_journey import _upgrade_head

    await _upgrade_head(url)


@pytest.mark.asyncio
async def test_two_http_replicas_share_durable_security_state(
    seed_runtime_authority, tmp_path
) -> None:
    """Instance A = 127.0.0.1:18781, Instance B = 127.0.0.1:18782, shared PostgreSQL."""
    key_pem, cert_pem = _cert_pair()
    session_secret = secrets.token_urlsafe(32)
    proc_a = proc_b = proc_idp = None
    log_a = tmp_path / "replica-a.log"
    log_b = tmp_path / "replica-b.log"
    async for pg_url in isolated_pg_url("wp_repl"):
        await _upgrade(pg_url)
        env = _replica_env(pg_url, cert_pem, session_secret)
        proc_idp = _start_idp()
        proc_a = _start(PORT_A, env, log_a)
        proc_b = _start(PORT_B, env, log_b)
        try:
            deadline = time.time() + 40.0
            last = None
            while time.time() < deadline:
                try:
                    response = httpx.get(
                        f"http://127.0.0.1:{PORT_IDP}/.well-known/openid-configuration",
                        timeout=2.0,
                    )
                    if response.status_code == 200:
                        break
                    last = response.status_code
                except Exception as exc:  # noqa: BLE001
                    last = exc
                time.sleep(0.25)
            else:
                raise AssertionError(f"mock IdP did not start: {last}")
            _wait_ready(URL_A)
            _wait_ready(URL_B)

            with httpx.Client(base_url=URL_A, timeout=20.0, follow_redirects=False) as a:
                with httpx.Client(base_url=URL_B, timeout=20.0, follow_redirects=False) as b:
                    register = a.post(
                        "/api/v1/web/auth/register",
                        json={
                            "full_name": "Replica Owner",
                            "email": "replica.owner@example.com",
                            "password": STRONG,
                            "accepted_terms": True,
                        },
                    )
                    assert register.status_code == 202, register.text
                    token = parse_qs(urlparse(register.json()["verification_url"]).query)["token"][
                        0
                    ]
                    assert (
                        a.post("/api/v1/web/auth/verify", json={"token": token}).status_code == 200
                    )
                    login = a.post(
                        "/api/v1/web/auth/login",
                        json={"email": "replica.owner@example.com", "password": STRONG},
                    )
                    assert login.status_code == 200
                    csrf = a.cookies["wp_csrf"]
                    onboard = a.post(
                        "/api/v1/web/onboarding",
                        headers={"X-WP-CSRF": csrf},
                        json={
                            "organization_name": "Replica Org",
                            "use_case": "Agent development",
                            "plan": "FREE",
                        },
                    )
                    assert onboard.status_code == 200, onboard.text
                    session = a.get("/api/v1/web/session")
                    user_id = session.json()["user"]["id"]
                    import datetime as dt

                    ts = dt.datetime.now(dt.UTC).isoformat()
                    payload = json.dumps(
                        {"event_id": "evt-repl", "subject_id": user_id, "outcome": "VERIFIED"},
                        separators=(",", ":"),
                    ).encode()
                    from responsibleai.enterprise.preflight import DEV_IDENTITY_WEBHOOK_SECRET

                    webhook = a.post(
                        "/api/enterprise/identity/verification/webhook",
                        content=payload,
                        headers={
                            "X-Identity-Signature": _sign_idv(
                                payload, ts, DEV_IDENTITY_WEBHOOK_SECRET
                            ),
                            "X-Identity-Timestamp": ts,
                            "Content-Type": "application/json",
                        },
                    )
                    assert webhook.status_code == 200, webhook.text
                    created = a.post(
                        "/api/v1/web/api-keys",
                        headers={"X-WP-CSRF": a.cookies["wp_csrf"]},
                        json={
                            "name": "replica-key",
                            "environment": "test",
                            "scopes": ["governance:read", "governance:write", "evidence:read"],
                        },
                    )
                    assert created.status_code == 201, created.text
                    raw_key = created.json()["api_key"]
                    key_id = created.json()["id"]

                    listed = b.get("/api/v1/web/api-keys", cookies=a.cookies)
                    assert listed.status_code == 200
                    auth_b = b.get(
                        "/api/governance/approvals",
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
                    assert auth_b.status_code == 200, auth_b.text

                    from responsibleai.db import OrgRepository, PolicyRepository, create_engine
                    from responsibleai.governance.models import GovernanceDecision
                    from responsibleai.governance.policy import PolicyRule
                    from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
                    from tests.test_v1_customer_journey import PURPOSE

                    engine = create_engine(pg_url)
                    await engine.init(auto_create_tables=False)
                    ctx = await OrgRepository(engine).authenticate(raw_key)
                    assert ctx is not None
                    org_id = session.json()["organization"]["id"]
                    await seed_runtime_authority(
                        engine,
                        organization_id=org_id,
                        principal_id=ctx.key_id,
                        action_types=(SYNTHETIC_COUNTER_TOOL,),
                        targets=(SYNTHETIC_COUNTER_TOOL,),
                        purpose=PURPOSE,
                    )
                    await PolicyRepository(engine).add_rule(
                        org_id,
                        PolicyRule(
                            rule_id="require-test-counter",
                            reason_code="TEST_COUNTER_REQUIRES_APPROVAL",
                            effect=GovernanceDecision.REQUIRE_APPROVAL,
                            action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
                        ),
                    )
                    await engine.close()
                    pending = a.post(
                        "/api/v1/governance/tools/call",
                        headers={"Authorization": f"Bearer {raw_key}"},
                        json={
                            "name": SYNTHETIC_COUNTER_TOOL,
                            "arguments": {},
                            "purpose": PURPOSE,
                        },
                    )
                    assert pending.status_code == 200, pending.text
                    approval_id = pending.json()["approval_id"]
                    inspect_b = b.get("/api/v1/web/dashboard/approvals", cookies=a.cookies)
                    assert inspect_b.status_code == 200
                    assert any(
                        item.get("approval_id") == approval_id for item in inspect_b.json()["items"]
                    )
                    resolved_b = b.post(
                        f"/api/v1/web/approvals/{approval_id}/resolve",
                        headers={"X-WP-CSRF": csrf},
                        cookies=a.cookies,
                        json={"outcome": "APPROVED"},
                    )
                    assert resolved_b.status_code == 200, resolved_b.text
                    executed_b = b.post(
                        f"/api/v1/web/approvals/{approval_id}/execute",
                        headers={"X-WP-CSRF": csrf},
                        cookies=a.cookies,
                        json={},
                    )
                    assert executed_b.status_code == 200, executed_b.text
                    counter_a = a.get(
                        "/api/v1/governance/test-counter",
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
                    assert counter_a.json()["counter"] == 1
                    assert counter_a.json()["downstream_call_count"] == 1

                    oidc = a.get("/api/auth/login/oidc")
                    assert oidc.status_code == 200, oidc.text
                    state = oidc.json()["state"]
                    authz = oidc.json()["authorization_url"]
                    nonce = parse_qs(urlparse(authz).query)["nonce"][0]
                    jwt = _unsigned_jwt(nonce)
                    callback = b.get(
                        "/api/auth/callback",
                        params={"code": jwt, "state": state},
                        cookies=oidc.cookies,
                    )
                    assert callback.status_code == 302, callback.text
                    replay_oidc = b.get(
                        "/api/auth/callback",
                        params={"code": jwt, "state": state},
                        cookies=oidc.cookies,
                    )
                    assert replay_oidc.status_code == 400

                    saml_start = a.get("/api/auth/login/saml")
                    assert saml_start.status_code == 200, saml_start.text
                    request_id = saml_start.json()["request_id"]
                    resp = _signed_response(
                        (key_pem, cert_pem),
                        in_response_to=request_id,
                        audience="https://whitepact.com/saml/metadata",
                    )
                    acs = b.post("/api/auth/acs", data={"SAMLResponse": resp})
                    assert acs.status_code == 302, acs.text
                    replay_saml = b.post("/api/auth/acs", data={"SAMLResponse": resp})
                    assert replay_saml.status_code == 400

                    rotated = a.post(
                        f"/api/v1/web/api-keys/{key_id}/rotate",
                        headers={"X-WP-CSRF": a.cookies["wp_csrf"]},
                    )
                    assert rotated.status_code == 200
                    new_raw = rotated.json()["api_key"]
                    old_on_b = b.get(
                        "/api/governance/approvals",
                        headers={"Authorization": f"Bearer {raw_key}"},
                    )
                    assert old_on_b.status_code == 401
                    new_on_b = b.get(
                        "/api/governance/approvals",
                        headers={"Authorization": f"Bearer {new_raw}"},
                    )
                    assert new_on_b.status_code == 200
                    revoked = a.delete(
                        f"/api/v1/web/api-keys/{rotated.json()['id']}",
                        headers={"X-WP-CSRF": a.cookies["wp_csrf"]},
                    )
                    assert revoked.status_code == 200
                    after_revoke = b.get(
                        "/api/governance/approvals",
                        headers={"Authorization": f"Bearer {new_raw}"},
                    )
                    assert after_revoke.status_code == 401

                    evidence_a = a.get("/api/v1/web/dashboard/evidence")
                    evidence_b = b.get("/api/v1/web/dashboard/evidence", cookies=a.cookies)
                    assert evidence_a.status_code == 200
                    assert evidence_b.status_code == 200
                    assert evidence_a.json()["items"] == evidence_b.json()["items"]
                    approvals_b = b.get("/api/v1/web/dashboard/approvals", cookies=a.cookies)
                    assert approvals_b.status_code == 200

                    last = None
                    for i in range(21):
                        client = a if i % 2 == 0 else b
                        last = client.get(
                            "/api/governance/approvals",
                            headers={"Authorization": "Bearer totally-invalid-key"},
                        )
                        if last.status_code == 429:
                            break
                    assert last is not None and last.status_code == 429, (
                        last.text if last else "no response"
                    )

                    proc_a.terminate()
                    proc_a.wait(timeout=10)
                    still = b.get("/api/v1/web/session", cookies=a.cookies)
                    assert still.status_code == 200
                    assert still.json()["organization"]["name"] == "Replica Org"
        finally:
            for proc in (proc_a, proc_b, proc_idp):
                if proc is None:
                    continue
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
        return
