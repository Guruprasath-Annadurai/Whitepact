# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
from __future__ import annotations

import traceback

import httpx
import pytest
from sdk.python.rai_client.governance import GovernanceRuntimeClient


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError]
)
@pytest.mark.parametrize(
    "method",
    [
        "call_tool",
        "list_approvals",
        "resolve_approval",
        "execute_approval",
        "revoke_delegation",
        "get_evidence",
        "list_evidence",
        "get_attestation",
    ],
)
async def test_transport_exception_preserves_class_without_credential_or_request(failure, method):
    key = "synthetic-private-transport-key"
    dispatches = 0

    def handler(request):
        nonlocal dispatches
        dispatches += 1
        raise failure(f"transport failure reflected {key}", request=request)

    client = GovernanceRuntimeClient(key, transport=httpx.MockTransport(handler))
    calls = {
        "call_tool": lambda: client.call_tool("local"),
        "list_approvals": client.list_approvals,
        "resolve_approval": lambda: client.resolve_approval("apr", "DENIED"),
        "execute_approval": lambda: client.execute_approval("apr"),
        "revoke_delegation": lambda: client.revoke_delegation("agent", reason="test"),
        "get_evidence": lambda: client.get_evidence("ev"),
        "list_evidence": client.list_evidence,
        "get_attestation": lambda: client.get_attestation("ev"),
    }
    with pytest.raises(failure) as caught:
        await calls[method]()
    assert key not in str(caught.value)
    assert key not in "".join(traceback.format_exception(caught.value))
    assert "[REDACTED]" in str(caught.value)
    assert caught.value.__context__ is None
    assert caught.value.__cause__ is None
    # The original authenticated request must not escape as exception metadata.
    with pytest.raises(RuntimeError, match="request"):
        _ = caught.value.request
    assert dispatches == 1
