# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The Python SDK must not turn a transport or authentication failure into "not blocked".

``call_tool`` used to return the body of any response as an outcome. A 401, 403, 429 or 500 has no
``denied`` / ``requires_approval`` flag, so a caller that proceeds when neither is set (the natural
reading of the old API) would run the action. Now only a 2xx JSON object is an outcome, and
``completed`` is the one positive signal.
"""

from __future__ import annotations

import httpx
import pytest
from sdk.python.rai_client import GovernanceRequestError, GovernanceRuntimeClient


def _client(handler) -> GovernanceRuntimeClient:
    return GovernanceRuntimeClient(
        "key-secret-123", base_url="http://wp.test", transport=httpx.MockTransport(handler)
    )


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 500, 502, 503])
async def test_a_non_2xx_response_is_an_exception_not_an_outcome(status: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"error": "whatever", "message": "x"})

    with pytest.raises(GovernanceRequestError) as raised:
        await _client(handler).call_tool("t", {})
    assert raised.value.status_code == status
    assert "key-secret-123" not in str(raised.value)


@pytest.mark.parametrize("body", [b"<html>gateway</html>", b"", b"[]", b'"ok"', b"null"])
async def test_a_2xx_response_that_is_not_a_json_object_is_refused(body: bytes) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(GovernanceRequestError):
        await _client(handler).call_tool("t", {})


async def test_denied_and_approval_answers_are_outcomes_and_are_not_completed() -> None:
    answers = {
        "denied": {"error": "governance_denied", "reason_codes": ["X"]},
        "approval": {"error": "governance_approval_required", "approval_id": "a1"},
    }
    for name, payload in answers.items():

        async def handler(request: httpx.Request, p=payload) -> httpx.Response:
            return httpx.Response(200, json=p)

        outcome = await _client(handler).call_tool("t", {})
        assert outcome.completed is False, name
    assert (
        await _client(lambda r: httpx.Response(200, json={"error": "governance_denied"})).call_tool(
            "t"
        )
    ).denied
    assert (
        await _client(
            lambda r: httpx.Response(
                200, json={"error": "governance_approval_required", "approval_id": "a"}
            )
        ).call_tool("t")
    ).requires_approval


async def test_a_clean_answer_is_completed_and_sends_the_bearer_key() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        return httpx.Response(200, json={"result": {"ok": True}})

    outcome = await _client(handler).call_tool("t", {"a": 1}, purpose="p")
    assert outcome.completed is True and not outcome.denied and not outcome.requires_approval
    assert seen["auth"] == "Bearer key-secret-123"
