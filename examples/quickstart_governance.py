"""README quickstart: evaluate one agent action with the governance gateway.

Runs offline: no LLM call, no database, no network. Kept in sync with the
README by ``tests/test_readme_quickstart.py``.
"""

from responsibleai.governance import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
)

gateway = WhitePactRuntimeGateway()

# Who is acting: an agent authenticated with an API key belonging to org "acme".
identity = IdentityContext(identity_id="key-1", kind="api_key", org_id="acme")
agent = AgentContext(identity=identity, framework="mcp-client")

# What it was delegated to do: MCP tool calls, plus deployments that need a human.
authority = AuthorityContext(
    delegated_by="acme",
    granted_action_types=frozenset({"mcp_tool_call", "deployment"}),
    require_approval_for=frozenset({"deployment"}),
)

for action in (
    ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health"),
    ActionRequest(agent=agent, action_type="deployment", target="prod"),
    ActionRequest(agent=agent, action_type="payment", target="vendor-42"),
):
    result = gateway.evaluate(action, authority)
    print(f"{action.action_type:>14} -> {result.decision.value}  {result.reason_codes}")
