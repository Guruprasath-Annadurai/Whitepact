# WS-2 — Runtime authority & MCP security (Lane A)

**Findings:** BLK-P0-02 (stdio governance bypass), BLK-P0-03 (kernel disconnected), supplemental authority/grant/revocation items.

**Base:** WS-1 qualified tree (`0207ed8` / closure `b5641b7`) via branch `cursor/whitepact-ws2-runtime-authority-f7a9`.

## Current architecture (verified in tree)

| Layer | Module | Role |
|-------|--------|------|
| Hosted MCP dispatch | `mcp/server.py` `_call_tool` | Fail-closed without org + governance; `apply_governance()` when enabled |
| Governance wiring | `mcp/governance_integration.py` | `AuthorityResolver`, `authorize_execution`, `InternalToolExecutor` |
| Kernel | `governance/sovereignty_kernel.py` | Invoked from `AuthorityResolver.resolve()` |
| Upstream proxy | `mcp/upstream_dispatch.py` | `apply_upstream_governance()` |
| Community stdio | `mcp/server.py` `main()` | Ungoverned by design when `mcp_trust_domain=community` |

## WS-2 delivery slices

1. **Enterprise trust domain (started):** `Settings.mcp_trust_domain` — `enterprise` refuses stdio startup; community unchanged.
2. **Adversarial matrix:** extend `tests/test_mcp_governance_dispatch.py` + new `tests/test_mcp_authority_adversarial.py` (forged/expired/replay grants, cross-tenant, resolver failures, direct upstream).
3. **Binding proof:** assert no `dispatch_tool()` on governed paths without `authorize_execution` success (static + integration).
4. **Documentation:** enterprise deployment guide — no claim of stdio protection in enterprise mode.

**Gate M1:** Antigravity independent verification mandatory before BLK-P0-02/P0-03 marked VERIFIED_CLOSED.
