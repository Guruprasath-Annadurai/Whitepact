# WhitePact — Antigravity CLI Plugin

Configures Antigravity CLI to connect to a deployed WhitePact MCP server via
the remote `serverUrl` transport. The repository's production deployment is an
external RC gate; this template deliberately contains a host placeholder.

This directory follows the official Antigravity plugin manifest format —
see [antigravity.google/docs/plugins](https://antigravity.google/docs/plugins)
— and is distributed directly from this repository rather than a curated
marketplace, since no single official Antigravity plugin directory exists
as of this writing. Marketplace tooling that supports adding a GitHub
repository as a plugin source (e.g. `agy-plugins-cli`) can point at
`Guruprasath-Annadurai/Whitepact` and discover this plugin under `plugins/`.

## Setup

1. Deploy the candidate or obtain the operator's verified public MCP URL and a
   tenant-scoped API key/OAuth access token.
2. Copy `mcp_config.json`, replacing `YOUR_WHITEPACT_HOST` and
   `<YOUR_WHITEPACT_API_KEY>` with the verified values.
3. Place it at `.agents/mcp_config.json` in your workspace, or merge it
   into your global `~/.gemini/config/mcp_config.json`.
4. Antigravity CLI will discover WhitePact's 30 governance tools
   (trust scoring, PII/harm scanning, hallucination and bias detection,
   compliance checks) via the `whitepact` MCP server entry.

## What's in this directory

- `plugin.json` — the required plugin manifest.
- `mcp_config.json` — a Streamable HTTP (`/mcp`) server template. It requires
  a verified host and Bearer credential; see Setup above.

No skills, hooks, or agents are bundled; this plugin's only purpose is
the MCP server connection itself.
