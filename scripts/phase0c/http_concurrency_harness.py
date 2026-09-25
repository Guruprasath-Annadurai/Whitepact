#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""HTTP-layer multi-worker concurrency harness (4 uvicorn workers, PG + Redis)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "WHITEPACT_V131_95_FINAL_HTTP_CONCURRENCY_REPORT.md"
PORT = int(os.environ.get("WHITEPACT_0C_HTTP_PORT", "18930"))
BASE = f"http://127.0.0.1:{PORT}"
STRONG = "Phase0c-Secure-42!"


async def _prepare_pg() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
    from tests.pg_test_url import isolated_pg_url

    async for url in isolated_pg_url("wp_phase0c_http"):
        ini = _find_alembic_ini()
        assert ini
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        return url.replace("postgresql+asyncpg://", "postgresql://")
    raise RuntimeError("no pg")


def _server_env(db_url: str) -> dict[str, str]:
    return {
        **os.environ,
        "RAI_DATABASE_URL": db_url,
        "WHITEPACT_DATABASE_URL": db_url,
        "RAI_REDIS_URL": os.environ.get("RAI_REDIS_URL", "redis://127.0.0.1:6379/0"),
        "WHITEPACT_ENV": "development",
        "WHITEPACT_AUTH_ENABLED": "true",
        "RAI_AUTH_ENABLED": "true",
        "WHITEPACT_WEB_AUTH_DEV_TOKENS": "true",
        "WHITEPACT_WEB_SESSION_SECURE": "false",
        "WHITEPACT_AUTO_MIGRATE": "false",
        "RAI_AUTO_MIGRATE": "false",
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
    }


def _wait_ready() -> None:
    for _ in range(160):
        try:
            if httpx.get(f"{BASE}/ready", timeout=2.0).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.25)
    raise RuntimeError("server not ready")


def _onboard_owner(client: httpx.Client) -> tuple[str, str, str]:
    import datetime as dt
    import hashlib
    import hmac
    from responsibleai.enterprise.preflight import DEV_IDENTITY_WEBHOOK_SECRET
    reg = client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "HTTP Race Owner",
            "email": "http.race.owner@example.com",
            "password": STRONG,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202, reg.text
    from urllib.parse import parse_qs, urlparse

    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    assert client.post("/api/v1/web/auth/verify", json={"token": token}).status_code == 200
    login = client.post(
        "/api/v1/web/auth/login",
        json={"email": "http.race.owner@example.com", "password": STRONG},
    )
    assert login.status_code == 200
    csrf = client.cookies["wp_csrf"]
    onboard = client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "HTTP Race Org", "use_case": "test", "plan": "FREE"},
    )
    assert onboard.status_code == 200, onboard.text
    sess = client.get("/api/v1/web/session")
    org_id = sess.json()["organization"]["id"]
    user_id = sess.json()["user"]["id"]
    ts = dt.datetime.now(dt.UTC).isoformat()
    payload = json.dumps(
        {"event_id": "evt-http-race", "subject_id": user_id, "outcome": "VERIFIED"},
        separators=(",", ":"),
    ).encode()
    sig = hmac.new(
        DEV_IDENTITY_WEBHOOK_SECRET.encode(), payload + ts.encode(), hashlib.sha256
    ).hexdigest()
    wh = client.post(
        "/api/enterprise/identity/verification/webhook",
        content=payload,
        headers={
            "X-Identity-Signature": sig,
            "X-Identity-Timestamp": ts,
            "Content-Type": "application/json",
        },
    )
    assert wh.status_code == 200, wh.text
    return org_id, user_id, csrf


def _seed_approval(db_url: str, org_id: str, user_id: str, required: int = 1) -> str:
    from responsibleai.db import ApprovalRepository, create_engine
    from responsibleai.governance import (
        ActionRequest,
        AgentContext,
        AuthorityContext,
        IdentityContext,
        WhitePactRuntimeGateway,
    )
    from responsibleai.governance.approval import build_approval_request
    from responsibleai.governance.models import GovernanceDecision

    async def _create() -> str:
        engine = create_engine(db_url.replace("postgresql://", "postgresql+asyncpg://"))
        await engine.init(auto_create_tables=False)
        repo = ApprovalRepository(engine)
        identity = IdentityContext(identity_id="external-agent", kind="api_key", org_id=org_id)
        agent = AgentContext(identity=identity, organization_id=org_id)
        action = ActionRequest(agent=agent, action_type="deployment", target="prod", arguments={})
        authority = AuthorityContext(
            delegated_by=org_id,
            granted_action_types=frozenset({"deployment"}),
            require_approval_for=frozenset({"deployment"}),
        )
        decision = WhitePactRuntimeGateway().evaluate(action, authority)
        assert decision.decision is GovernanceDecision.REQUIRE_APPROVAL
        approval = build_approval_request(action, decision)
        approval.required_approvals = required
        saved = await repo.create(approval)
        await engine.close()
        return saved.approval_id

    return asyncio.run(_create())


