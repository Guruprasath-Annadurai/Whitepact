# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""One-shot call; configured server authority is required independently of this client."""

import asyncio
import json
import os

from rai_client.governance import GovernanceRuntimeClient


async def main() -> None:
    client = GovernanceRuntimeClient(
        os.environ["WHITEPACT_API_KEY"],
        base_url=os.environ.get("WHITEPACT_URL", "http://127.0.0.1:8765"),
        timeout=5,
    )
    result = await client.call_tool(
        os.environ["WHITEPACT_TOOL"],
        purpose=os.environ.get("WHITEPACT_PURPOSE", "sdk-governance"),
    )
    print(
        json.dumps(
            {
                "completed": result.completed,
                "denied": result.denied,
                "requires_approval": result.requires_approval,
                "uncertain": result.reconciliation_required,
                "approval_id": result.approval_id,
            }
        )
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # Neither tracebacks nor response bodies are safe example output.
        print("No confirmed answer. Do not retry a mutation; reconcile first.")
        raise SystemExit(1) from None
