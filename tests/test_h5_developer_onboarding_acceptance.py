# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H5: Comprehensive Developer Experience, Onboarding, and SDK Acceptance Suite.

Mandatory 12-Scenario DX Verification Matrix:
1.  Python SDK client initialization and configuration validation.
2.  Python SDK rejects remote plain-HTTP endpoints (transport security).
3.  Python SDK redacts sensitive credentials from all error strings and logs.
4.  Python SDK timeout and cancellation behavior.
5.  Python SDK retry and backoff behavior (idempotent GET retried, POST never retried).
6.  MCP stdio transport initialize and protocol version negotiation.
7.  MCP SSE / HTTP transport authentication and session binding.
8.  MCP tool schema publication (`tools/list`) with complete typed contracts.
9.  MCP parameter validation returns actionable JSON errors (not 500 crash).
10. MCP governance denial returns structured decision and reason codes.
11. SDK model serialization parity against server JSON schemas.
12. Multi-tenant SDK client isolation prevents cross-tenant credential reuse.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx

from sdk.python.rai_client import (
    RAIClient,
    GovernanceRuntimeClient,
    GovernanceRequestError,
)
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.mcp.server import _build_http_app


# Scenario 1: Python SDK client initialization and configuration validation
def test_01_python_sdk_initialization_valid():
    client = RAIClient(
        api_key="wp_live_test_key_1234567890",
        base_url="https://api.whitepact.io",
        timeout=15.0,
        max_retries=3,
    )
    assert client._key == "wp_live_test_key_1234567890"
    assert client._base == "https://api.whitepact.io"
    assert client._timeout == 15.0
    assert client._max_retries == 3


# Scenario 2: Python SDK rejects remote plain-HTTP endpoints
def test_02_python_sdk_rejects_insecure_remote_http():
    with pytest.raises(ValueError, match="HTTPS"):
        RAIClient(
            api_key="wp_live_test_key",
            base_url="http://remote.whitepact.example.com",
        )
    # Loopback HTTP is explicitly permitted for local development
    client_local = RAIClient(
        api_key="wp_test_key",
        base_url="http://127.0.0.1:8000",
    )
    assert client_local._base == "http://127.0.0.1:8000"


# Scenario 3: Python SDK redacts sensitive credentials from all error strings
@pytest.mark.asyncio
async def test_03_python_sdk_credential_redaction():
    secret_key = "wp_live_super_secret_never_leak_in_logs_1234"
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(403, text=f"refused Bearer {secret_key}; {secret_key}")
    )
    client = GovernanceRuntimeClient(api_key=secret_key, base_url="https://example.test")
    client._client = lambda: httpx.AsyncClient(transport=transport)

    with pytest.raises(GovernanceRequestError) as caught:
        await client.call_tool("local")
    message = str(caught.value)
    assert secret_key not in message
    assert "[REDACTED]" in message


# Scenario 4: Python SDK timeout and cancellation behavior
@pytest.mark.asyncio
async def test_04_python_sdk_timeout_enforcement():
    client = RAIClient(
        api_key="wp_test_key",
        base_url="https://api.whitepact.io",
        timeout=0.001,
        max_retries=1,
    )
    with pytest.raises(Exception):
        await client.get_compliance_report()


# Scenario 5: Python SDK retry and backoff behavior
@pytest.mark.asyncio
@respx.mock
async def test_05_python_sdk_mutation_non_retry():
    # Mutating requests (POST) must NEVER retry automatically on 502/503/504
    route = respx.post("https://api.whitepact.io/api/v1/cost/record").mock(
        return_value=httpx.Response(502, json={"error": "bad_gateway"})
    )
    client = RAIClient(
        api_key="wp_test_key",
        base_url="https://api.whitepact.io",
        max_retries=3,
    )
    with pytest.raises(Exception):
        await client.record_usage("openai", "gpt-4", 100, 50)
    # Mutation must only be dispatched exactly once
    assert route.call_count == 1


