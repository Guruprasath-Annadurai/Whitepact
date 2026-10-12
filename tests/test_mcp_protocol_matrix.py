# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Protocol behaviour of the hosted MCP Streamable-HTTP endpoint, observed against the real app.

This is what the versioned compatibility matrix in ``docs/launch/MCP_COMPATIBILITY_MATRIX.md`` is built
from. It does not claim conformance to a specification the pinned SDK does not implement: it records what
the server does when a client offers each protocol version, and checks the behaviours that matter for
safety (authentication on every request, validation before dispatch, no handler run on a bad request).
"""

from __future__ import annotations

import json
import re
from unittest import mock

import httpx
import pytest
from jsonschema import Draft202012Validator

from responsibleai.mcp.tools import TOOL_DEFS
from tests import test_mcp_governance_dispatch as _gov

governed_app_with_key = _gov.governed_app_with_key

ACCEPT = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
SUPPORTED_BY_PINNED_SDK = ["2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"]


def _rpc(method: str, params: dict | None = None, *, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, **({"params": params} if params else {})}


def _initialize(version: str) -> dict:
    return _rpc(
        "initialize",
        {
            "protocolVersion": version,
            "capabilities": {},
            "clientInfo": {"name": "matrix", "version": "0"},
        },
    )


def _parse(response: httpx.Response) -> dict | None:
    text = response.text.strip()
    if not text:
        return None
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _refused(body: dict) -> bool:
    """A JSON-RPC error, an isError result, or a structured {"error": ...} payload in the content."""
    if "error" in body:
        return True
    result = body.get("result", {})
    if result.get("isError") is True:
        return True
    for item in result.get("content", []):
        try:
            if "error" in json.loads(item.get("text", "{}")):
                return True
        except ValueError:
            continue
    return False


async def _post(app, raw: str | None, body, headers: dict | None = None) -> httpx.Response:
    h = dict(ACCEPT)
    if raw is not None:
        h["Authorization"] = f"Bearer {raw}"
    h.update(headers or {})
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        if isinstance(body, str | bytes):
            return await client.post("/mcp", headers=h, content=body)
        return await client.post("/mcp", headers=h, json=body)


@pytest.mark.parametrize("version", SUPPORTED_BY_PINNED_SDK)
async def test_every_version_the_pinned_sdk_supports_is_negotiated_as_offered(
    governed_app_with_key, version: str
) -> None:
    app, raw, *_ = governed_app_with_key
    response = await _post(app, raw, _initialize(version))
    assert response.status_code == 200, response.text
    result = _parse(response)["result"]
    assert result["protocolVersion"] == version
    assert result["serverInfo"]["name"]
    assert "tools" in result["capabilities"]


@pytest.mark.parametrize("version", ["2026-07-28", "2099-01-01", "not-a-version", ""])
async def test_a_version_the_sdk_does_not_implement_is_answered_with_one_it_does(
    governed_app_with_key, version: str
) -> None:
    """The 2026-07-28 specification is NOT implemented by the pinned SDK (mcp < 2.0). The server must
    negotiate down to a version it does speak, never claim the one it does not."""
    app, raw, *_ = governed_app_with_key
    response = await _post(app, raw, _initialize(version))
    assert response.status_code == 200, response.text
    negotiated = _parse(response)["result"]["protocolVersion"]
    assert negotiated in SUPPORTED_BY_PINNED_SDK
    assert negotiated != "2026-07-28"


async def test_tools_list_matches_the_definitions_and_every_schema_is_valid_json_schema(
    governed_app_with_key,
) -> None:
    app, raw, *_ = governed_app_with_key
    response = await _post(app, raw, _rpc("tools/list"))
    assert response.status_code == 200, response.text
    tools = _parse(response)["result"]["tools"]
    names = [t["name"] for t in tools]
    # TOOL_DEFS also holds the test-only fixture; it is deliberately not advertised to clients.
    # A governed hosted connection additionally advertises the four read-only authority tools.
    from responsibleai.mcp.authority_tools import AUTHORITY_TOOL_NAMES

    advertised = sorted(
        [d.name for d in TOOL_DEFS if d.name != "test.counter.increment"]
        + sorted(AUTHORITY_TOOL_NAMES)
    )
    assert sorted(names) == advertised
    assert "test.counter.increment" not in names
    assert len(names) == len(set(names)), "duplicate tool name"
    assert len(tools) == len(TOOL_DEFS) - 1 + 4 == 34
    for tool in tools:
        assert re.fullmatch(r"[A-Za-z0-9_.\-]{1,64}", tool["name"]), tool["name"]
        assert tool.get("description"), tool["name"]
        Draft202012Validator.check_schema(tool["inputSchema"])
        assert tool["inputSchema"].get("type") == "object", tool["name"]


async def test_resources_list_reports_the_declared_resources(governed_app_with_key) -> None:
    from responsibleai.mcp import resources

    app, raw, *_ = governed_app_with_key
    response = await _post(app, raw, _rpc("resources/list"))
    assert response.status_code == 200, response.text
    listed = _parse(response)["result"]["resources"]
    assert len(listed) == len(resources.RESOURCE_DEFS) == 20
    assert len({str(r["uri"]) for r in listed}) == len(listed)


@pytest.mark.parametrize(
    "arguments",
    [{"text": 123}, {"text": ["a"]}, {"unexpected": True}, {}, {"text": None}],
)
async def test_invalid_arguments_are_rejected_before_any_handler_runs(
    governed_app_with_key, arguments: dict
) -> None:
    app, raw, org_id, engine, _key = governed_app_with_key
    with mock.patch("responsibleai.mcp.server.dispatch_tool", new=mock.AsyncMock()) as spy:
        response = await _post(
            app, raw, _rpc("tools/call", {"name": "rai_scan", "arguments": arguments})
        )
        body = _parse(response)
    assert response.status_code < 500, response.text
    assert body is not None
    assert _refused(body), body
    spy.assert_not_awaited()


async def test_unknown_tool_and_unknown_method_are_errors_not_crashes(
    governed_app_with_key,
) -> None:
    app, raw, *_ = governed_app_with_key
    unknown_tool = await _post(
        app, raw, _rpc("tools/call", {"name": "does.not.exist", "arguments": {}})
    )
    assert unknown_tool.status_code < 500
    body = _parse(unknown_tool)
    assert body is not None and _refused(body), body
    unknown_method = await _post(app, raw, _rpc("nonexistent/method"))
    assert unknown_method.status_code < 500
    assert "error" in _parse(unknown_method)


@pytest.mark.parametrize(
    "payload",
    [b"{not json", b"", b"[]", b'{"jsonrpc":"1.0","id":1,"method":"initialize"}', b"\x00\xff\xfe"],
)
async def test_malformed_requests_never_produce_a_server_error(
    governed_app_with_key, payload
) -> None:
    app, raw, *_ = governed_app_with_key
    response = await _post(app, raw, payload)
    assert response.status_code < 500, (payload, response.status_code, response.text[:200])


async def test_every_request_is_authenticated_not_just_the_first(governed_app_with_key) -> None:
    """Stateless transport: a session id from an authenticated client is worthless without a credential."""
    app, raw, *_ = governed_app_with_key
    first = await _post(app, raw, _initialize("2025-11-25"))
    session = first.headers.get("mcp-session-id")
    extra = {"mcp-session-id": session} if session else {"mcp-session-id": "forged-session-id"}
    anonymous = await _post(app, None, _rpc("tools/list"), extra)
    assert anonymous.status_code in (401, 403), anonymous.text
    wrong_key = await _post(app, "wp_live_" + "0" * 40, _rpc("tools/list"), extra)
    assert wrong_key.status_code in (401, 403), wrong_key.text


async def test_a_session_id_does_not_carry_one_tenants_identity_to_another_key(
    governed_app_with_key,
) -> None:
    """A second tenant's key sends the first tenant's session id: the work is done as the second tenant
    (or refused), never as the first."""
    from responsibleai.db import OrgRepository
    from responsibleai.rbac.models import Plan, Role

    app, raw_a, org_a, engine, _key = governed_app_with_key
    org_b = await OrgRepository(engine).create_org("Other Co", "other-co", plan=Plan.ENTERPRISE)
    _rec, raw_b = await OrgRepository(engine).create_key(org_b.id, "b", role=Role.ANALYST)
    first = await _post(app, raw_a, _initialize("2025-11-25"))
    session = first.headers.get("mcp-session-id") or "session-of-tenant-a"
    from sqlalchemy import select

    from responsibleai.db.engine import governance_execution_nonces

    async with engine.raw.connect() as conn:
        before_a = len(
            (
                await conn.execute(
                    select(governance_execution_nonces).where(
                        governance_execution_nonces.c.organization_id == org_a
                    )
                )
            ).fetchall()
        )
    await _post(
        app,
        raw_b,
        _rpc(
            "tools/call",
            {"name": "rai_health", "arguments": {"whitepact_purpose": "automated-test"}},
        ),
        {"mcp-session-id": session},
    )
    async with engine.raw.connect() as conn:
        after_a = len(
            (
                await conn.execute(
                    select(governance_execution_nonces).where(
                        governance_execution_nonces.c.organization_id == org_a
                    )
                )
            ).fetchall()
        )
    assert after_a == before_a, "tenant B's call, carrying tenant A's session id, acted on tenant A"
