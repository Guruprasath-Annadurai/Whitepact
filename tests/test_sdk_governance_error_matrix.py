"""Every governance endpoint has the same safe HTTP/JSON error contract."""

import httpx
import pytest
from sdk.python.rai_client import GovernanceRequestError, GovernanceRuntimeClient

METHODS = [
    lambda c: c.call_tool("local"),
    lambda c: c.list_approvals(),
    lambda c: c.resolve_approval("a", "DENIED"),
    lambda c: c.revoke_delegation("a", reason="test"),
    lambda c: c.execute_approval("a"),
    lambda c: c.get_evidence("e"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("invoke", METHODS)
@pytest.mark.parametrize(
    "status,body",
    [
        (401, "expired synthetic"),
        (403, "denied synthetic"),
        (429, "limited synthetic"),
        (503, "failed synthetic"),
        (200, "null"),
        (200, "[]"),
        (200, "bad JSON"),
    ],
)
async def test_safe_normalized_governance_errors(invoke, status, body):
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(status, text=body)

    client = GovernanceRuntimeClient("synthetic", transport=httpx.MockTransport(respond))
    with pytest.raises(GovernanceRequestError) as caught:
        await invoke(client)
    assert caught.value.status_code == status
    assert "synthetic" not in str(caught.value)
    assert len(calls) == 1
