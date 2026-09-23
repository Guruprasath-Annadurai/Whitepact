# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Public commerce routes must work before JavaScript and without authentication."""

import re

import pytest
from httpx import ASGITransport, AsyncClient

PAGES = {
    "/": "WhitePact — Runtime Governance for AI Agents",
    "/pricing": "Pricing | WhitePact",
    "/terms": "Terms of Service | WhitePact",
    "/privacy": "Privacy Policy | WhitePact",
    "/refund-policy": "Refund Policy | WhitePact",
}


@pytest.mark.parametrize("path,title", PAGES.items())
async def test_commerce_public_html_metadata_fallback_and_footer(path, title):
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.get(path)
        assert response.status_code == 200
        assert f"<title>{title}</title>" in response.text
        assert f'rel="canonical" href="https://whitepact.com{path}"' in response.text
        assert '<meta name="robots" content="index, follow"' in response.text
        assert "<noscript>" in response.text and "<h1>" in response.text
        assert not re.search(r"\b(TODO|TBD|placeholder|lorem ipsum)\b", response.text, re.I)
        for destination in list(PAGES)[1:]:
            assert f'href="{destination}"' in response.text
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "content-security-policy" in response.headers
        assert (await client.head(path)).status_code == 200


async def test_commerce_sitemap_redirect_and_real_404():
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        sitemap = (await client.get("/sitemap.xml")).text
        for path in PAGES:
            assert f"<loc>https://whitepact.com{path}</loc>" in sitemap
        assert "/refunds" not in sitemap
        for method in (client.get, client.head):
            response = await method("/refunds", follow_redirects=False)
            assert response.status_code in (301, 308)
            assert response.headers["location"] == "/refund-policy"
            assert (await method("/definitely-does-not-exist")).status_code == 404
        robots = (await client.get("/robots.txt")).text
        assert "Allow: /" in robots
        assert not any(f"Disallow: {path}" in robots for path in list(PAGES)[1:])


async def test_sovereign_public_metadata_and_workbench_shell_are_hosted():
    from responsibleai.dashboard.app import app

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        public = await client.get("/sovereign")
        assert public.status_code == 200
        assert "<title>WhitePact Sovereign | Authority analysis workbench</title>" in public.text
        assert 'rel="canonical" href="https://whitepact.com/sovereign"' in public.text
        assert "See authority before it becomes action." in public.text

        workbench = await client.get("/sovereign/workbench")
        assert workbench.status_code == 200
        assert '<div id="root"></div>' in workbench.text
        assert (await client.head("/sovereign/workbench")).status_code == 200
