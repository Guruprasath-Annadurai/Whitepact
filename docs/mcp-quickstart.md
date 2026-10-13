# MCP quickstart

WhitePact exposes **30 production MCP tools** (verified via `production_tool_count()`
in `src/responsibleai/mcp/tools.py`). Do not inflate this count in integrations.

## Authentication ≠ authority

| Layer | What it proves | What it does **not** prove |
|-------|----------------|-----------------------------|
| MCP / HTTP auth | Caller identity (API key, transport) | Permission to run a specific tool |
| Governance dispatch | Policy + delegation + risk | Nothing without an active grant |

Hosted MCP tools are **read-only** at the protocol level today; onboarding tests
should still treat responses as governance decisions, not implicit grants.

## Self-hosted stdio (local)

**Prerequisites:** Python 3.11+, package with MCP extras.

```bash
pip install "rai-governance-platform[dashboard,mcp]"
# Dashboard must be reachable if tools call back to HTTP (default local URL)
uvicorn responsibleai.dashboard.app:app --port 8765 &
whitepact-mcp
```

Client config (Claude Desktop / Cursor — see `server.json` and `docs/integrations/cursor.md`):

```json
{
  "mcpServers": {
    "whitepact": {
      "command": "whitepact-mcp",
      "args": []
    }
  }
}
```

`whitepact-mcp` and `responsibleai-mcp` are the same entry point.

## Remote Streamable HTTP

Canonical hosted endpoint (from `docs/integrations/README.md`):

- `https://whitepact-mcp-http.onrender.com/mcp` (Streamable HTTP)
- Legacy SSE: `.../sse` (prefer Streamable HTTP for new work)

**Auth:** `Authorization: Bearer <org-scoped-api-key>` from the dashboard
(Settings → API Keys). WhitePact does not act as an OAuth authorization server.

## Example flow (conceptual)

1. Client connects with a **valid API key** (authentication).
2. Client calls a governance tool (e.g. trust scan / policy lookup).
3. WhitePact resolves **delegation + policy** for the org; returns ALLOW/DENY outcome.
4. A denied tool call returns a structured block — not an execution grant.

Protocol smoke (against live or local endpoint):

```bash
python scripts/integration_smoke.py
```

## Further reading

- [`README.md`](../README.md) — MCP section
- [`compliance/MCP_DISTRIBUTION_GUIDE.md`](../compliance/MCP_DISTRIBUTION_GUIDE.md)
- [`docs/integrations/PLATFORM_COMPATIBILITY.md`](integrations/PLATFORM_COMPATIBILITY.md)
