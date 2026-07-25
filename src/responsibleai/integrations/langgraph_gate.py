"""LangGraph trust-gate node — the "actually stops a bad call" reference
integration from GAME_CHANGER_BUILD_PLAN.md Phase B.

Unlike the LangChain middleware (which can only allow or hard-block a
tool call), LangGraph's `interrupt()` lets a below-threshold call pause
for a human decision instead of being silently rejected — approve,
reject, or (by resuming with a different value) something in between.
That's the "gate, not just a check" positioning from
GAME_CHANGER_STRATEGY.md Section 3.

Requires `langgraph>=1.0` (for `interrupt()`/checkpointer semantics).
Not a core dependency — install via the `langgraph` extra:

    pip install "rai-governance-platform[langgraph]"

Usage:

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import StateGraph, START
    from responsibleai.integrations.langgraph_gate import make_trust_gate_node

    builder = StateGraph(MyState)
    builder.add_node("trust_gate", make_trust_gate_node(min_score=70))
    builder.add_edge(START, "trust_gate")
    graph = builder.compile(checkpointer=InMemorySaver())  # required for interrupt()

    # ... graph.stream(...) pauses with an Interrupt when a call scores
    # below 70; resume with Command(resume="approve") or Command(resume="reject").

Important: `interrupt()` re-executes the entire node from the top on
resume (documented LangGraph behavior), so the trust check itself runs
twice for a gated call — once before the pause, once after resume. That
is deliberate and harmless here (a read-only HTTP GET), not a bug; do
not add caching that would let a stale trust score survive the resume.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

try:
    from langgraph.types import interrupt

    _LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when extra isn't installed
    _LANGGRAPH_AVAILABLE = False

    def interrupt(value: Any) -> Any:  # type: ignore[misc]
        raise ImportError(
            "make_trust_gate_node requires the 'langgraph' extra: "
            "pip install \"rai-governance-platform[langgraph]\" (needs langgraph>=1.0)."
        )

from responsibleai.integrations.client import TrustCheckResult, TrustClient

if TYPE_CHECKING:
    pass

TrustGateStatus = Literal["approved", "rejected", "skipped"]


def _require_langgraph() -> None:
    if not _LANGGRAPH_AVAILABLE:
        raise ImportError(
            "make_trust_gate_node requires the 'langgraph' extra: "
            "pip install \"rai-governance-platform[langgraph]\" (needs langgraph>=1.0)."
        )


def _get_tool_call(state: Any) -> dict[str, Any] | None:
    if isinstance(state, dict):
        return state.get("tool_call")
    return getattr(state, "tool_call", None)


def _result_summary(result: TrustCheckResult) -> dict[str, Any]:
    return {
        "model": result.model,
        "provider": result.provider,
        "known": result.known,
        "certified": result.certified,
        "overall_score": result.overall_score,
        "has_reported_incidents": result.has_reported_incidents,
        "error": result.error,
    }


def make_trust_gate_node(
    *,
    min_score: float = 0.0,
    require_known: bool = False,
    default_provider: str = "unknown",
    provider_map: dict[str, str] | None = None,
    client: TrustClient | None = None,
):
    """Build a LangGraph node that gates on `state["tool_call"]`.

    The proposed tool call's name is looked up in the Trust Index as
    `model_name`, with `provider` resolved from `provider_map` (falling
    back to `default_provider`) — the same registration convention the
    LangChain middleware uses, so a tool assessed once is recognized by
    both integrations.

    Below `min_score` (or unknown, when `require_known=True`), the node
    calls `interrupt()` with the trust-check details and expects the
    resume value to be the literal string `"approve"` or `"reject"`
    (anything else is treated as a rejection, fail-closed for the
    human-decision path — unlike the automatic pass/fail default, an
    explicit interrupt reaching a human should not silently proceed on
    an unrecognized response).
    """
    _require_langgraph()
    resolved_client = client or TrustClient()
    resolved_provider_map = provider_map or {}

    def trust_gate_node(state: Any) -> dict[str, Any]:
        tool_call = _get_tool_call(state)
        if not tool_call:
            return {"trust_gate_status": "skipped", "trust_check": None}

        name = tool_call["name"]
        provider = resolved_provider_map.get(name, default_provider)
        result = resolved_client.check(name, provider)
        summary = _result_summary(result)

        if result.passes(min_score=min_score, require_known=require_known):
            return {"trust_gate_status": "approved", "trust_check": summary}

        decision = interrupt({
            "reason": "trust_gate_below_threshold",
            "tool_call": tool_call,
            "trust_check": summary,
            "min_score": min_score,
            "require_known": require_known,
        })
        status: TrustGateStatus = "approved" if decision == "approve" else "rejected"
        return {"trust_gate_status": status, "trust_check": summary}

    return trust_gate_node
