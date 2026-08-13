"""Configure WhitePact as a remote MCP server for the xAI Grok API.

Reads credentials from the environment only -- never hardcode a key here
or pass one on the command line where it could end up in shell history.

    export XAI_API_KEY=...
    export WHITEPACT_API_KEY=...
    python examples/grok/remote_mcp_example.py

Security note: `allowed_tools` is deliberately scoped to a small
read-only set below rather than left unset (which would expose all 27
WhitePact tools). Widen it once you've confirmed the connection works.
"""

from __future__ import annotations

import os
import sys

WHITEPACT_MCP_URL = "https://whitepact-mcp-http.onrender.com/mcp"

ALLOWED_TOOLS = [
    "rai_scan",
    "rai_trust_score",
    "rai_org_status",
]


def build_remote_mcp_config(whitepact_api_key: str) -> dict:
    return {
        "type": "mcp",
        "server_label": "whitepact",
        "server_url": WHITEPACT_MCP_URL,
        "headers": {"Authorization": f"Bearer {whitepact_api_key}"},
        "allowed_tools": ALLOWED_TOOLS,
    }


def main() -> int:
    xai_api_key = os.environ.get("XAI_API_KEY")
    whitepact_api_key = os.environ.get("WHITEPACT_API_KEY")

    if not whitepact_api_key:
        print("WHITEPACT_API_KEY not set in environment.", file=sys.stderr)
        return 1
    if not xai_api_key:
        print(
            "XAI_API_KEY not set -- printing the remote MCP config only, "
            "not calling the live xAI API.",
            file=sys.stderr,
        )
        print(build_remote_mcp_config(whitepact_api_key))
        return 0

    try:
        from openai import OpenAI  # xAI's API is OpenAI-compatible
    except ImportError:
        print("pip install openai  # xAI's SDK compatibility layer", file=sys.stderr)
        return 1

    client = OpenAI(api_key=xai_api_key, base_url="https://api.x.ai/v1")
    response = client.responses.create(
        model="grok-4",
        input="Use whitepact's rai_scan tool on: 'SSN 123-45-6789, call 555-0100.'",
        tools=[build_remote_mcp_config(whitepact_api_key)],
    )
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
