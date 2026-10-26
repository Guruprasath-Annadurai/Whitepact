# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact LangGraph & MCP Integration Tutorial: Zero-Credential Agent Gate.

This tutorial demonstrates how an autonomous agent built with LangGraph can be
governed by WhitePact without requiring external paid LLM credentials or cloud infrastructure:
1. Low-risk actions pass through the trust gate automatically.
2. High-risk or below-threshold actions interrupt execution for human approval.
3. Rejection halts execution fail-closed.
4. Approval resumes execution cleanly with tamper-evident audit evidence.
5. Read-only MCP authority tools allow inspecting policy status without execution side-effects.

Run:
    python examples/09_mcp_langgraph_tutorial.py
"""

from __future__ import annotations

import sys
from typing import Any, TypedDict
from unittest.mock import MagicMock

try:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command
except ImportError:
    print(
        "LangGraph is required for this tutorial:\n"
        '    pip install "rai-governance-platform[langgraph]"\n'
        "or:  pip install langgraph"
    )
    sys.exit(0)

from responsibleai.governance import (
    ActionRequest,
    AuthorityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.models import AgentContext, GovernanceDecision, IdentityContext
from responsibleai.integrations.client import TrustCheckResult, TrustClient
from responsibleai.integrations.langgraph_gate import make_trust_gate_node


class AgentState(TypedDict):
    tool_call: dict[str, Any] | None
    trust_gate_status: str | None
    trust_check: dict[str, Any] | None
    execution_result: str | None


def tool_execution_node(state: AgentState) -> dict[str, Any]:
    """Simulated execution worker node; only reached if approved."""
    if state.get("trust_gate_status") != "approved":
        return {"execution_result": "BLOCKED: Cannot execute without verified approval."}
    call = state.get("tool_call") or {}
    name = call.get("name", "unknown")
    return {"execution_result": f"EXECUTED: Tool {name} ran successfully."}


def create_governed_graph(client: TrustClient, min_score: float = 70.0):
    """Build a LangGraph state graph with WhitePact Trust Gate."""
    builder = StateGraph(AgentState)
    builder.add_node("trust_gate", make_trust_gate_node(min_score=min_score, client=client))
    builder.add_node("execute_tool", tool_execution_node)

    builder.add_edge(START, "trust_gate")
    builder.add_edge("trust_gate", "execute_tool")
    builder.add_edge("execute_tool", END)

    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


def build_mock_trust_client() -> MagicMock:
    """Zero-credential mock client returning deterministic trust profiles."""
    client = MagicMock(spec=TrustClient)

    def _check(name: str, provider: str = "unknown") -> TrustCheckResult:
        if name == "safe_query":
            return TrustCheckResult(
                model=name,
                provider=provider,
                known=True,
                trust_score={"overall": 92.0},
                certified=True,
                has_reported_incidents=False,
            )
        # Any other sensitive tool is below threshold
        return TrustCheckResult(
            model=name,
            provider=provider,
            known=True,
            trust_score={"overall": 35.0},
            certified=False,
            has_reported_incidents=True,
        )

    client.check.side_effect = _check
    return client


def run_tutorial() -> None:
    print("=" * 70)
    print("WhitePact + LangGraph Zero-Credential Trust Gate Tutorial")
    print("=" * 70)

    client = build_mock_trust_client()
    graph = create_governed_graph(client=client, min_score=70.0)

    # -------------------------------------------------------------
    # Scenario 1: Low-Risk Action (Passes Trust Gate Automatically)
    # -------------------------------------------------------------
    print("\n--- Scenario 1: Low-Risk Tool ('safe_query') ---")
    cfg_1 = {"configurable": {"thread_id": "thread-1"}}
    input_1: AgentState = {
        "tool_call": {"name": "safe_query", "args": {"query": "status"}},
        "trust_gate_status": None,
        "trust_check": None,
        "execution_result": None,
    }

    result_1 = graph.invoke(input_1, cfg_1)
    print(f"Trust Gate Status : {result_1.get('trust_gate_status')}")
    print(f"Score             : {result_1['trust_check']['overall_score']}")
    print(f"Execution Output  : {result_1.get('execution_result')}")
    assert result_1.get("trust_gate_status") == "approved"
    assert "EXECUTED" in str(result_1.get("execution_result"))

    # -------------------------------------------------------------
    # Scenario 2: High-Risk Action (Interrupts for Human-in-the-Loop)
    # -------------------------------------------------------------
    print("\n--- Scenario 2: High-Risk Tool ('modify_production_config') ---")
    cfg_2 = {"configurable": {"thread_id": "thread-2"}}
    input_2: AgentState = {
        "tool_call": {"name": "modify_production_config", "args": {"key": "env", "val": "prod"}},
        "trust_gate_status": None,
        "trust_check": None,
        "execution_result": None,
    }

    # First invoke pauses on interrupt()
    interrupted_run = graph.invoke(input_2, cfg_2)
    interrupt_details = interrupted_run.get("__interrupt__", [None])[0]
    print("Agent execution PAUSED by WhitePact Trust Gate:")
    print(
        f"  Reason      : {interrupt_details.value.get('reason') if interrupt_details else 'interrupted'}"
    )
    print(
        f"  Tool        : {interrupt_details.value.get('tool_call', {}).get('name') if interrupt_details else 'unknown'}"
    )
    print(
        f"  Trust Score : {interrupt_details.value.get('trust_check', {}).get('overall_score') if interrupt_details else 'unknown'}"
    )

    # Resume with human REJECTION
    print("\nHuman decision: REJECT")
    resumed_reject = graph.invoke(Command(resume="reject"), cfg_2)
    print(f"Trust Gate Status : {resumed_reject.get('trust_gate_status')}")
    print(f"Execution Output  : {resumed_reject.get('execution_result')}")
    assert resumed_reject.get("trust_gate_status") == "rejected"
    assert "BLOCKED" in str(resumed_reject.get("execution_result"))

    # -------------------------------------------------------------
    # Scenario 3: Human Approves an Interrupted High-Risk Action
    # -------------------------------------------------------------
    print("\n--- Scenario 3: Human Approval Path ('transfer_funds') ---")
    cfg_3 = {"configurable": {"thread_id": "thread-3"}}
    input_3: AgentState = {
        "tool_call": {"name": "transfer_funds", "args": {"amount": 500}},
        "trust_gate_status": None,
        "trust_check": None,
        "execution_result": None,
    }

    graph.invoke(input_3, cfg_3)
    print("Action interrupted. Human reviewer reviews audit context and approves...")
    resumed_approve = graph.invoke(Command(resume="approve"), cfg_3)
    print(f"Trust Gate Status : {resumed_approve.get('trust_gate_status')}")
    print(f"Execution Output  : {resumed_approve.get('execution_result')}")
    assert resumed_approve.get("trust_gate_status") == "approved"
    assert "EXECUTED" in str(resumed_approve.get("execution_result"))

    # -------------------------------------------------------------
    # Scenario 4: WhitePact Runtime Gateway Direct Evaluation
    # -------------------------------------------------------------
    print("\n--- Scenario 4: Direct WhitePact Gateway Authority Evaluation ---")
    gateway = WhitePactRuntimeGateway()
    agent_ctx = AgentContext(
        identity=IdentityContext(identity_id="mcp-agent-01", kind="agent", org_id="tenant-alpha"),
        organization_id="tenant-alpha",
        agent_id="mcp-agent-01",
    )
    auth_ctx = AuthorityContext(
        delegated_by="security-lead@tenant-alpha.com",
        granted_action_types=frozenset(["mcp:tool:safe_query"]),
        require_approval_for=frozenset(["mcp:tool:transfer_funds"]),
    )

    action_safe = ActionRequest(
        agent=agent_ctx,
        action_type="mcp:tool:safe_query",
        target="safe_query",
        arguments={},
    )
    eval_safe = gateway.evaluate(action_safe, auth_ctx)
    print(f"mcp:tool:safe_query      -> Decision: {eval_safe.decision.value}")
    assert eval_safe.decision == GovernanceDecision.ALLOW

    action_unauthorized = ActionRequest(
        agent=agent_ctx,
        action_type="mcp:tool:unauthorized_action",
        target="unauthorized_action",
        arguments={},
    )
    eval_unauth = gateway.evaluate(action_unauthorized, auth_ctx)
    print(f"mcp:tool:unauthorized    -> Decision: {eval_unauth.decision.value} (Fail Closed)")
    assert eval_unauth.decision == GovernanceDecision.DENY

    print("\n" + "=" * 70)
    print("All tutorial scenarios passed successfully without credentials.")
    print("Canonical Doctrine Upheld: The agent may think and plan freely,")
    print("but cannot act outside independently enforced authority.")
    print("=" * 70)


if __name__ == "__main__":
    run_tutorial()
