"""A2A (Agent2Agent protocol) outbound governance gate -- item #4 of the
v3 authority-layer spec's build list ("A2A adapter architecture").

**What this governs**: MCP governs *tool calls* (an agent calling a
function). A2A governs *agent-to-agent* calls (one agent sending a
Task/Message to another agent it doesn't control) -- a distinct trust
boundary WhitePact had no coverage for at all before this module.
Two risks specific to that boundary, both already have a WhitePact
primitive built for them elsewhere in this codebase:

1. The remote agent itself might be untrustworthy -- reuses
   ``integrations.client.TrustClient`` (the same "check a third party
   before calling it" pattern the LangChain/LangGraph/ADK integrations
   already use for tools, now applied to another *agent*).
2. The outbound message becomes part of the *receiving* agent's
   context -- exactly the "content that gets replayed as trusted
   context" risk ``governance.memory_firewall.scan_memory_write()``
   (item #3, Memory Authority) was built for. An A2A message is not
   technically a memory write, but it poses the identical risk to
   whatever the receiving agent does with it, so this reuses the same
   scanner rather than inventing a second one.

**Framework-agnostic by design**: the core gate (``A2ATrustGate``)
takes plain strings (remote agent name/provider, message text) and has
*no* dependency on the ``a2a-sdk`` package at all -- unlike
``adk_toolset.py`` (which wraps ADK's own `McpToolset` and genuinely
needs the ADK package to do anything), there is nothing here that
structurally requires the real SDK to be installed, so the gate itself
is not gated behind a `_require_a2a_sdk()` guard. The optional
``extract_agent_and_message()`` helper at the bottom, which pulls
those plain strings out of real ``a2a-sdk`` `AgentCard`/`Message`
objects via duck typing, is offered as a convenience for callers who
do have the SDK installed -- see its own docstring for the version
caveat.

Install the real SDK via the ``a2a`` extra if you want to pass live
``a2a-sdk`` objects through ``extract_agent_and_message()``:

    pip install "rai-governance-platform[a2a]"

Usage (framework-agnostic core, no SDK needed):

    from responsibleai.integrations.a2a_adapter import A2ATrustGate

    gate = A2ATrustGate(min_score=70)
    result = await gate.check_async(
        remote_agent_name="partner-agent",
        remote_agent_provider="acme-corp",
        message="Please process this refund for order #4471.",
    )
    if not result.allowed:
        raise RuntimeError(f"A2A call blocked: {result.reasons}")
    # ... send the message via your real a2a-sdk client ...
"""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.governance.memory_firewall import scan_memory_write
from responsibleai.integrations.client import TrustCheckResult, TrustClient

try:
    import a2a  # noqa: F401

    _A2A_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra isn't installed
    _A2A_SDK_AVAILABLE = False


def _require_a2a_sdk() -> None:
    if not _A2A_SDK_AVAILABLE:
        raise ImportError(
            "extract_agent_and_message requires the 'a2a' extra: "
            'pip install "rai-governance-platform[a2a]" (needs a2a-sdk). The '
            "core A2ATrustGate.check()/check_async() methods do not require this "
            "-- they take plain strings and work without the SDK installed."
        )


@dataclass(frozen=True)
class A2AGateResult:
    """The gate's decision for one outbound agent-to-agent call.
    ``reasons`` is empty iff ``allowed`` is ``True``."""

    allowed: bool
    reasons: tuple[str, ...]
    trust_check: TrustCheckResult | None
    memory_firewall_matched_patterns: tuple[str, ...]