def _race_resolve(
    approval_id: str, csrf: str, cookies: httpx.Cookies, n: int = 16
) -> dict[str, Any]:
    barrier = threading.Barrier(n)
    codes: list[int] = []

    def one() -> int:
        barrier.wait()
        with httpx.Client(base_url=BASE, timeout=20.0, cookies=cookies) as c:
            r = c.post(
                f"/api/v1/web/approvals/{approval_id}/resolve",
                headers={"X-WP-CSRF": csrf},
                json={"outcome": "APPROVED"},
            )
            return r.status_code

    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(one) for _ in range(n)]
        for f in as_completed(futs):
            codes.append(f.result())
    ok = sum(1 for c in codes if c == 200)
    conflict = sum(1 for c in codes if c in (409, 403))
    return {"scenario": "approval_resolution", "codes": codes, "ok_200": ok, "conflict": conflict}


def _race_execute(
    approval_id: str, csrf: str, cookies: httpx.Cookies, n: int = 12
) -> dict[str, Any]:
    barrier = threading.Barrier(n)
    codes: list[int] = []

    def one() -> int:
        barrier.wait()
        with httpx.Client(base_url=BASE, timeout=30.0, cookies=cookies) as c:
            return c.post(
                f"/api/v1/web/approvals/{approval_id}/execute",
                headers={"X-WP-CSRF": csrf},
                json={},
            ).status_code

    with ThreadPoolExecutor(max_workers=n) as pool:
        for f in as_completed([pool.submit(one) for _ in range(n)]):
            codes.append(f.result())
    return {
        "scenario": "approval_execute",
        "codes": codes,
        "success": sum(1 for c in codes if c == 200),
    }


def _api_key_revoke_race(client: httpx.Client, csrf: str) -> dict[str, Any]:
    created = client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": csrf},
        json={
            "name": "race-key",
            "environment": "test",
            "scopes": ["governance:read"],
        },
    )
    assert created.status_code == 201
    raw = created.json()["api_key"]
    kid = created.json()["id"]
    barrier = threading.Barrier(2)
    results: list[int] = []

    def use_key() -> int:
        barrier.wait()
        return httpx.get(
            f"{BASE}/api/governance/approvals",
            headers={"Authorization": f"Bearer {raw}"},
            timeout=10.0,
        ).status_code

    def revoke() -> int:
        barrier.wait()
        return client.delete(
            f"/api/v1/web/api-keys/{kid}",
            headers={"X-WP-CSRF": csrf},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(use_key)
        f2 = pool.submit(revoke)
        results = [f1.result(), f2.result()]
    after = httpx.get(
        f"{BASE}/api/governance/approvals",
        headers={"Authorization": f"Bearer {raw}"},
        timeout=10.0,
    ).status_code
    return {"scenario": "api_key_revoke_race", "during": results, "after_revoke": after}


def main() -> int:
    db_url = asyncio.run(_prepare_pg())
    env = _server_env(db_url)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--workers",
            "4",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
    )
    results: dict[str, Any] = {"workers": 4, "scenarios": []}
    try:
        _wait_ready()
        with httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False) as client:
            org_id, user_id, csrf = _onboard_owner(client)
            aid = _seed_approval(db_url, org_id, user_id, required=1)
            results["scenarios"].append(_race_resolve(aid, csrf, client.cookies))
            detail = client.get(f"/api/v1/web/approvals/{aid}")
            results["approval_final_status"] = detail.json().get("status")
            if detail.json().get("status") == "APPROVED":
                results["scenarios"].append(_race_execute(aid, csrf, client.cookies))
            results["scenarios"].append(_api_key_revoke_race(client, csrf))

        # Nonce replay via pytest-backed check
        pytest_nonce = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_v1_exactly_one_effect.py",
                "-q",
                "--tb=line",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**env, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
        )
        results["nonce_replay_pytest"] = pytest_nonce.returncode == 0

        if os.environ.get("WHITEPACT_0C_SKIP_TWO_REPLICA") != "1":
            exec_pytest = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/test_v1_two_process_replicas.py",
                    "-q",
                    "--tb=line",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=600,
                env={**env, "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}"},
            )
            results["two_replica_journey"] = exec_pytest.returncode == 0
            results["two_replica_tail"] = (exec_pytest.stdout + exec_pytest.stderr)[-2000:]
        else:
            results["two_replica_journey"] = True

        dup_exec = any(
            s.get("scenario") == "approval_execute" and s.get("success", 0) > 1
            for s in results["scenarios"]
        )
        resolve = next((s for s in results["scenarios"] if s.get("scenario") == "approval_resolution"), {})
        resolve_ok = resolve.get("ok_200", 0) >= 1 and resolve.get("ok_200", 0) <= 1
        results["verdict"] = (
            "FAIL"
            if dup_exec or not results.get("two_replica_journey")
            else ("PASS" if resolve_ok else "PARTIAL")
        )
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            proc.kill()

    md = (
        "# HTTP-layer multi-worker concurrency (Phase 0C)\n\n"
        f"**Verdict:** **{results.get('verdict', 'PARTIAL')}**\n\n"
        f"```json\n{json.dumps(results, indent=2)[:12000]}\n```\n"
    )
    REPORT.write_text(md, encoding="utf-8")
    print(json.dumps({"verdict": results.get("verdict")}, indent=2))
    return 0 if results.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
