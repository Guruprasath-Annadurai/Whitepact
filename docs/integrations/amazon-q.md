# Amazon Q Developer (legacy — see kiro-cli.md)

**Status**: LEGACY / SUPERSEDED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-16.

**Amazon Q Developer is being retired in favor of Kiro.** Confirmed
2026-08-16: new Amazon Q Developer signups closed 2026-05-15, and
existing IDE plugins/subscriptions reach end of support 2027-04-30. New
setups should target **[`kiro-cli.md`](kiro-cli.md)** instead — this
page is kept only for founders already on an existing Amazon Q Developer
install who haven't migrated yet.

## If you're still on Amazon Q Developer

The config format below was Amazon Q CLI's own remote-MCP shape
(distinct from Kiro's — Amazon Q uses an explicit `"transport": "http"`
field that Kiro doesn't have):

```json
{
  "mcpServers": {
    "whitepact": {
      "url": "https://whitepact-mcp-http.onrender.com/mcp",
      "transport": "http",
      "headers": {
        "Authorization": "Bearer <YOUR_WHITEPACT_API_KEY>"
      }
    }
  }
}
```

Config path: `~/.aws/amazonq/mcp.json` (global) or `.amazonq/mcp.json`
(workspace). If you install Kiro, it auto-copies this into
`~/.kiro/settings/mcp.json` — check there first rather than
re-configuring by hand.

## Founder action

Migrate to Kiro CLI per `kiro-cli.md` rather than invest further in
Amazon Q Developer, which is not accepting new signups.
