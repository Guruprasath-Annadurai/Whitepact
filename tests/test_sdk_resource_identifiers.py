# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Opaque SDK IDs cannot alter the intended governance route."""

import httpx
import pytest
from sdk.python.rai_client.governance import GovernanceRuntimeClient

OPERATIONS = (
    lambda c, value: c.resolve_approval(value, "APPROVED"),
    lambda c, value: c.execute_approval(value),
    lambda c, value: c.revoke_delegation(value, reason="test"),
    lambda c, value: c.get_evidence(value),
    lambda c, value: c.get_attestation(value),
)
INVALID = (
    "",
    ".",
    "..",
    "../other",
    "a/b",
    "a\\b",
    "a?b",
    "a#b",
    "%2e%2e",
    " a",
    "a ",
    "a b",
    "a\t",
    "a\n",
    "a\x00",
    "a\x7f",
    "a\u00a0b",
    "a\u0080b",
    "a\ud800b",
    None,
    42,
)


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("value", INVALID)
async def test_invalid_id_never_sends_a_request(operation, value):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"result": {}})

    client = GovernanceRuntimeClient("local-test", transport=httpx.MockTransport(handle))
    with pytest.raises(ValueError, match="Invalid resource identifier"):
        await operation(client, value)
    assert requests == []


@pytest.mark.parametrize("value", ["apr-9", "abc_123", "ev.1", "urn:opaque:123", "évidence"])
async def test_attestation_preserves_a_valid_id_and_server_tenant_boundary(value):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"evidence_id": value, "outcome_status": "UNKNOWN"})

    client = GovernanceRuntimeClient("local-test", transport=httpx.MockTransport(handle))
    out = await client.get_attestation(value)
    assert out["outcome_status"] == "UNKNOWN"
    assert len(seen) == 1
    assert seen[0].url.path == f"/api/governance/evidence/{value}/attestation"
    assert seen[0].url.query == b""
    assert seen[0].headers["Authorization"] == "Bearer local-test"