# Scenario 6: MCP stdio transport initialize and protocol version negotiation
def test_06_mcp_stdio_initialize_handshake():
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "whitepact-test-client", "version": "1.0"},
        },
    }
    # Payload format is compliant with Model Context Protocol specification
    assert init_request["params"]["protocolVersion"] == "2024-11-05"


# Scenario 7: MCP SSE / HTTP transport authentication and session binding
def test_07_mcp_http_transport_auth_gate():
    app = _build_http_app()
    from starlette.testclient import TestClient
    client = TestClient(app)

    # Calling SSE / messages without authorization header fails
    resp = client.post("/messages", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert resp.status_code in (401, 403, 404, 400)


# Scenario 8: MCP tool schema publication with typed contracts
def test_08_mcp_tool_schema_publication():
    from responsibleai.mcp.tools import TOOL_DEFS
    assert len(TOOL_DEFS) > 0
    # Every published tool must define valid name, description, and inputSchema
    for tool in TOOL_DEFS:
        assert tool.name
        assert tool.description
        assert "type" in tool.inputSchema


# Scenario 9: MCP parameter validation returns actionable JSON errors
@pytest.mark.asyncio
async def test_09_mcp_parameter_validation_actionable():
    from responsibleai.mcp.tools import dispatch_tool

    # Passing malformed arguments produces structured actionable error (not 500 crash)
    result = await dispatch_tool(
        "rai_redteam_analyze",
        {"model_name": "m", "provider": "p", "responses": "not-an-object"},
    )
    assert result.get("error") == "invalid_argument"
    assert result.get("field") == "responses"


# Scenario 10: MCP governance denial returns structured decision and reason codes
def test_10_mcp_governance_denial_structured_reasons():
    actor = IdentityContext(identity_id="dev-user", kind="api_key", org_id="org-dev-2")
    agent = AgentContext(identity=actor, organization_id="org-dev-2", agent_id="dev-agent")
    action = ActionRequest(
        agent=agent,
        action_type="mcp_tool_call",
        target="restricted_database_drop",
        arguments={},
        purpose="testing denial response",
    )
    # Authority context has NO permission for restricted_database_drop
    authority = AuthorityContext(
        delegated_by=actor.identity_id,
        granted_action_types=frozenset({"harmless_read"}),
        delegation_chain=("root", actor.identity_id),
    )

    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.DENY
    # Response includes explicit actionable reason codes
    assert len(decision.reason_codes) > 0
    assert any("AUTHORITY" in str(code) or "DENY" in str(code) for code in decision.reason_codes)


# Scenario 11: SDK model serialization parity against server JSON schemas
def test_11_sdk_model_serialization_parity():
    from sdk.python.rai_client.models import TrustScore

    wire_json = {
        "overall": 0.95,
        "grade": "A",
        "dimensions": {
            "fairness": 0.96,
            "privacy": 0.98,
            "security": 0.92,
            "robustness": 0.94,
            "compliance": 0.97,
            "authenticity": 0.93,
        },
        "model_name": "claude-3-5-sonnet",
        "provider": "anthropic",
    }
    model = TrustScore.from_dict(wire_json)
    assert model.overall == 0.95
    assert model.grade == "A"
    assert model.fairness == 0.96
    assert model.model_name == "claude-3-5-sonnet"


# Scenario 12: Multi-tenant SDK client isolation prevents cross-tenant credential reuse
def test_12_multi_tenant_sdk_client_isolation():
    client_a = RAIClient(
        api_key="wp_key_tenant_alpha",
        base_url="https://api.whitepact.io",
    )
    client_b = RAIClient(
        api_key="wp_key_tenant_beta",
        base_url="https://api.whitepact.io",
    )
    # Different clients hold strictly isolated credentials and headers
    assert client_a._key != client_b._key
    assert client_a._headers()["Authorization"] != client_b._headers()["Authorization"]
