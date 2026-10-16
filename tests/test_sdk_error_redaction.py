# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reflected bearer credentials must not be included in public SDK errors."""

import httpx
import pytest
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["synthetic-local-secret", "synthetic-" + "x" * 250])
async def test_reflected_api_key_redacted_before_message_truncation(key):
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(403, text=f"refused Bearer {key}; {key}")
    )
    client = GovernanceRuntimeClient(api_key=key, base_url="https://example.test")
    client._client = lambda: httpx.AsyncClient(transport=transport)
    with pytest.raises(GovernanceRequestError) as caught:
        await client.call_tool("local")
    message = str(caught.value)
    assert key not in message
    assert key[:40] not in message
    assert "[REDACTED]" in message
    assert caught.value.status_code == 403
