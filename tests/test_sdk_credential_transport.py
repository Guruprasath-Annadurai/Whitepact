"""Bearer keys are never dispatched over remote plaintext HTTP."""

import httpx
import pytest
from sdk.python.rai_client.client import RAIClient
from sdk.python.rai_client.governance import GovernanceRuntimeClient


@pytest.mark.parametrize("factory", [RAIClient, GovernanceRuntimeClient])
@pytest.mark.parametrize(
    "url",
    [
        "http://remote.example",
        "http://localhost.evil.example",
        "https://user:password@example.com",
        "ftp://127.0.0.1",
    ],
)
def test_unsafe_credential_destination_is_refused(factory, url):
    with pytest.raises(ValueError):
        factory(api_key="synthetic-local-key", base_url=url)


@pytest.mark.parametrize("factory", [RAIClient, GovernanceRuntimeClient])
@pytest.mark.parametrize(
    "url",
    ["https://example.com", "http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8765"],
)
def test_secure_or_explicit_loopback_configuration_remains_supported(factory, url):
    factory(api_key="synthetic-local-key", base_url=url)


@pytest.mark.asyncio
async def test_allowed_local_governance_request_preserves_bearer_contract():
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(200, json={"result": {"ok": True}})

    c = GovernanceRuntimeClient("synthetic-local-key", transport=httpx.MockTransport(respond))
    assert (await c.call_tool("local")).completed
    assert seen[0].headers["Authorization"] == "Bearer synthetic-local-key"
