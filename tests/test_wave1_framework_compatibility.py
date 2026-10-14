"""Real optional-framework consumers; no external model calls or authority claims.

The localhost fixture is a controlled provider contract, not the WhitePact
governance runtime. These checks prove framework/SDK compatibility only.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, TypedDict

import pytest


@pytest.fixture
def provider_contract(monkeypatch):
    monkeypatch.setenv("WHITEPACT_TRUST_FAILURE_MODE", "closed")
    state = {"known": True, "score": 95, "requests": [], "outcome": {"result": "ok"}}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            state["requests"].append(("GET", self.path))
            self.respond({"known": state["known"], "trust_score": {"overall": state["score"]}})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            state["requests"].append(("POST", self.path, body))
            self.respond(state["outcome"])

        def respond(self, data):
            body = json.dumps(data).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize("known,score,executions", [(True, 95, 1), (True, 5, 0), (False, 95, 0)])
def test_langchain_real_request_and_structured_tool(provider_contract, known, score, executions):
    pytest.importorskip("langchain")
    from langchain.agents.middleware.types import ToolCallRequest
    from langchain_core.tools import StructuredTool

    from responsibleai.integrations.client import TrustClient
    from responsibleai.integrations.langchain_middleware import TrustGateMiddleware

    origin, state = provider_contract
    state.update(known=known, score=score)
    effects = []

    def local_probe(value: str) -> str:
        """Non-consequential local compatibility probe."""
        effects.append(value)
        return value

    tool = StructuredTool.from_function(local_probe)
    call = {"name": tool.name, "args": {"value": "probe"}, "id": "compat-1", "type": "tool_call"}
    request = ToolCallRequest(tool_call=call, tool=tool, state={"messages": []}, runtime=None)
    result = TrustGateMiddleware(min_score=70, client=TrustClient(origin)).wrap_tool_call(
        request, lambda req: req.tool.invoke(req.tool_call)
    )
    assert len(effects) == executions
    assert result.tool_call_id == "compat-1"
    assert result.status == ("success" if executions else "error")
    assert len(state["requests"]) == 1


def test_langgraph_real_checkpoint_resume_rechecks_unknown(provider_contract):
    pytest.importorskip("langgraph")
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Command

    from responsibleai.integrations.client import TrustClient
    from responsibleai.integrations.langgraph_gate import make_trust_gate_node

    class State(TypedDict):
        tool_call: dict[str, Any]
        trust_gate_status: str
        trust_check: dict[str, Any]

    origin, state = provider_contract
    state["score"] = 5
    builder = StateGraph(State)
    builder.add_node("gate", make_trust_gate_node(min_score=70, client=TrustClient(origin)))
    builder.add_edge(START, "gate")
    builder.add_edge("gate", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "compat-resume"}}
    result = graph.invoke({"tool_call": {"name": "probe", "args": {}, "id": "g1"}}, config)
    assert result["__interrupt__"]
    state["known"] = False
    result = graph.invoke(Command(resume="not-an-approval"), config)
    assert result["trust_gate_status"] == "rejected"
    assert result["trust_check"]["known"] is False
    assert len(state["requests"]) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("framework", ["openai", "adk"])
@pytest.mark.parametrize(
    "response,completed,uncertain",
    [
        ({"result": "ok", "outcome_status": "SUCCEEDED"}, True, False),
        ({"error": "governance_denied"}, False, False),
        ({"error": "governance_approval_required", "approval_id": "ap-1"}, False, False),
        ({"error": "governance_unknown_outcome"}, False, True),
        ({"decision": "DENY"}, False, False),
        ({"result": "not-success", "decision": "QUARANTINE"}, False, False),
        ({"result": "not-success", "status": "FAILED"}, False, False),
        ({"result": "not-success", "status": "PENDING"}, False, False),
        ({}, False, False),
        ({"result": {"isError": True}}, False, False),
    ],
)
async def test_real_framework_tools_preserve_sdk_outcomes(
    provider_contract, framework, response, completed, uncertain
):
    from rai_client.governance import GovernanceRuntimeClient

    origin, state = provider_contract
    state["outcome"] = response
    client = GovernanceRuntimeClient("local-test-key", origin)

    async def governed_probe(value: str) -> dict:
        """Ask the server to govern a probe; never execute a downstream action locally."""
        outcome = await client.call_tool("probe", {"value": value})
        return {"completed": outcome.completed, "uncertain": outcome.reconciliation_required}

    if framework == "openai":
        pytest.importorskip("agents")
        from agents import Agent, RunContextWrapper, function_tool
        from agents.tool_context import ToolContext

        tool = function_tool(governed_probe)
        agent = Agent(name="compatibility", tools=[tool])
        assert agent.tools[0] is tool
        context = ToolContext.from_agent_context(
            RunContextWrapper(context=None),
            "tool-1",
            agent=agent,
            tool_name=tool.name,
            tool_arguments='{"value":"probe"}',
        )
        result = await tool.on_invoke_tool(context, '{"value":"probe"}')
    else:
        pytest.importorskip("google.adk")
        from google.adk.agents import LlmAgent
        from google.adk.tools import FunctionTool

        tool = FunctionTool(governed_probe)
        agent = LlmAgent(name="compatibility", model="gemini-2.0-flash", tools=[tool])
        assert agent.tools[0] is tool
        result = await tool.run_async(args={"value": "probe"}, tool_context=None)
    assert result == {"completed": completed, "uncertain": uncertain}
    assert state["requests"] == [
        (
            "POST",
            "/api/v1/governance/tools/call",
            {"name": "probe", "arguments": {"value": "probe"}, "purpose": "sdk-governance"},
        )
    ]
