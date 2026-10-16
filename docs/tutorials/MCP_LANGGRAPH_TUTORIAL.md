# Governed Agent Workflows: LangGraph & MCP Integration Tutorial

This tutorial guides you through governing autonomous agents built with **LangGraph** and connecting them to **Model Context Protocol (MCP)** tools using WhitePact's independently enforced runtime authority.

> [!IMPORTANT]
> **Canonical Doctrine**:
> *The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority.*

---

## 1. Why a Trust Gate in LangGraph?

Standard LangChain / LangGraph middleware often faces a binary dilemma: either allow a tool call automatically, or throw an exception and crash the run. 

WhitePact's LangGraph integration uses LangGraph's native `interrupt()` and checkpointer mechanisms:
- **Low-risk / Approved tools**: Pass through the gate immediately.
- **Below-threshold / Sensitive tools**: The graph **pauses safely** and emits an `interrupt` payload detailing the tool call, risk score, and required approval tier.
- **Human Reviewer**: Evaluates the action and resumes the graph using `Command(resume="approve")` or `Command(resume="reject")`.
- **Execution Broker**: If rejected, execution halts **fail-closed** without invoking the underlying tool.

---

## 2. Zero-Credential Quickstart

This tutorial runs entirely locally in-memory without requiring external LLM API keys (OpenAI, Anthropic) or cloud credentials.

### Prerequisites

```bash
pip install "rai-governance-platform[langgraph]"
```

Or when developing inside the repository:
```bash
uv pip install -e ".[langgraph]"
```

### Complete Code Example (`examples/09_mcp_langgraph_tutorial.py`)

Run the verified tutorial directly:
```bash
python examples/09_mcp_langgraph_tutorial.py
```

### Key Implementation Snippets

#### 1. Defining the State Graph with WhitePact Trust Gate

```python
from typing import Any, TypedDict
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END
from responsibleai.integrations.langgraph_gate import make_trust_gate_node

class AgentState(TypedDict):
    tool_call: dict[str, Any] | None
    trust_gate_status: str | None
    trust_check: dict[str, Any] | None
    execution_result: str | None

builder = StateGraph(AgentState)
# Gate requires minimum trust score of 70.0
builder.add_node("trust_gate", make_trust_gate_node(min_score=70.0, client=trust_client))
builder.add_node("execute_tool", tool_execution_node)

builder.add_edge(START, "trust_gate")
builder.add_edge("trust_gate", "execute_tool")
builder.add_edge("execute_tool", END)

# In-memory checkpointer preserves state across interrupts
graph = builder.compile(checkpointer=InMemorySaver())
```

#### 2. Handling the Human-in-the-Loop Interrupt

When a tool scores below the threshold:

```python
config = {"configurable": {"thread_id": "session-42"}}
state_input = {
    "tool_call": {"name": "transfer_funds", "args": {"amount": 500}},
    "trust_gate_status": None,
    "trust_check": None,
    "execution_result": None,
}

# Invocation pauses at trust_gate
interrupted_state = graph.invoke(state_input, config)
interrupt = interrupted_state["__interrupt__"][0]

print("PAUSED:", interrupt.value["reason"])
# Outputs: 'trust_gate_below_threshold'
```

#### 3. Resuming with Human Decision

```python
from langgraph.types import Command

# To Reject:
resumed = graph.invoke(Command(resume="reject"), config)
assert resumed["trust_gate_status"] == "rejected"
# The execute_tool node recognizes the rejection and aborts execution.

# To Approve:
resumed = graph.invoke(Command(resume="approve"), config)
assert resumed["trust_gate_status"] == "approved"
# Execution resumes and runs the tool.
```

---

## 3. Read-Only MCP Authority Tools (Option B Architecture)

In addition to workflow gates, WhitePact exposes narrow, read-only MCP authority inspection tools to AI assistants:
- `whitepact_policy_status`: Inspect active policy version and constraints.
- `whitepact_simulate_policy`: Perform zero-effect dry runs of proposed actions.
- `whitepact_list_pending_approvals`: Enumerate outstanding human approvals.
- `whitepact_verify_evidence`: Verify cryptographic hash-chains of audit records.

These tools are strictly separated from execution workers, cannot mutate policy, cannot mint execution grants, and run in tenant-isolated read-only contexts.
