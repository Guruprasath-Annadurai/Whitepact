# WhitePact — Antigravity CLI Plugin

Connects [Antigravity CLI](https://antigravity.google/) (Google's successor
to Gemini CLI, retired 2026-06-18) to WhitePact's hosted MCP server via the
remote `serverUrl` transport.

This directory follows the official Antigravity plugin manifest format —
see [antigravity.google/docs/plugins](https://antigravity.google/docs/plugins)
— and is distributed directly from this repository rather than a curated
marketplace, since no single official Antigravity plugin directory exists
as of this writing. Marketplace tooling that supports adding a GitHub
repository as a plugin source (e.g. `agy-plugins-cli`) can point at
`Guruprasath-Annadurai/Whitepact` and discover this plugin under `plugins/`.

## Setup

1. Get a WhitePact API key: create a free org at the [dashboard](https://responsibleai-dashboard.onrender.com),
   then go to Settings → API Keys.
2. Copy `mcp_config.json` from this directory, replacing
   `<YOUR_WHITEPACT_API_KEY>` with the real key.
3. Place it at `.agents/mcp_config.json` in your workspace, or merge it
   into your global `~/.gemini/config/mcp_config.json`.
4. Antigravity CLI will discover WhitePact's 27 governance tools
   (trust scoring, PII/harm scanning, hallucination and bias detection,
   compliance checks) via the `whitepact` MCP server entry.

## What's in this directory

- `plugin.json` — the required plugin manifest.
- `mcp_config.json` — the MCP server definition, pointing at
  `whitepact-mcp-http.onrender.com`'s Streamable HTTP transport
  (`/mcp`). Requires a Bearer API key — see Setup above.

No skills, hooks, or agents are bundled; this plugin's only purpose is
the MCP server connection itself.
