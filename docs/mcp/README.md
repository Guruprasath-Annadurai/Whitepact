# WhitePact MCP integration

WhitePact `1.2.6` exposes **30 tools** and **20 advertised resources** through
one MCP server. The resource count is 10 distinct resources advertised under
the preferred `whitepact://` and compatible legacy `rai://` URI schemes.

These counts come from `TOOL_DEFS` and `RESOURCE_DEFS`, are mirrored in
`server.json`, and are checked by `scripts/check_mcp_docs.py` and the MCP test
suite. They are not a hand-maintained marketing estimate.

## Local stdio setup

```bash
python -m pip install "rai-governance-platform[mcp]==1.2.6"
whitepact-mcp
```

Typical client configuration:

```json
{
  "mcpServers": {
    "whitepact": {
      "command": "whitepact-mcp"
    }
  }
}
```

`responsibleai-mcp` remains a compatible command alias. Stdio is local and
does not require a WhitePact API key.

## Remote transport

The project implements Streamable HTTP at `/mcp` and legacy SSE. Remote
deployments require authentication. The public reference endpoint and its
current availability are deployment evidence, not implied by source support;
run `python scripts/integration_smoke.py` with a valid deployment key before
relying on it.

## Status vocabulary

- **COMPATIBLE**: protocol/configuration is supported by WhitePact.
- **TESTED**: the named client and version completed a real connection test.
- **LISTED**: a directory currently publishes the server entry.
- **SUBMITTED**: a review request exists but is not approved.
- **APPROVED**: the provider explicitly accepted the listing.
- **UNVERIFIED**: no current direct evidence.

These states are deliberately separate. See the canonical
[`platform compatibility matrix`](../integrations/PLATFORM_COMPATIBILITY.md)
for dated client evidence and limitations.
