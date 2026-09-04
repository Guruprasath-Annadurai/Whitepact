# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Small, deterministic WhitePact authority demo; no API keys or network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from responsibleai.governance import (  # noqa: E402
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import build_evidence_record  # noqa: E402


def main() -> None:
    identity = IdentityContext(identity_id="operator-1", kind="human", org_id="demo-org")
    agent = AgentContext(identity=identity, agent_id="payments-agent", framework="demo")
    authority = AuthorityContext(
        delegated_by="finance-owner",
        granted_action_types=frozenset({"payment.execute"}),
        require_approval_for=frozenset({"payment.execute"}),
    )
    action = ActionRequest(
        agent=agent,
        action_type="payment.execute",
        target="vendor-bank-account",
        arguments={"amount_usd": 8_500.0, "currency": "USD"},
    )

    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    evidence = build_evidence_record(action, agent, authority, decision)

    print("Agent proposes: payment.execute USD 8,500")
    print(f"WhitePact decision: {decision.decision.value}")
    print("Execution proceeded: NO")
    print(
        json.dumps(
            {
                "action_id": evidence.action_id,
                "decision": evidence.decision,
                "reason_codes": evidence.reason_codes,
                "risk_tier": evidence.risk_tier,
                "argument_keys": evidence.argument_keys,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
