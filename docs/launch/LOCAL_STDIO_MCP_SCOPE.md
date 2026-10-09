# Local stdio MCP scope

**Decision: intentionally outside the governed product contract.**

`whitepact-mcp` / `responsibleai-mcp` is the community stdio transport. It starts only when `WHITEPACT_MCP_TRUST_DOMAIN=community` (the default for local development). Before the MCP protocol begins, the process writes this to stderr:

`WHITEPACT STDIO: UNGOVERNED LOCAL MODE`

That process does not enforce tenant authority, memory-scope delegation, or execution authorization. Tool calls on it go through `dispatch_tool()` because there is no organization identity to govern. Hosted Streamable HTTP and legacy SSE are the governed paths: they fail closed without tenant-scoped governance, and production refuses to boot unless `mcp_trust_domain=enterprise` and `mcp_governance_enabled=true`.

Enterprise trust domain does not start stdio. It exits with status 2 and does not print the community banner.

Public claims must not describe this local process as protected execution. The hosted product is a separate transport.

Tests: `tests/test_mcp_enterprise_trust_domain.py`.