class A2ATrustGate:
    """Governs an OUTBOUND A2A call -- call ``check()``/``check_async()``
    before actually sending a Task/Message to a remote agent, and don't
    send it if ``result.allowed`` is ``False``.

    Fails open on a trust-check network error or an unknown (never
    Trust-Index-assessed) remote agent by default, same reasoning as
    ``TrustCheckResult.passes()`` and the LangChain/LangGraph
    integrations -- set ``require_known=True`` for a stricter,
    allow-listing posture. The memory-firewall scan never fails open:
    a matched injection pattern always blocks, since (unlike an
    unscored trust check) a positive match is a concrete finding, not
    an absence of data.
    """

    def __init__(
        self,
        *,
        min_score: float = 0.0,
        require_known: bool = False,
        scan_message: bool = True,
        client: TrustClient | None = None,
    ) -> None:
        self.min_score = min_score
        self.require_known = require_known
        self.scan_message = scan_message
        self.client = client or TrustClient()

    def _trust_reason(self, result: TrustCheckResult) -> str | None:
        if result.passes(min_score=self.min_score, require_known=self.require_known):
            return None
        if result.known:
            return f"remote agent trust score {result.overall_score} below minimum {self.min_score}"
        return "remote agent has no Trust Index record and require_known=True"

    def check(
        self, remote_agent_name: str, remote_agent_provider: str, message: str
    ) -> A2AGateResult:
        trust_result = self.client.check(remote_agent_name, remote_agent_provider)
        return self._decide(trust_result, message)

    async def check_async(
        self, remote_agent_name: str, remote_agent_provider: str, message: str
    ) -> A2AGateResult:
        trust_result = await self.client.check_async(remote_agent_name, remote_agent_provider)
        return self._decide(trust_result, message)

    def _decide(self, trust_result: TrustCheckResult, message: str) -> A2AGateResult:
        reasons: list[str] = []
        trust_reason = self._trust_reason(trust_result)
        if trust_reason is not None:
            reasons.append(trust_reason)

        matched_patterns: tuple[str, ...] = ()
        if self.scan_message:
            firewall_result = scan_memory_write(message)
            matched_patterns = firewall_result.matched_patterns
            if firewall_result.is_blocked:
                reasons.append(
                    f"outbound message matched injection pattern(s): {', '.join(matched_patterns)}"
                )

        return A2AGateResult(
            allowed=not reasons,
            reasons=tuple(reasons),
            trust_check=trust_result,
            memory_firewall_matched_patterns=matched_patterns,
        )


def extract_agent_and_message(agent_card: object, message: object) -> tuple[str, str, str]:
    """Best-effort extraction of ``(agent_name, agent_provider,
    message_text)`` from real ``a2a-sdk`` ``AgentCard``/``Message``
    objects, for callers who want to pass those straight to
    ``A2ATrustGate`` without manually pulling fields out themselves.

    **Duck-typed, not a verified SDK integration**: ``a2a-sdk``'s exact
    object shape can vary by version, so this reads via ``getattr()``
    with fallbacks rather than importing and type-checking against SDK
    classes directly -- if a field this function expects has moved or
    been renamed in your installed version, it degrades to a sensible
    default (``"unknown"`` provider, empty message text) rather than
    raising. Verify against your installed ``a2a-sdk`` version before
    relying on this in production; the framework-agnostic
    ``A2ATrustGate.check()``/``check_async()`` methods (plain strings)
    are the tested, load-bearing path -- this is a convenience on top,
    not a replacement for calling them directly if extraction doesn't
    fit your SDK version.

    ``agent_card`` is expected to expose ``.name`` and optionally
    ``.provider`` (or ``.provider.organization``, the ``AgentProvider``
    shape); ``message`` is expected to expose ``.parts``, a list of
    objects each optionally exposing ``.root.text`` or ``.text`` (A2A's
    `TextPart`).
    """
    _require_a2a_sdk()

    name = getattr(agent_card, "name", None) or "unknown"

    provider = getattr(agent_card, "provider", None)
    if provider is None:
        provider_name = "unknown"
    elif isinstance(provider, str):
        provider_name = provider
    else:
        provider_name = (
            getattr(provider, "organization", None) or getattr(provider, "name", None) or "unknown"
        )

    parts = getattr(message, "parts", None) or []
    text_fragments: list[str] = []
    for part in parts:
        root = getattr(part, "root", part)
        text = getattr(root, "text", None)
        if isinstance(text, str):
            text_fragments.append(text)
    message_text = "\n".join(text_fragments)

    return name, provider_name, message_text
