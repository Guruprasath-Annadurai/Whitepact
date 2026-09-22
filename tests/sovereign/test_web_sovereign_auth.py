# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from responsibleai.db import WebIdentityRepository, create_engine
from responsibleai.governance.synthetic_counter import bind_counter_engine
from responsibleai.sovereign.api_deps import bind_sovereign_engine, bind_web_identity_repository
from responsibleai.sovereign.router import router
from responsibleai.sovereign.web_routes import web_router
from responsibleai.sovereign.zero_effect import ZeroEffectScope, consequential_invocation_count

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "sovereign-v1-web.json"


@pytest.fixture()
async def sovereign_web_app():
    engine = create_engine(":memory:")
    await engine.init()
    bind_counter_engine(engine)
    bind_sovereign_engine(engine)
    identities = WebIdentityRepository(engine)
    bind_web_identity_repository(identities)
    app = FastAPI()
    app.include_router(router)
    app.include_router(web_router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, engine, identities


async def _session(
    client: AsyncClient, identities: WebIdentityRepository, slug: str
) -> tuple[str, str]:
    user_id, verification = await identities.register(
        "Tester", f"{slug}@example.com", "Test-Password-42!"
    )
    assert await identities.verify_email(verification) is True
    org_id = await identities.attach_organization(user_id, name=slug, slug=slug)
    session_token, csrf = await identities.create_session(user_id, org_id=org_id)
    client.cookies.set("wp_session", session_token)
    client.cookies.set("wp_csrf", csrf)
    return org_id, user_id


def _contract_web_post_paths() -> list[str]:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    paths: list[str] = []
    for cap in data.get("capabilities", []):
        if cap.get("availability") not in ("AVAILABLE", "EXPERIMENTAL"):
            continue
        for ep in cap.get("endpoints", []):
            if ep["method"] == "POST" and ep["path"].startswith("/api/web/sovereign/"):
                paths.append(ep["path"])
    return sorted(set(paths))


@pytest.mark.asyncio
async def test_unauthenticated_web_post_rejected(sovereign_web_app) -> None:
    client, _, _ = sovereign_web_app
    res = await client.post("/api/web/sovereign/xray", json={})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_body_organization_id_rejected(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    await _session(client, identities, "org-a")
    res = await client.post(
        "/api/web/sovereign/xray",
        json={"organization_id": "evil-org"},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_query_organization_id_rejected(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    await _session(client, identities, "org-q")
    res = await client.post(
        "/api/web/sovereign/xray?organization_id=evil",
        json={},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_header_organization_id_rejected(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    await _session(client, identities, "org-h")
    res = await client.post(
        "/api/web/sovereign/xray",
        json={},
        headers={
            "X-WP-CSRF": client.cookies["wp_csrf"],
            "X-Organization-Id": "evil",
        },
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_cross_tenant_capsule_hidden(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    org_a, _ = await _session(client, identities, "tenant-a")
    create = await client.post(
        "/api/web/sovereign/capsules",
        json={},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert create.status_code == 200
    capsule = create.json()
    assert capsule["organization_id"] == org_a

    await _session(client, identities, "tenant-b")
    foreign = {**capsule, "organization_id": org_a}
    validate = await client.post(
        "/api/web/sovereign/capsules/validate",
        json={"capsule": foreign},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert validate.status_code == 404


@pytest.mark.asyncio
async def test_web_xray_uses_session_tenant(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    org_id, _ = await _session(client, identities, "xray-org")
    res = await client.post(
        "/api/web/sovereign/xray",
        json={},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert res.status_code == 200
    assert res.json()["graph"]["organization_id"] == org_id


@pytest.mark.asyncio
async def test_simulation_zero_effect_on_web_route(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    org_id, _ = await _session(client, identities, "sim-org")
    with ZeroEffectScope():
        before = consequential_invocation_count()
        res = await client.post(
            "/api/web/sovereign/simulate/blast-radius",
            json={"actor_identity_id": "agent-1"},
            headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        )
        assert res.status_code == 200
        assert consequential_invocation_count() == before
        assert res.json()["organization_id"] == org_id


@pytest.mark.asyncio
async def test_gauntlet_web_returns_backend_status(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    await _session(client, identities, "gauntlet-org")
    res = await client.post(
        "/api/web/sovereign/gauntlet",
        json={},
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert "cases" in body
    statuses = {c.get("status") for c in body["cases"]}
    assert statuses.issubset({"PASS", "FAIL", "ERROR", "UNAVAILABLE"})


@pytest.mark.asyncio
async def test_contract_browser_post_routes_registered(sovereign_web_app) -> None:
    client, _, identities = sovereign_web_app
    org_id, _ = await _session(client, identities, "routes-org")
    csrf = client.cookies["wp_csrf"]
    created = await client.post(
        "/api/web/sovereign/capsules",
        json={},
        headers={"X-WP-CSRF": csrf},
    )
    assert created.status_code == 200
    capsule = created.json()
    for path in _contract_web_post_paths():
        if path.endswith("/capsules/validate") or path.endswith("/capsules/reproduce"):
            payload = {"capsule": capsule}
        elif path.endswith("/explain"):
            payload = {"evidence_id": "missing-evidence"}
        elif (
            path.endswith("/trace")
            or path.endswith("/flight-recorder")
            or path.endswith("/evidence/correlate")
        ):
            payload = {"evidence_id": "missing-evidence"}
        elif path.endswith("/policy/lint") or path.endswith("/policy/diff"):
            payload = {"rules": []}
        elif path.endswith("/policy/test"):
            payload = {"cases": []}
        elif path.endswith("/policy/simulate"):
            payload = {"rules": [], "action_types": []}
        elif path.endswith("/simulate/mission"):
            payload = {"agent_id": "a", "steps": []}
        elif path.endswith("/simulate/blast-radius"):
            payload = {"actor_identity_id": "a"}
        elif path.endswith("/shadow"):
            payload = {"agent_id": "a", "action_type": "read"}
        elif path.endswith("/authority/compare") or path.endswith("/authority/drift"):
            payload = {"manifest": {"organization_id": org_id, "capabilities": []}}
        else:
            payload = {}
        res = await client.post(path, json=payload, headers={"X-WP-CSRF": csrf})
        assert res.status_code not in {401, 403, 405}, path
