# Cursor

**Status**: VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-15.

## Example config

[`../../.cursor-example/mcp.json`](../../.cursor-example/mcp.json) — named
`.cursor-example` deliberately, **not** `.cursor/mcp.json`, so it never
gets picked up automatically by contributors working in this repo. Copy
its contents into your own `~/.cursor/mcp.json` (global) or a project's
`.cursor/mcp.json` (project-scoped) yourself.

## Endpoint

```
https://whitepact-mcp-http.onrender.com/mcp
```

Streamable HTTP, per Cursor's documented remote MCP support.

## Authentication

Bearer API key via the `headers` block, as shown in the example.

## Setup

1. Copy `.cursor-example/mcp.json`'s `whitepact` entry into your own
   Cursor MCP config.
2. Replace `<YOUR_WHITEPACT_API_KEY>` with a real key from your WhitePact
   dashboard.
3. Reload Cursor / reopen the project.

## Tool approval

Cursor prompts for per-tool approval by default. Since all 27 WhitePact
tools are read-only, approving "Always allow" for WhitePact tools carries
no destructive risk — but that's your call to make, not a default this
doc sets for you.

## "Add to Cursor" one-click button

**Not implemented.** Cursor does document a deep-link format for
one-click server installs, but this was not independently re-confirmed
against Cursor's current official docs during this pass, and the task's
own instruction is explicit: don't invent a custom URI scheme. Rather
than guess at the encoding and ship something that might silently break,
this is left as a founder action once someone can verify the current
format directly against Cursor's docs.

## Verification steps

Open Cursor's MCP settings panel after adding the config; `whitepact`
should show as connected with 27 tools listed.

**Verified live 2026-08-15**: added the `whitepact` entry to
`~/.cursor/mcp.json` alongside an existing server, substituted the real
API key, restarted Cursor, and confirmed `whitepact` shows as connected
in Cursor's MCP settings.

## Safe test prompt

> "Use the whitepact MCP server's rai_hallucination tool to check this
> claim: 'Water boils at 150°C at sea level.'"

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Server not listed | Wrong config file scope (global vs. project) | Confirm which `mcp.json` Cursor is reading |
| `401` | Bad header | Re-check `Authorization: Bearer <key>` |

## Cursor Marketplace listing (all-users discoverability)

Config-based install (above) works today for any individual user, but
only reaches people who already have the config. To make WhitePact
discoverable and one-click installable by **all** Cursor users, it needs
to be listed in the official Cursor Marketplace
(`cursor.com/marketplace`) — separate from the community
`cursor.directory`.

Built and pushed 2026-08-15:
- `.cursor-plugin/plugin.json` — manifest with `variables` schema so each
  installer enters their own `WHITEPACT_API_KEY` at install time (no
  shared/embedded key)
- `.cursor-plugin/mcp.json` — server config using `${WHITEPACT_API_KEY}`
  interpolation
- `.cursor-plugin/README.md` — usage docs
- `.cursor-plugin/assets/logo.png` — logo, served via
  `raw.githubusercontent.com`

**Submitted 2026-08-15** at `cursor.com/marketplace/publish` (individual
publisher, org handle `whitepact`) — confirmation received: "Thanks for
applying, we've received your submission." Cursor manually reviews every
submission before listing; follow-up expected at
`marketplace-publishing@cursor.com`. No further action until they
respond.

## Founder action

None required to reach current (VERIFIED) state for config-based
install. Marketplace listing is awaiting Cursor's review response.
