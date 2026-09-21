# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from responsibleai.db import create_engine
from responsibleai.sovereign.api_deps import bind_sovereign_engine
from responsibleai.sovereign.router import router
from fastapi import FastAPI


@pytest.fixture()
async def api_client():
    engine = create_engine(":memory:")
    await engine.init()
    bind_sovereign_engine(engine)
    app = FastAPI()
    app.include_router(router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    bind_sovereign_engine(engine)  # keep bound


@pytest.mark.asyncio
async def test_api_status(api_client: AsyncClient) -> None:
    res = await api_client.get("/api/sovereign/status")
    assert res.status_code == 200
    body = res.json()
    assert "sovereign_version" in body


@pytest.mark.asyncio
async def test_api_capabilities(api_client: AsyncClient) -> None:
    res = await api_client.get("/api/sovereign/capabilities")
    assert res.status_code == 200
