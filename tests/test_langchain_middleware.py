"""Tests for TrustGateMiddleware — the LangChain wrap_tool_call adapter
described in GAME_CHANGER_BUILD_PLAN.md Phase B. Requires the real
`langchain` package (the `langchain` extra / dev dependency) since the
whole point is verifying against the actual AgentMiddleware/ToolMessage
API, not a hand-rolled stand-in for it."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

langchain = pytest.importorskip("langchain")

from responsibleai.integrations.client import TrustCheckResult, TrustClient  # noqa: E402
from responsibleai.integrations.langchain_middleware import TrustGateMiddleware  # noqa: E402


class _FakeRequest:
    def __init__(self, name: str, call_id: str = "call_1") -> None:
        self.tool_call = {"name": name, "args": {}, "id": call_id}


def _client_returning(result: TrustCheckResult) -> MagicMock:
    client = MagicMock(spec=TrustClient)
    client.check.return_value = result
    client.check_async = _async_return(result)
    return client


def _async_return(value):
    async def _inner(*_args, **_kwargs):
        return value

    return _inner


def _low_score_result(name: str) -> TrustCheckResult:
    return TrustCheckResult(
        model=name,
        provider="unknown",
        known=True,
        trust_score={"overall": 10.0},
        certified=False,
        has_reported_incidents=False,
    )


def _high_score_result(name: str) -> TrustCheckResult:
    return TrustCheckResult(
        model=name,
        provider="unknown",
        known=True,
        trust_score={"overall": 95.0},
        certified=True,
        has_reported_incidents=False,
    )


class TestSyncWrapToolCall:
    def test_blocks_below_threshold_without_calling_handler(self) -> None:
        client = _client_returning(_low_score_result("bad-tool"))
        mw = TrustGateMiddleware(min_score=50, client=client)

        def handler(_request):
            raise AssertionError("handler must not run for a blocked call")

        result = mw.wrap_tool_call(_FakeRequest("bad-tool"), handler)
        assert result.status == "error"
        assert "bad-tool" in result.content
        assert result.tool_call_id == "call_1"

    def test_allows_above_threshold_and_returns_handler_result(self) -> None:
        client = _client_returning(_high_score_result("good-tool"))
        mw = TrustGateMiddleware(min_score=50, client=client)

        result = mw.wrap_tool_call(_FakeRequest("good-tool"), lambda req: "HANDLER_RAN")
        assert result == "HANDLER_RAN"

    def test_unknown_tool_passes_by_default(self) -> None:
        unknown = TrustCheckResult(
            model="never-assessed",
            provider="unknown",
            known=False,
            trust_score=None,
            certified=False,
            has_reported_incidents=False,
        )
        client = _client_returning(unknown)
        mw = TrustGateMiddleware(min_score=50, client=client)

        result = mw.wrap_tool_call(_FakeRequest("never-assessed"), lambda req: "OK")
        assert result == "OK"

    def test_unknown_tool_blocked_when_require_known(self) -> None:
        unknown = TrustCheckResult(
            model="never-assessed",
            provider="unknown",
            known=False,
            trust_score=None,
            certified=False,
            has_reported_incidents=False,
        )
        client = _client_returning(unknown)
        mw = TrustGateMiddleware(min_score=0, require_known=True, client=client)

        def handler(_request):
            raise AssertionError("handler must not run")

        result = mw.wrap_tool_call(_FakeRequest("never-assessed"), handler)
        assert result.status == "error"

    def test_provider_map_overrides_default_provider(self) -> None:
        client = _client_returning(_high_score_result("stripe-mcp"))
        mw = TrustGateMiddleware(
            min_score=0,
            client=client,
            provider_map={"stripe-mcp": "stripe"},
        )
        mw.wrap_tool_call(_FakeRequest("stripe-mcp"), lambda req: "OK")
        client.check.assert_called_once_with("stripe-mcp", "stripe")


class TestAsyncWrapToolCall:
    async def test_blocks_below_threshold(self) -> None:
        client = _client_returning(_low_score_result("bad-tool"))
        mw = TrustGateMiddleware(min_score=50, client=client)

        async def handler(_request):
            raise AssertionError("handler must not run for a blocked call")

        result = await mw.awrap_tool_call(_FakeRequest("bad-tool"), handler)
        assert result.status == "error"

    async def test_allows_above_threshold(self) -> None:
        client = _client_returning(_high_score_result("good-tool"))
        mw = TrustGateMiddleware(min_score=50, client=client)

        async def handler(_request):
            return "HANDLER_RAN"

        result = await mw.awrap_tool_call(_FakeRequest("good-tool"), handler)
        assert result == "HANDLER_RAN"


class TestConstruction:
    def test_default_client_is_a_real_trust_client(self) -> None:
        mw = TrustGateMiddleware()
        assert isinstance(mw.client, TrustClient)

    def test_is_a_real_agent_middleware(self) -> None:
        from langchain.agents.middleware import AgentMiddleware

        assert isinstance(TrustGateMiddleware(), AgentMiddleware)
