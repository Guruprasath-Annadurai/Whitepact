# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Corporate HTML delivery must stay separate from protected product operations."""

import json
import re
from html import unescape
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

CONTENT = Path(__file__).parents[1] / "web" / "src" / "content"
PUBLIC = {
    **json.loads((CONTENT / "commerce.json").read_text()),
    **json.loads((CONTENT / "public-info.json").read_text()),
    **json.loads((CONTENT / "corporate.json").read_text()),
}


@pytest.mark.parametrize("page", PUBLIC.values(), ids=PUBLIC.keys())
async def test_anonymous_corporate_metadata_with_auth_enabled(page, monkeypatch):
    from responsibleai.dashboard.app import app, settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get(page["path"])
        assert response.status_code == 200
        assert f"<title>{page['title']}</title>" in response.text
        assert f'href="https://whitepact.com{page["path"]}"' in response.text
        # Public content must exist before scripts run, including when scripts
        # fail (not only when the browser activates a noscript fallback).
        headings = re.findall(r"<h1(?:\s[^>]*)?>(.*?)</h1>", response.text, re.S)
        assert len(headings) == 1
        heading_text = " ".join(unescape(re.sub(r"<[^>]*>", " ", headings[0])).split())
        assert page["heading"] in heading_text
        for attribute, value in (
            ('property="og:title"', page["title"]),
            ('property="og:description"', page["description"]),
            ('name="twitter:title"', page["title"]),
            ('name="twitter:description"', page["description"]),
        ):
            assert f'<meta {attribute} content="{value}"' in unescape(response.text)
        assert 'href="/architecture"' in response.text
        assert "Missing or invalid Authorization" not in response.text
        csp = response.headers["content-security-policy"]
        assert "script-src" in csp
        assert "unsafe-eval" not in csp
        assert (await client.head(page["path"])).status_code == 200
        # Public HTML does not make the organization data API public.
        assert (await client.get("/api/v1/web/dashboard/summary")).status_code == 401


@pytest.mark.parametrize("path", ["/api/web/evidence", "/api/v1/web/dashboard/summary"])
async def test_product_data_stays_authenticated(path):
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        assert (await client.get(path)).status_code == 401


async def test_sovereign_tenant_operation_stays_authenticated(monkeypatch):
    from responsibleai.dashboard.app import app
    from responsibleai.db import WebIdentityRepository, create_engine
    from responsibleai.sovereign import api_deps

    # ASGITransport does not run dashboard lifespan; bind the real isolated
    # repository normally installed by startup, without overriding authentication.
    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(api_deps, "_web_identity_repo", WebIdentityRepository(engine))
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            assert (await client.post("/api/web/sovereign/xray", json={})).status_code == 401
    finally:
        await engine.close()


@pytest.mark.parametrize(
    "path",
    [
        "/login",
        "/signup",
        "/dashboard",
        "/dashboard/billing",
        "/sovereign/workbench",
        "/billing/success",
        "/billing/cancelled",
    ],
)
async def test_application_shells_noindex_before_javascript(path):
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get(path)
        assert response.status_code == 200
        assert 'name="robots" content="noindex,nofollow"' in response.text
        assert 'rel="canonical" href="https://whitepact.com/"' not in response.text
        assert '"@type":"SoftwareApplication"' not in response.text


async def test_discovery_and_unknown_url_boundary():
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        discovery = (await client.get("/llms.txt")).text
        assert "# WhitePact" in discovery
        assert "independently enforced authority" in discovery
        assert "certified scoring" not in discovery
        sitemap = (await client.get("/sitemap.xml")).text
        for page in PUBLIC.values():
            assert f"https://whitepact.com{page['path']}" in sitemap
        unknown = await client.get("/corporate-page-does-not-exist")
        assert unknown.status_code == 404
        assert 'name="robots" content="noindex,nofollow"' in unknown.text
