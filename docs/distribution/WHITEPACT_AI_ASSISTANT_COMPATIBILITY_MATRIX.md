# AI-assistant compatibility matrix

2026-10-11. "Tested" means a real client of that assistant connected to a WhitePact server and the result was
recorded. **No assistant below was connected in this pass.** The only client exercised is the reference `mcp`
Python SDK 1.29.1.

| Client | Connection path | Tested | Result | Notes |
| --- | --- | --- | --- | --- |
| Reference MCP Python SDK 1.29.1 | Streamable HTTP, Bearer key and OAuth | **Yes** (in-process ASGI) | PASS for initialize, tools/list, resources/list, validation, auth, tenant isolation | `docs/launch/MCP_COMPATIBILITY_MATRIX.md` |
| ChatGPT / Codex | plugin directory (ZIP + hosted MCP) or developer-mode connector | NO | NOT TESTED | needs a verified domain and a ChatGPT account |
| Claude (claude.ai, Claude Code) | custom remote connector or plugin | NO | NOT TESTED | Claude states support for the newest MCP specification; this server's SDK pins `mcp<2` and negotiates up to 2025-11-25. Older negotiated versions are normally accepted, but this is unproven for Claude |
| Grok | grok.com/connectors → Custom, public HTTPS URL | NO | NOT TESTED | no public third-party listing programme described in the official connectors page |
| Gemini, Perplexity, Cursor, others | not researched | NO | NOT ASSESSED | no claim |

Protocol facts that do hold: versions 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 are negotiated as offered; 2026-07-28 is
not implemented by the pinned SDK and is answered with a supported version.
