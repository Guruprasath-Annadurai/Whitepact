"""Agent-framework integrations for the ResponsibleAI Trust Index.

Every module here builds on `client.TrustClient` — a plain HTTP client
with no framework dependency. Framework-specific adapters (LangChain,
LangGraph, Google ADK) live in their own modules and import from here,
never the other way around, so `client.py` stays importable with only
this project's existing core dependencies.

See GAME_CHANGER_BUILD_PLAN.md Phase B for why these exist: the trust
check other agents call before invoking a third-party model or tool,
not another "evaluate your own model's output" tool.
"""

from responsibleai.integrations.client import TrustCheckResult, TrustClient
from responsibleai.integrations.gemini_mcp_bridge import GeminiMCPBridge

__all__ = ["GeminiMCPBridge", "TrustCheckResult", "TrustClient"]
