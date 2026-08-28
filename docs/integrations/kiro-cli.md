# Kiro CLI

**Status**: VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-16.

Kiro is AWS's successor to Amazon Q Developer — Amazon Q Developer's IDE
plugins and subscriptions reach end of support 2027-04-30, and new
Amazon Q Developer signups closed 2026-05-15. This doc targets Kiro
directly rather than the retiring product; see `amazon-q.md` for the
legacy path if you're already on Amazon Q Developer and haven't
migrated.

## Prerequisites

- Kiro CLI installed and signed in.
- A WhitePact API key.

## Install (macOS)

```bash
brew install --cask amazon-q
```

Despite the cask name (a holdover from the rebrand), this installs
"Kiro CLI.app" and the `kiro-cli` / `q` binaries. Then sign in per
Kiro's own auth flow — see
[kiro.dev/docs/getting-started/authentication](https://kiro.dev/docs/getting-started/authentication/).

## Endpoint

```
https://YOUR_WHITEPACT_HOST/mcp
```

Streamable HTTP.

## Authentication

Bearer API key via the `headers` block. Kiro's MCP config has no
separate `transport` field for remote servers — presence of `url`
(rather than `command`) is what makes it a remote server. No OAuth
needed since WhitePact runs a static Bearer key, not an Authorization
Server.

## Setup

Global config lives at `~/.kiro/settings/mcp.json` (workspace-scoped
config, if you want it project-local instead, takes priority over
global — see Kiro's own config-scope docs). Copy the `whitepact` entry
from [`../../examples/kiro-cli/mcp-config.json`](../../examples/kiro-cli/mcp-config.json)
into it. The example uses `${WHITEPACT_API_KEY}` interpolation — export
that env var yourself before starting Kiro, or replace it with a literal
key value directly in the file (less good practice, but works).

If you're migrating from Amazon Q Developer's `~/.aws/amazonq/mcp.json`,
Kiro auto-copies existing MCP settings into `~/.kiro/` on first install
— check there before adding this manually, you may already have it.

## Verification steps

Kiro CLI hot-reloads MCP config changes on save — no restart needed.
Ask Kiro to list available tools and confirm `whitepact` shows 27 tools.

**Verified live 2026-08-16**: installed via `brew install --cask
amazon-q` (which installs Kiro CLI, `kiro-cli` binary confirmed at
`~/.local/bin/kiro-cli`), signed in, added `whitepact` to
`~/.kiro/settings/mcp.json` with `${WHITEPACT_API_KEY}` interpolation,
launched `kiro-cli`, and confirmed WhitePact's tools show up.

## Safe test prompt

> "Use the whitepact rai_scan tool to check this text for PII: 'Contact
> John at john@example.com or 555-123-4567.'"

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `401` | Missing/incorrect Bearer header | Re-check `Authorization: Bearer <key>` |
| Server not found | Config in wrong scope (global vs. workspace) | Confirm which `mcp.json` is closest to where you're chatting — Kiro applies the closest-scope config |
| `${WHITEPACT_API_KEY}` not resolving | Env var not exported before Kiro started | `export WHITEPACT_API_KEY=...` then restart Kiro, or use a literal value |

## Security notes

All 30 tools are read-only (`readOnlyHint=True`, `destructiveHint=False`).
Kiro's own per-tool approval / `autoApprove` list still applies —
WhitePact does not bypass client-side approval.

## Founder action

None required to reach current (VERIFIED) state.
