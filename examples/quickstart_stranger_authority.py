# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Minimal stranger quickstart: authority allow/deny, evidence, revocation.

Run from repository root (no API keys, no Docker):

    python examples/quickstart_stranger_authority.py

Uses in-process SQLite (:memory:), ``WhitePactRuntimeGateway``, and
``DelegationRepository`` — the same building blocks exercised in
``tests/test_workflow_authority.py`` and ``examples/08_whitepact_enterprise_scenario.py``.

For the full enterprise narrative (approvals, workflow sequences, bundles),
run ``python examples/08_whitepact_enterprise_scenario.py`` next.
"""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, "src")

from responsibleai.db import DelegationRepository, EvidenceRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import build_evidence_record

ORG_ID = "quickstart-org"
AGENT_ID = "quickstart-agent"
ACTION_TOOL = "payment.execute"  # stand-in for a governed tool/action type


def _agent() -> AgentContext:
    identity = IdentityContext(identity_id=AGENT_ID, kind="agent", org_id=ORG_ID)
    return AgentContext(identity=identity, agent_id=AGENT_ID, framework="quickstart")


async def main() -> None:
    print("WhitePact stranger quickstart (local, in-memory)\n")

    engine = create_engine(":memory:")
    await engine.init()
    delegations = DelegationRepository(engine)
    evidence_repo = EvidenceRepository(engine)
    gateway = WhitePactRuntimeGateway()

    # 2–4. Authority context + agent + one governed action type
    print("[1] Grant delegated authority to the agent")
    record = await delegations.grant(
        ORG_ID,
        AGENT_ID,
        granted_action_types=frozenset({ACTION_TOOL}),
        constraints={"max_value_usd": 5_000.0},
        purpose="quickstart evaluation",
        granted_by="org-admin",
    )
    authority: AuthorityContext = record.to_authority_context()
    agent = _agent()
    print(f"    granted_action_types={sorted(authority.granted_action_types)}")

    # 5–6. Allowed governed action
    print("\n[2] Submit an in-authority action → expect ALLOW")
    allowed = ActionRequest(
        agent=agent,
        action_type=ACTION_TOOL,
        target="vendor-001",
        arguments={"amount_usd": 100.0},
    )
    allow_result = gateway.evaluate(allowed, authority)
    assert allow_result.decision == GovernanceDecision.ALLOW
    print(f"    decision={allow_result.decision.value}")

    # 7. Denied action (not granted)
    print("\n[3] Submit an action outside the grant → expect DENY")
    denied = ActionRequest(
        agent=agent,
        action_type="wire.international",
        target="acct-offshore",
        arguments={"amount_usd": 50.0},
    )
    deny_result = gateway.evaluate(denied, authority)
    assert deny_result.decision == GovernanceDecision.DENY
    print(f"    decision={deny_result.decision.value}  reasons={deny_result.reason_codes[:2]}")

    # 8. Evidence / audit
    print("\n[4] Persist tamper-evident evidence for the allow decision")
    evidence = build_evidence_record(allowed, agent, authority, allow_result)
    stored = await evidence_repo.record(evidence)
    chain_valid = await evidence_repo.verify_chain(ORG_ID)
    print(f"    evidence_id={stored.evidence_id[:12]}...  chain_valid={chain_valid}")

    # 9–10. Revoke delegation → no effective authority remains
    print("\n[5] Revoke the agent's delegation (cascading)")
    revoked_ids = await delegations.revoke_branch(
        ORG_ID, AGENT_ID, revoked_by="org-admin", reason="quickstart cleanup"
    )
    print(f"    revoked_delegation_ids={revoked_ids}")

    fresh = await delegations.get_effective_authority(ORG_ID, AGENT_ID)
    assert fresh is None
    print("    get_effective_authority() → None (no active grant)")

    print(
        "\n[6] Subsequent integration must reload authority (stale in-memory context does not self-heal)"
    )
    stale_allow = gateway.evaluate(allowed, authority)
    print(
        f"    evaluate() with *stale* AuthorityContext still returns {stale_allow.decision.value} — "
        "callers must resolve authority from storage (dashboard/MCP do this on each request)."
    )

    await engine.close()
    print(
        "\nQuickstart complete. Next: docs/quickstart.md (HTTP/Docker) and examples/08_whitepact_enterprise_scenario.py"
    )


if __name__ == "__main__":
    asyncio.run(main())
