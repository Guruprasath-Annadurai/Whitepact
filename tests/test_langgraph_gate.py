"""Tests for make_trust_gate_node — the LangGraph interrupt()-based gate
described in GAME_CHANGER_BUILD_PLAN.md Phase B. Runs against a real
compiled LangGraph graph with a real checkpointer, not a mocked
interrupt() — the whole point of this adapter is the pause/resume
mechanics, which a mock would hide."""

from __future__ import annotations

from typing import Any, TypedDict
from unittest.mock import MagicMock

import pytest

langgraph = pytest.importorskip("langgraph")

from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402
from langgraph.graph import END, START, StateGraph  # noqa: E402
from langgraph.types import Command  # noqa: E402

from responsibleai.integrations.client import TrustCheckResult, TrustClient  # noqa: E402
from responsibleai.integrations.langgraph_gate import make_trust_gate_node  # noqa: E402


class _State(TypedDict):
    tool_call: dict[str, Any]
    trust_gate_status: str | None
    trust_check: dict[str, Any] | None


def _client_returning(result: TrustCheckResult) -> MagicMock:
    client = MagicMock(spec=TrustClient)
    client.check.return_value = result
    return client


def _build_graph(node):
    builder = StateGraph(_State)
    builder.add_node("trust_gate", node)
    builder.add_edge(START, "trust_gate")
    builder.add_edge("trust_gate", END)
    return builder.compile(checkpointer=InMemorySaver())


class TestApprovedPath:
    def test_high_score_passes_without_interrupting(self) -> None:
        client = _client_returning(
            TrustCheckResult(
                model="good-tool",
                provider="unknown",
                known=True,
                trust_score={"overall": 95.0},
                certified=True,
                has_reported_incidents=False,
            )
        )
        graph = _build_graph(make_trust_gate_node(min_score=50, client=client))
        config = {"configurable": {"thread_id": "t-approved"}}

        out = graph.invoke({"tool_call": {"name": "good-tool", "args": {}, "id": "c1"}}, config)
        assert "__interrupt__" not in out
        assert out["trust_gate_status"] == "approved"


class TestNoToolCall:
    def test_missing_tool_call_is_skipped(self) -> None:
        client = MagicMock(spec=TrustClient)
        graph = _build_graph(make_trust_gate_node(min_score=50, client=client))
        config = {"configurable": {"thread_id": "t-skip"}}

        out = graph.invoke({"tool_call": None}, config)
        assert out["trust_gate_status"] == "skipped"
        client.check.assert_not_called()


class TestBlockedPathInterruptAndResume:
    def _low_score_client(self) -> MagicMock:
        return _client_returning(
            TrustCheckResult(
                model="risky-tool",
                provider="unknown",
                known=True,
                trust_score={"overall": 5.0},
                certified=False,
                has_reported_incidents=True,
            )
        )

    def test_low_score_pauses_with_an_interrupt(self) -> None:
        graph = _build_graph(make_trust_gate_node(min_score=50, client=self._low_score_client()))
        config = {"configurable": {"thread_id": "t-interrupt"}}

        out = graph.invoke({"tool_call": {"name": "risky-tool", "args": {}, "id": "c1"}}, config)
        assert "__interrupt__" in out
        payload = out["__interrupt__"][0].value
        assert payload["reason"] == "trust_gate_below_threshold"
        assert payload["trust_check"]["overall_score"] == 5.0

    def test_resume_approve_marks_approved(self) -> None:
        graph = _build_graph(make_trust_gate_node(min_score=50, client=self._low_score_client()))
        config = {"configurable": {"thread_id": "t-approve"}}
        graph.invoke({"tool_call": {"name": "risky-tool", "args": {}, "id": "c1"}}, config)

        out = graph.invoke(Command(resume="approve"), config)
        assert out["trust_gate_status"] == "approved"

    def test_resume_reject_marks_rejected(self) -> None:
        graph = _build_graph(make_trust_gate_node(min_score=50, client=self._low_score_client()))
        config = {"configurable": {"thread_id": "t-reject"}}
        graph.invoke({"tool_call": {"name": "risky-tool", "args": {}, "id": "c1"}}, config)

        out = graph.invoke(Command(resume="reject"), config)
        assert out["trust_gate_status"] == "rejected"

    def test_resume_with_unrecognized_value_fails_closed(self) -> None:
        graph = _build_graph(make_trust_gate_node(min_score=50, client=self._low_score_client()))
        config = {"configurable": {"thread_id": "t-garbage"}}
        graph.invoke({"tool_call": {"name": "risky-tool", "args": {}, "id": "c1"}}, config)

        out = graph.invoke(Command(resume="banana"), config)
        assert out["trust_gate_status"] == "rejected"


class TestWithoutCheckpointer:
    def test_still_interrupts_but_state_is_not_persisted(self) -> None:
        """Documents actual LangGraph behavior for this module's users:
        `interrupt()` still pauses execution and returns an Interrupt
        without a checkpointer configured — it does not raise — but per
        `interrupt()`'s own docs, resuming relies on persisted state, so a
        checkpointer is required for the pause/resume cycle to actually
        work end-to-end (see TestBlockedPathInterruptAndResume above,
        which does configure one)."""
        client = _client_returning(
            TrustCheckResult(
                model="risky-tool",
                provider="unknown",
                known=True,
                trust_score={"overall": 5.0},
                certified=False,
                has_reported_incidents=False,
            )
        )
        builder = StateGraph(_State)
        builder.add_node("trust_gate", make_trust_gate_node(min_score=50, client=client))
        builder.add_edge(START, "trust_gate")
        builder.add_edge("trust_gate", END)
        uncheckpointed = builder.compile()  # no checkpointer

        out = uncheckpointed.invoke({"tool_call": {"name": "risky-tool", "args": {}, "id": "c1"}})
        assert "__interrupt__" in out
