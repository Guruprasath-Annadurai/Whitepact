# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SDK governance HTTP contract (Python) — P1-03."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from sdk.python.rai_client.governance import GovernanceRuntimeClient


@pytest.mark.asyncio
@respx.mock
async def test_governance_sdk_tool_call_path_and_auth() -> None:
    route = respx.post("http://test/api/v1/governance/tools/call").mock(
        return_value=httpx.Response(
            200,
            json={"error": "governance_approval_required", "approval_id": "apr-1"},
        )
    )
    client = GovernanceRuntimeClient("wp_test_key", base_url="http://test")
    body = await client.call_tool("test.counter.increment", {"n": 1})
    assert body["approval_id"] == "apr-1"
    assert route.called
    assert route.calls[0].request.headers["Authorization"] == "Bearer wp_test_key"
    sent = json.loads(route.calls[0].request.content.decode())
    assert sent["name"] == "test.counter.increment"
    assert sent["purpose"] == "sdk-governance"


@pytest.mark.asyncio
@respx.mock
async def test_governance_sdk_approval_resolve_execute_paths() -> None:
    respx.get("http://test/api/governance/approvals").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    resolve = respx.post("http://test/api/governance/approvals/apr-9/resolve").mock(
        return_value=httpx.Response(200, json={"status": "APPROVED"})
    )
    execute = respx.post("http://test/api/governance/approvals/apr-9/execute").mock(
        return_value=httpx.Response(200, json={"status": "EXECUTED"})
    )
    client = GovernanceRuntimeClient("wp_key", base_url="http://test")
    listed = await client.list_approvals()
    assert listed["items"] == []
    resolved = await client.resolve_approval("apr-9", "APPROVED", notes="sdk")
    assert resolved["status"] == "APPROVED"
    executed = await client.execute_approval("apr-9")
    assert executed["status"] == "EXECUTED"
    assert json.loads(resolve.calls[0].request.content.decode())["outcome"] == "APPROVED"
    assert execute.called
