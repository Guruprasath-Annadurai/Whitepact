# WhitePact V1 — MCP Protocol Modernization

Evidence is from the **installed** Python SDK in this environment, not
from documentation alone.

## Installed MCP SDK

Package: `mcp==1.30.0` (`mcp>=1.0.0,<2.0.0` in `pyproject.toml`)

Source of versions: `mcp.types` and `mcp.shared.version`.

## Supported protocol versions

From `mcp.shared.version.SUPPORTED_PROTOCOL_VERSIONS`:

- `2024-11-05` (legacy HTTP+SSE)
- `2025-03-26` (`DEFAULT_NEGOTIATED_VERSION`)
- `2025-06-18`
- `2025-11-25` (`LATEST_PROTOCOL_VERSION`)

Negotiation (SDK `mcp.server.session.ServerSession`): if the client
requests a supported version, the server echoes it; otherwise it
answers with `LATEST_PROTOCOL_VERSION`.

## Current WhitePact hosted protocol profile

Process: `responsibleai-mcp-http` / `whitepact-mcp-http`

Both hosted transports share `_authenticate`, `_call_tool`, plan
gating, and (when enabled) `apply_governance()`. Governance is not
weakened for compatibility.

## Current `/mcp` semantics

- Streamable HTTP (`mcp.server.streamable_http_manager.StreamableHTTPSessionManager`)
- Preferred hosted transport
- `stateless=True`: no session affinity, no event-store resumability
- Bearer auth on every request
- Route: `POST /mcp` (also GET for SSE streams as implemented by the SDK)

## Legacy `/sse` semantics

- HTTP+SSE (`mcp.server.sse.SseServerTransport`)
- Spec `2024-11-05` profile: `/sse` + `/messages/`
- Same auth and governance as `/mcp`
- Kept unmodified for existing clients; no removal date

## stdio semantics

- `responsibleai-mcp` / `whitepact-mcp`
- Local, ungated community trust domain by design
- Not a hosted replica; production hosted preflight does not apply

## Current-protocol support

YES for Streamable HTTP `/mcp` via the installed SDK 1.30.0, including
initialize / tools / structured tool output (`tests/test_mcp_http_transport.py`).

## Legacy support

YES for `/sse` auth and `/health` transport listing. Full SSE
initialize interop remains covered by SDK transport tests plus
WhitePact auth tests.

## Protocol-version negotiation

Delegated to the SDK session. WhitePact does not fork protocol
version tables.

## Session dependency

Hosted `/mcp` is **stateless**. Production must not assume sticky
sessions for Streamable HTTP.

## Governance parity

`/mcp` and `/sse` use the same `_call_tool` path. stdio remains
ungoverned. Hosted production requires `mcp_governance_enabled=true`.

## Tests

- `tests/test_mcp_protocol_modernization.py` (installed SDK versions)
- `tests/test_mcp_http_transport.py` (live `/mcp` initialize + tools)
- `tests/test_mcp_transport_security.py` (auth limiter, DNS rebinding)

## Conformance evidence

See those tests. Compatibility is not claimed from docs alone.

## Remaining blocker

None in the installed SDK for current-protocol hosted `/mcp` with
`stateless=True`. SDK 2.x remains pinned out (`mcp<2.0.0`) because of
the camelCase tool schema break; that is a separate, deliberate bump.
