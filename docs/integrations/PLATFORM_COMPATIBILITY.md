# WhitePact Enterprise Provider Compatibility

This matrix describes the `1.2.4rc1` source candidate. It deliberately
separates repository verification from provider-account verification.

Last reviewed: 2026-08-27

## Release-candidate MCP contract

| Capability | Candidate behavior |
|---|---|
| Primary endpoint | HTTPS `POST /mcp`, stateless Streamable HTTP |
| Legacy endpoint | `/sse` plus `/messages/` |
| Authentication | OAuth/OIDC bearer tokens with exact audience, issuer, expiry, subject, scope, and tenant validation; static tenant API keys remain supported for clients that supply a bearer token directly |
| OAuth discovery | RFC 9728 protected-resource metadata and OAuth authorization-server discovery validation |
| Tenant isolation | Unknown/missing tenants fail closed; authority repositories scope reads and revocations by tenant |
| Tools | 30 tools with JSON Schema inputs, object output schemas, structured content, and explicit MCP annotations |
| Resources | 10 resources under both `whitepact://` and legacy `rai://` URI schemes |
| Governance | Heart root, consent, intent, purpose binding, live authority passport, policy, approval, evidence, and reauthorization gates |
| Operations | `/live`, `/ready`, `/health`, migration gate, Redis-backed distributed authentication throttling |

## Status definitions

- **REPOSITORY_VERIFIED**: protocol behavior is covered by automated local tests.
- **CONFIG_READY**: repository behavior and provider configuration are ready, but the candidate has not been exercised with a real provider account.
- **BRIDGE_VERIFIED**: a repository-tested client bridge exists for a provider surface that does not yet support native remote MCP.
- **EXTERNAL_GATE**: completion requires credentials, provider approval, deployed infrastructure, or another action outside this repository.

## Provider matrix

| Provider | Native surface | Candidate status | Authentication path | Remaining external gate |
|---|---|---|---|---|
| OpenAI | Responses/Plugins remote MCP | CONFIG_READY | OAuth 2.1 discovery, PKCE-capable authorization server, exact resource audience and `mcp:tools` scope | Deploy candidate; register/approve OAuth client or client metadata; run submission compatibility test |
| Anthropic Claude | Messages API and Managed Agents MCP connectors | CONFIG_READY | Pre-obtained OAuth bearer token or Claude vault `mcp_oauth` credential | Run candidate through Claude connector with a real vault/account |
| Microsoft | Copilot Studio custom MCP server | CONFIG_READY | OAuth 2.0 or API-key bearer; register Copilot callback URL in the external IdP | Tenant admin registration and Copilot Studio validation |
| xAI | Responses API Remote MCP Tool | CONFIG_READY | `authorization` bearer token; OAuth access tokens work when obtained out of band | Run candidate with xAI credentials and an enterprise tenant token |
| AWS | Bedrock AgentCore Gateway MCP target | CONFIG_READY | OAuth authorization code/client credentials/token exchange or API-key bearer | Provision Gateway/Identity resources and synchronize the target |
| Mistral | Studio Connectors | CONFIG_READY | OAuth2 client credentials or static Authorization header | Run the Connectors Debugger and register the candidate connector |
| Google Gemini Antigravity | Remote Streamable HTTP MCP | CONFIG_READY | Custom Authorization header | Run the preview agent with a candidate tenant credential |
| Gemini 3 Interactions model path | No native remote MCP at review date | BRIDGE_VERIFIED | Host application opens authenticated MCP session; `GeminiMCPBridge` exposes schemas and routes calls | Keep bridge until Google marks native remote MCP supported for this model path |

## Provider-specific constraints

### OpenAI

Use the exact public MCP URL as both `server_url` and token audience. Production
must expose `/.well-known/oauth-protected-resource`, validate the authorization
server metadata, advertise S256 PKCE, and issue tokens containing `sub`, tenant,
audience, expiry, and `mcp:tools`. WhitePact is a resource server; the external
identity provider owns authorization, token issuance, client registration, and
user consent.

Official reference: <https://developers.openai.com/api/docs/guides/tools-connectors-mcp>

### Claude

Use the public HTTPS `/mcp` URL. Claude currently supports tool calls over
Streamable HTTP and SSE. Restrict the enabled tools explicitly and keep its
default per-tool approval policy for production onboarding.

Official reference: <https://platform.claude.com/docs/en/agents-and-tools/mcp-connector>

### Microsoft

Copilot Studio accepts API-key or OAuth 2.0 authentication. For OAuth, add the
callback URL Copilot Studio provides to the identity-provider client. Do not
reuse a dashboard client ID as the MCP resource audience.

Official reference: <https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-create-new-server>

### xAI

Configure a Remote MCP Tool with `server_url`, `server_label`, an allowlist, and
the tenant access token in `authorization`. xAI does not currently support the
OpenAI Responses `require_approval` field, so application/Heart approval remains
the enforcement layer.

Official reference: <https://docs.x.ai/developers/tools/remote-mcp>

### AWS

Use a Streamable HTTP target. AgentCore supports OAuth, API keys, and several
OAuth grant patterns; DYNAMIC listing avoids control-plane discovery that would
otherwise require a machine-to-machine token. WhitePact's stateless transport is
compatible with AgentCore's recommended mode.

Official references:
<https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-target-MCPservers.html>
and
<https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp-protocol-contract.html>

### Mistral

Register the public `/mcp` URL, authenticate with OAuth2 client credentials or
an Authorization header, and run the Connector Debugger before publishing.
Connectors remain a public-preview provider feature, so repeat validation for
each enterprise candidate.

Official reference: <https://docs.mistral.ai/studio/connectors/debugger>

### Gemini

Antigravity supports remote Streamable HTTP MCP. The Gemini 3 Interactions
documentation still lists remote MCP as unavailable, so applications using that
model path should use `responsibleai.integrations.GeminiMCPBridge`. The bridge
does not acquire or store credentials and cannot bypass WhitePact governance.

Official references:
<https://ai.google.dev/gemini-api/docs/antigravity-agent> and
<https://ai.google.dev/gemini-api/docs/interactions-overview>

## Required live test for every provider

1. Obtain a tenant-scoped token for the exact MCP resource and scope.
2. Confirm unauthenticated discovery returns `401` plus resource metadata.
3. Initialize the provider against `/mcp` and list all expected tools.
4. Confirm annotations and input/output schemas are accepted.
5. Call `rai_health`, then a governed `rai_scan` with a fully enrolled Heart principal.
6. Confirm a wrong audience, wrong scope, unknown tenant, revoked consent, and cross-tenant identifier are rejected.
7. Record provider, client/API version, timestamp, tenant, result, and evidence artifact. Never mark a provider VERIFIED based only on repository tests.
