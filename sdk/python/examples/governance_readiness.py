# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only installed SDK onboarding check; credentials never appear in output.

Run after installing the SDK wheel. Server tenant membership and permissions are
required. This check does not create authority, approve actions, or execute tools.
"""

import asyncio
import json
import os

from rai_client.governance import GovernanceRuntimeClient


async def main() -> None:
    client = GovernanceRuntimeClient(
        os.environ["WHITEPACT_API_KEY"],
        os.environ.get("WHITEPACT_URL", "http://127.0.0.1:8765"),
        timeout=5,
    )
    policy = await client.get_policy()
    approvals = await client.list_approvals()
    evidence = await client.list_evidence(limit=10)
    # A bounded list is not complete history, pagination, or proof of non-effect.
    print(
        json.dumps(
            {
                "policy_readable": isinstance(policy, dict),
                "approvals_readable": isinstance(approvals.get("pending"), list),
                "evidence_readable": isinstance(evidence.get("evidence"), list),
                "authority_granted_by_client": False,
            }
        )
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        print(
            "Readiness check unavailable. Verify session/key permissions and server availability."
        )
        raise SystemExit(1) from None
