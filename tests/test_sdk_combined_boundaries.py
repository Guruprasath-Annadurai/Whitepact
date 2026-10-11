"""Cross-feature regression coverage on the combined SDK candidate."""

import ast
from pathlib import Path

import httpx
import pytest
from sdk.python.rai_client.client import RAIClient
from sdk.python.rai_client.governance import GovernanceRuntimeClient, GovernanceToolOutcome


def test_actual_backend_outcome_enum_never_promotes_non_success():
    tree = ast.parse(Path("src/responsibleai/governance/outcome.py").read_text())
    enum = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "OutcomeStatus"
    )
    values = [node.value.value for node in enum.body if isinstance(node, ast.Assign)]
    assert "SUCCEEDED" in values and "UNKNOWN" in values
    for value in values:
        assert GovernanceToolOutcome(raw={"result": {}, "outcome_status": value}).completed == (
            value == "SUCCEEDED"
        )


@pytest.mark.asyncio
async def test_unknown_then_lost_mutation_response_never_retries_or_completes():
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, json={"result": None, "outcome_status": "UNKNOWN"})
        raise httpx.ReadTimeout("lost response", request=request)

    client = GovernanceRuntimeClient("synthetic", transport=httpx.MockTransport(respond))
    assert not (await client.call_tool("local")).completed
    with pytest.raises(httpx.ReadTimeout):
        await client.call_tool("local")
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_https_validation_redirect_refusal_and_one_shot_mutation_compose():
    with pytest.raises(ValueError):
        RAIClient(api_key="synthetic", base_url="http://remote.test")
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(307, headers={"Location": "https://other.test"})

    client = RAIClient(api_key="synthetic", base_url="https://remote.test")
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as transport:
        client._client = transport
        with pytest.raises(httpx.HTTPStatusError):
            await client.record_usage("local", "local", 1, 1)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_error_redaction_and_transport_timeout_do_not_replay():
    key = "synthetic-combined-key"
    calls = []

    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return httpx.Response(403, text=f"refused {key}")

    client = GovernanceRuntimeClient(key, transport=httpx.MockTransport(respond))
    with pytest.raises(httpx.ReadTimeout):
        await client.call_tool("local")
    assert len(calls) == 1
    with pytest.raises(Exception) as caught:
        await client.call_tool("local")
    assert "[REDACTED]" in str(caught.value) and key not in str(caught.value)
    assert len(calls) == 2
