# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Credential negatives for the hosted MCP Streamable-HTTP transport (real client, real ASGI app).

Companion to ``tests/test_transport_credential_negatives.py`` (REST). The question in every test is
whether the tool handler ran: ``dispatch_tool`` is replaced by a spy and must stay un-awaited, and
no admission nonce may be written.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest import mock

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import select, text

from responsibleai.db.engine import governance_execution_nonces
from responsibleai.db.org_repository import OrgRepository
from responsibleai.mcp.tools import WHITEPACT_PURPOSE_ARGUMENT
from tests import test_mcp_governance_dispatch as _governance_tests
from tests.test_mcp_governance_dispatch import TEST_GOVERNANCE_PURPOSE, _client

# Re-export the fixture under its own name so pytest finds it in this module without a redefinition.
governed_app_with_key = _governance_tests.governed_app_with_key

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "negative-test", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


async def _nonce_count(engine, org_id: str) -> int:
    async with engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(governance_execution_nonces).where(
                    governance_execution_nonces.c.organization_id == org_id
                )
            )
        ).fetchall()
    return len(rows)


@pytest.fixture
def dispatch_spy(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    spy = mock.AsyncMock(return_value={"ok": True})
    monkeypatch.setattr("responsibleai.mcp.server.dispatch_tool", spy)
    return spy


async def _raw_initialize(app, authorization: str | None) -> httpx.Response:
    headers = dict(HEADERS)
    if authorization is not None:
        headers["Authorization"] = authorization
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        return await client.post("/mcp", headers=headers, json=INITIALIZE)


async def test_forged_malformed_or_missing_credentials_never_reach_a_handler(
    governed_app_with_key, dispatch_spy
) -> None:
    app, raw, org_id, engine, _key_id = governed_app_with_key
    for value in (
        None,
        "",
        "Bearer",
        "Bearer ",
        f"Bearer {raw[:-1]}{'A' if raw[-1] != 'A' else 'B'}",
        f"Bearer {raw}x",
        f"Basic {raw}",
        raw,
        "Bearer wp_live_" + "0" * 40,
    ):
        response = await _raw_initialize(app, value)
        assert response.status_code in (401, 403), (
            value,
            response.status_code,
            response.text[:200],
        )
    dispatch_spy.assert_not_awaited()
    assert await _nonce_count(engine, org_id) == 0


async def test_an_expired_key_is_refused(governed_app_with_key, dispatch_spy) -> None:
    app, raw, org_id, engine, key_id = governed_app_with_key
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE org_api_key_metadata SET expires_at = :t WHERE key_id = :id"),
            {"t": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(), "id": key_id},
        )
    response = await _raw_initialize(app, f"Bearer {raw}")
    assert response.status_code in (401, 403), response.text[:200]
    dispatch_spy.assert_not_awaited()
    assert await _nonce_count(engine, org_id) == 0


async def test_a_revoked_key_is_refused(governed_app_with_key, dispatch_spy) -> None:
    app, raw, org_id, engine, key_id = governed_app_with_key
    assert await OrgRepository(engine).revoke_key(key_id, org_id=org_id) is True
    response = await _raw_initialize(app, f"Bearer {raw}")
    assert response.status_code in (401, 403), response.text[:200]
    dispatch_spy.assert_not_awaited()


async def test_revoking_the_key_mid_session_stops_the_next_tool_call(
    governed_app_with_key, dispatch_spy
) -> None:
    """A session opened with a valid key must not outlive that key's revocation."""
    app, raw, org_id, engine, key_id = governed_app_with_key
    arguments = {WHITEPACT_PURPOSE_ARGUMENT: TEST_GOVERNANCE_PURPOSE}
    seen: dict[str, int] = {}
    refused_with: list[int] = []
    try:
        async with (
            _client(app, raw) as http_client,
            streamable_http_client("/mcp", http_client=http_client) as (read, write, _sid),
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                first = await session.call_tool("rai_health", arguments)
                assert first.isError is not True, first
                seen["calls"] = dispatch_spy.await_count
                seen["nonces"] = await _nonce_count(engine, org_id)
                assert seen["nonces"] >= 1, "the first call must really have been admitted"

                assert await OrgRepository(engine).revoke_key(key_id, org_id=org_id) is True

                second = await session.call_tool("rai_health", arguments)
                # If the transport let it through, the governed layer must still have refused it.
                body = json.loads(second.content[0].text) if second.content else {}
                assert second.isError or "error" in body, f"call succeeded after revocation: {body}"
    except* httpx.HTTPStatusError as group:
        refused_with = [e.response.status_code for e in group.exceptions]
    if refused_with:
        assert set(refused_with) <= {401, 403}, refused_with
    assert dispatch_spy.await_count == seen["calls"], "handler ran after revocation"
    assert await _nonce_count(engine, org_id) == seen["nonces"]
