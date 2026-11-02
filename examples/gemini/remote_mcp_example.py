"""Configure WhitePact as a remote MCP server for Gemini's Interactions API.

Reads credentials from the environment only.

    export GEMINI_API_KEY=...
    export WHITEPACT_API_KEY=...
    python examples/gemini/remote_mcp_example.py

Constraints confirmed from Gemini's current Remote MCP docs (see
docs/integrations/gemini.md):
  - Streamable HTTP only -- do not configure SSE here.
  - Server name must not contain a hyphen -- "whitepact", not "white-pact".

Schema verified live 2026-08-14 against the real Interactions API
(google-genai SDK v2.14.0, model="gemini-pro-latest"). Two real,
live-confirmed corrections versus an earlier draft of this script:
  1. `client.models.generate_content(model="gemini-2.5-pro", ...)` is
     the WRONG API for this -- that model returns a live 404
     ("no longer available to new users... use the Interactions API")
     even though it's still listed in the SDK's own Model type hints,
     which are stale relative to the live server. Use
     `client.interactions.create(...)` instead, with a rolling model
     alias ("gemini-pro-latest") that can't go stale the same way.
  2. The correct MCP tool shape for this API is
     `{"type": "mcp_server", "name", "url", "headers", "allowed_tools"}`
     -- a flat dict, not the nested `Tool(mcp_servers=[McpServer(...)])`
     shape used by the older `models.generate_content` path (a
     different, unrelated Tool type in the same SDK). allowed_tools
     really does exist as a scoping mechanism here -- it just lives on
     this type, not the one checked first.
"""

from __future__ import annotations

import os
import sys

WHITEPACT_MCP_URL = "https://whitepact-mcp-http.onrender.com/mcp"
SERVER_NAME = "whitepact"  # no hyphen -- see module docstring
MODEL = "gemini-pro-latest"  # rolling alias -- avoids the exact staleness bug found above

ALLOWED_TOOLS = ["rai_scan", "rai_trust_score", "rai_policy_check"]


def build_remote_mcp_tool(whitepact_api_key: str) -> dict:
    return {
        "type": "mcp_server",
        "name": SERVER_NAME,
        "url": WHITEPACT_MCP_URL,
        "headers": {"Authorization": f"Bearer {whitepact_api_key}"},
        "allowed_tools": [{"tools": ALLOWED_TOOLS}],
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
    response = client.interactions.create(
        model=MODEL,
        input="Run rai_trust_score on: 'Our system is 100% bias-free.'",
        tools=[build_remote_mcp_tool(whitepact_api_key)],
    )
    print(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
