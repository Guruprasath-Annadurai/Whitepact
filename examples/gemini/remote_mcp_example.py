"""Configure WhitePact as a remote MCP server for Gemini's Interactions API.

Reads credentials from the environment only.

    export GEMINI_API_KEY=...
    export WHITEPACT_API_KEY=...
    python examples/gemini/remote_mcp_example.py

Constraints confirmed from Gemini's current Remote MCP docs (see
docs/integrations/gemini.md):
  - Streamable HTTP only -- do not configure SSE here.
  - Server name must not contain a hyphen -- "whitepact", not "white-pact".
"""

from __future__ import annotations

import os
import sys

WHITEPACT_MCP_URL = "https://whitepact-mcp-http.onrender.com/mcp"
SERVER_NAME = "whitepact"  # no hyphen -- see module docstring

ALLOWED_TOOLS = [
    "rai_scan",
    "rai_trust_score",
    "rai_policy_check",
]


def build_remote_mcp_tool(whitepact_api_key: str) -> dict:
    return {
        "mcp_server": {
            "name": SERVER_NAME,
            "url": WHITEPACT_MCP_URL,
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {whitepact_api_key}"},
            "allowed_tools": ALLOWED_TOOLS,
        }
    }


def main() -> int:
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    whitepact_api_key = os.environ.get("WHITEPACT_API_KEY")

    if not whitepact_api_key:
        print("WHITEPACT_API_KEY not set in environment.", file=sys.stderr)
        return 1
    if not gemini_api_key:
        print(
            "GEMINI_API_KEY not set -- printing the remote MCP tool config "
            "only, not calling the live Gemini API.",
            file=sys.stderr,
        )
        print(build_remote_mcp_tool(whitepact_api_key))
        return 0

    try:
        from google import genai
    except ImportError:
        print("pip install google-genai", file=sys.stderr)
        return 1

    client = genai.Client(api_key=gemini_api_key)
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents="Run rai_trust_score on: 'Our system is 100% bias-free.'",
        config={"tools": [build_remote_mcp_tool(whitepact_api_key)]},
    )
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
