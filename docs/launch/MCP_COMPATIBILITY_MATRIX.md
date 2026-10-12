# MCP compatibility matrix (hosted server)

Measured against the real hosted application on 2026-10-11 with the pinned SDK. **Protocol conformance is not
directory registration and is not third-party client interoperability**; only what is marked "tested" below was run.
Evidence: `tests/test_mcp_protocol_matrix.py` (23), `tests/test_mcp_http_transport.py`,
`tests/test_mcp_governance_dispatch.py`, `tests/test_mcp_http_credential_negatives.py`,
`tests/test_mcp_oauth_authorization_server.py`, `tests/test_mcp_oauth.py`.

## SDK

`mcp>=1.0.0,<2.0.0` (pyproject). Installed and tested: **mcp 1.29.1**. The `<2.0` pin stays; a move to SDK 2.x is a
separate migration with its own regression run. Do not remove the pin as part of unrelated work.

## Protocol versions

| Version offered by the client | Result (initialize over Streamable HTTP) | Evidence |
| --- | --- | --- |
| 2024-11-05, 2025-03-26, 2025-06-18, 2025-11-25 | Negotiated as offered | tested |
| **2026-07-28** | **Not implemented by the pinned SDK.** The server answers with a version it does speak (never 2026-07-28) | tested (negotiation down) |
| Unknown / malformed version string | Negotiated down to a supported version | tested |

Conformance to the 2026-07-28 specification text is **NOT TESTED** and the pinned SDK cannot provide it.

## Transports

| Transport | Status | Notes |
| --- | --- | --- |
| Streamable HTTP `/mcp` (stateless) | Engineered + tested | Every POST is authenticated on its own; a session id carries no authority (tested). Malformed bodies get 400, oversize 413, never 500 (fixed this pass: the SDK returned 500 for invalid UTF-8) |
| Legacy HTTP+SSE `/sse` + `/messages/` | Present; basic interop tested | The credential matrix of `test_mcp_http_credential_negatives.py` covers `/mcp`, not `/sse` |
| stdio (`whitepact-mcp`) | **Ungoverned by design** | `docs/launch/LOCAL_STDIO_MCP_SCOPE.md`; refused under the enterprise trust domain |

## Behaviour verified

| Area | Result |
| --- | --- |
| Initialize, server info, capabilities | tested (4 versions) |
| `tools/list` | 30 advertised tools; the test-only fixture `test.counter.increment` exists in `TOOL_DEFS` but is **not advertised**. Names unique and match `[A-Za-z0-9_.-]{1,64}`; every `inputSchema` is valid JSON Schema 2020-12 with `type: object` |
| `resources/list` | 20 resources, unique URIs |
| Request validation | Wrong-typed, missing and unexpected arguments are refused before any handler runs (dispatch spy stays un-awaited) |
| Unknown tool / unknown method | Error, no crash |
| Malformed JSON-RPC bodies (not JSON, empty, wrong version, binary) | Never a 5xx |
| Authentication | Required on every request; forged, malformed, expired and revoked keys refused; key revoked mid-session refused on the next call |
| Tenant context | Tenant B using tenant A's session id acts as B or is refused; nothing is written to A |
| OAuth (reviewer login) | RFC 9728 protected-resource metadata, PKCE S256, audience binding, wrong-audience and cross-tenant tokens denied, single-use codes, refresh rotation and replay revocation (existing suite, re-run green) |
| Token passthrough | Not performed: the server validates its own credentials; upstream calls use separately registered upstream credentials (`test_mcp_ws2_upstream_reconciliation.py`); not re-audited here |

## Not tested

Cancellation and mid-request disconnect behaviour; resource indicators beyond the audience checks above; upstream
server tool-description changes after registration beyond the fingerprint-drift test; any third-party client
(Claude Desktop, Cursor, VS Code, ChatGPT apps, etc.); load on the MCP transport; the MCP Registry listing.
