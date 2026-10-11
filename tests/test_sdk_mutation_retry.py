"""A lost mutation response is not permission to replay the mutation."""

import httpx
import pytest
from sdk.python.rai_client.client import RAIClient


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["status", "transport"])
async def test_post_is_one_shot_even_when_response_is_lost(failure):
    calls = []

    def respond(request):
        calls.append(request)
        if failure == "transport":
            raise httpx.ReadTimeout("lost response", request=request)
        return httpx.Response(503)

    client = RAIClient(max_retries=3)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        client._client = transport
        with pytest.raises((httpx.HTTPStatusError, httpx.ReadTimeout)):
            await client.record_usage("local", "local", 1, 1)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_read_retry_remains_bounded(monkeypatch):
    calls = []

    async def no_wait(_):
        pass

    monkeypatch.setattr("sdk.python.rai_client.client.asyncio.sleep", no_wait)

    def respond(request):
        calls.append(request)
        return httpx.Response(503 if len(calls) < 3 else 200, json={"ok": True})

    client = RAIClient(max_retries=3)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        client._client = transport
        assert await client.cost_summary() == {"ok": True}
    assert len(calls) == 3
