# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Populates ``AgentContext.trust_state`` from the public Trust Index —
closing the gap ``governance/models.py`` used to flag: the field existed
on ``AgentContext`` since Phase 8, but nothing ever wrote to it.

Reuses ``integrations.client.TrustClient`` (the same HTTP client the
LangChain/LangGraph/ADK trust-gate integrations already use) rather than
adding a second way to call the Trust Index API.
"""

from __future__ import annotations

from responsibleai.governance.models import AgentContext
from responsibleai.integrations.client import TrustClient


async def enrich_agent_trust_state(agent: AgentContext, trust_client: TrustClient) -> AgentContext:
    """Mutates and returns *agent* with ``trust_state`` populated, if
    ``agent.provider``/``agent.model`` are both set — an action that
    doesn't name a third-party model has nothing for the Trust Index to
    look up, so this is a no-op in that case rather than an error.
    Fails open on any lookup error (network, timeout, unknown model) via
    ``TrustCheckResult.error`` — `WhitePactRuntimeGateway`'s consultation
    of ``trust_state`` already accounts for that (``known=False`` never
    triggers a low-trust downgrade)."""
    if agent.provider and agent.model:
        agent.trust_state = await trust_client.check_async(agent.model, agent.provider)
    return agent
