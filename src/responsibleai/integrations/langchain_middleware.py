"""LangChain agent middleware that gates tool calls on the ResponsibleAI
Trust Index — the reference "npm audit for AI agents" integration
described in GAME_CHANGER_BUILD_PLAN.md Phase B.

Requires `langchain>=1.0` (the `wrap_tool_call` middleware hook this
depends on doesn't exist before that). Not a core dependency of this
project — install via the `langchain` extra:

    pip install "rai-governance-platform[langchain]"

Usage:

    from langchain.agents import create_agent
    from responsibleai.integrations.langchain_middleware import TrustGateMiddleware

    agent = create_agent(
        model="gpt-4o",
        tools=[my_third_party_tool],
        middleware=[TrustGateMiddleware(min_score=70)],
    )

Why middleware and not a callback: LangChain's `on_tool_start` callback
is observer-only and cannot block execution (confirmed against the
installed `langchain-core` callbacks docs/source — see
GAME_CHANGER_BUILD_PLAN.md's correction on this). `wrap_tool_call`
middleware, added in LangChain 1.0, is the actual interception point —
it receives a `handler` callable and can choose not to call it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from langchain.agents.middleware import AgentMiddleware
    from langchain_core.messages import ToolMessage

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra isn't installed
    _LANGCHAIN_AVAILABLE = False
    AgentMiddleware = object  # type: ignore[assignment,misc]

from responsibleai.integrations.client import TrustClient

if TYPE_CHECKING:
    from langchain.agents.middleware.types import ToolCallRequest
    from langgraph.types import Command


def _require_langchain() -> None:
    if not _LANGCHAIN_AVAILABLE:
        raise ImportError(
            "TrustGateMiddleware requires the 'langchain' extra: "
            "pip install \"rai-governance-platform[langchain]\" (needs langchain>=1.0 "
            "for the wrap_tool_call middleware hook)."
        )


class TrustGateMiddleware(AgentMiddleware):  # type: ignore[misc]
    """Blocks a tool call when its Trust Index score is below `min_score`.

    The tool's own name is used as the Trust Index `model_name`; provider
    defaults to `default_provider` unless overridden per-tool via
    `provider_map`. This mirrors how the free self-assessment endpoint
    already registers arbitrary tools/models under a (name, provider)
    pair — a third-party MCP server or tool can self-assess under its own
    name exactly the way a model does.

    Fails open on network errors and on unknown (never-assessed) tools by
    default — see `TrustCheckResult.passes()` for the reasoning. Set
    `require_known=True` to block anything with no Trust Index record at
    all, which is a stricter, allow-listing posture some deployments will
    want instead.
    """

    def __init__(
        self,
        *,
        min_score: float = 0.0,
        require_known: bool = False,
        default_provider: str = "unknown",
        provider_map: dict[str, str] | None = None,
        client: TrustClient | None = None,
    ) -> None:
        _require_langchain()
        super().__init__()
        self.min_score = min_score
        self.require_known = require_known
        self.default_provider = default_provider
        self.provider_map = provider_map or {}
        self.client = client or TrustClient()

    def _provider_for(self, tool_name: str) -> str:
        return self.provider_map.get(tool_name, self.default_provider)

    def _blocked_message(self, request: ToolCallRequest, reason: str) -> ToolMessage:
        return ToolMessage(
            content=(
                f"Blocked by ResponsibleAI TrustGateMiddleware: {reason}. "
                f"Tool '{request.tool_call['name']}' did not pass the configured "
                f"trust threshold (min_score={self.min_score}, require_known={self.require_known})."
            ),
            tool_call_id=request.tool_call["id"],
            status="error",
        )

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Any,
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call["name"]
        provider = self._provider_for(tool_name)
        result = self.client.check(tool_name, provider)
        if not result.passes(min_score=self.min_score, require_known=self.require_known):
            reason = (
                f"score {result.overall_score} below minimum {self.min_score}"
                if result.known
                else "no Trust Index record found and require_known=True"
            )
            return self._blocked_message(request, reason)
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Any,
    ) -> ToolMessage | Command[Any]:
        tool_name = request.tool_call["name"]
        provider = self._provider_for(tool_name)
        result = await self.client.check_async(tool_name, provider)
        if not result.passes(min_score=self.min_score, require_known=self.require_known):
            reason = (
                f"score {result.overall_score} below minimum {self.min_score}"
                if result.known
                else "no Trust Index record found and require_known=True"
            )
            return self._blocked_message(request, reason)
        return await handler(request)
