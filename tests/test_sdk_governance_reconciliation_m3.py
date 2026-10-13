# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SDK surfaces UNKNOWN / reconciliation-required payloads (P1-03 / P1-05)."""

from __future__ import annotations

import httpx
import pytest
import respx
from sdk.python.rai_client.governance import GovernanceRuntimeClient


@pytest.mark.asyncio
@respx.mock
async def test_governance_sdk_marks_unknown_as_reconciliation() -> None:
    respx.post("http://test/api/v1/governance/tools/call").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "UNKNOWN",
                "reconciliation_required": True,
                "evidence_id": "ev-42",
            },
        )
    )
    client = GovernanceRuntimeClient("wp_key", base_url="http://test")
    outcome = await client.call_tool("demo.tool", {})
    assert outcome.reconciliation_required is True
    assert outcome.requires_approval is False


@pytest.mark.asyncio
@respx.mock
async def test_governance_sdk_get_evidence_path() -> None:
    route = respx.get("http://test/api/governance/evidence/ev-42").mock(
        return_value=httpx.Response(200, json={"evidence_id": "ev-42", "decision": "ALLOW"})
    )
    client = GovernanceRuntimeClient("wp_key", base_url="http://test")
    body = await client.get_evidence("ev-42")
    assert body["evidence_id"] == "ev-42"
    assert route.called
