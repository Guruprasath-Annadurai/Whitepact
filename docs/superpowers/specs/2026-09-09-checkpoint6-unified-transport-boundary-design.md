# Checkpoint 6: unified transport boundary

## Decision

Official production execution adapters remain protocol translators. They may
authenticate and normalize requests, but only the existing canonical governance
services may resolve authority, consent, purpose, policy, approval, execution
authorization, durable admission, and evidence. No new governance engine or
schema is introduced.

The canonical execution halls are:

- `apply_governance` for internal tools reached through hosted MCP;
- `apply_upstream_governance` for tenant-registered upstream MCP tools;
- `resume_approval` for both internal and upstream approved work.

All three issue a request-bound `ExecutionAuthorization`, persist required
evidence before dispatch, and execute through an executor that durably consumes
the authorization nonce. Transport adapters return the canonical result and
preserve `UNKNOWN` reconciliation semantics.

## Inventory and classification

| Path | Entry point | Classification | Security boundary |
|---|---|---|---|
| Hosted MCP, Streamable HTTP | `mcp.server._call_tool` | Guarded official production | Authenticated `OrgContext` enters `apply_governance`; missing governance fails closed. |
| Hosted MCP, HTTP+SSE | `mcp.server._call_tool` | Guarded official production | Same context variables and canonical hall as Streamable HTTP. |
| Dashboard upstream execution | `dashboard.app.upstream_call_tool` | Guarded official production | REST authentication supplies the tenant/principal; request enters `apply_upstream_governance`. |
| Approval execution | `dashboard.app.governance_execute_approval` | Guarded official production | REST adapter supplies only tenant and approval ID; `resume_approval` reloads the persisted request and current security state. |
| Internal executor | `governance.execution.InternalToolExecutor.execute` | Guarded dispatch sink | Validates and durably admits a bound authorization before `dispatch_tool`. |
| Upstream executor | `governance.upstream_executor.UpstreamMCPExecutor.execute` | Guarded dispatch sink | Validates server/tool/arguments/tenant/purpose and durably admits before network dispatch. |
| Community stdio | `mcp.server._run_stdio` | Explicit Community/local | Deliberate operator-owned local mode. It is not selected by request data and is unavailable as hosted failure fallback. |
| MCP initialize/list tools/resources | MCP SDK handlers | Non-consequential | Discovery and static metadata do not call a tool or mutate tenant state. |
| Dashboard administrative APIs | FastAPI mutation routes | Administrative boundary | Tenant/RBAC and existing epoch/version coordination apply; these are not tool execution requests. |
| Webhook delivery and retry | `WebhookManager.fire` / `_retry_worker` | Operational callback transport | It is not an AI/tool authorization path, but tenant ownership must be explicit and retry must use the tenant-owned current configuration. |
| Dashboard WebSocket | `websocket_dashboard` / `ConnectionManager.broadcast` | Operational notification transport | It cannot execute tools, but snapshots and events must remain tenant-scoped. |
| Email/OIDC discovery/provider clients | provider helpers | Non-governance protocol clients | They implement authentication or transactional delivery, not agent/tool execution. |

There is no queue or worker that executes a serialized governance `ALLOW`.
Webhook retry is the only background external-delivery worker; it delivers
already-created operational events and must not become a cross-tenant channel.

## Findings established before implementation

1. `WebhookManager.fire` selects every configuration subscribed to an event,
   regardless of the originating organization. A tenant event can therefore be
   delivered to another tenant's webhook. The origin tenant must be a required
   input and selection must require exact ownership.
2. Dashboard broadcasts omit a channel, causing tenant event data to reach all
   connected WebSockets. WebSocket authentication and snapshots also do not
   normalize database-backed organization keys. Connections and event delivery
   must use authenticated tenant channels; bootstrap/anonymous local behavior
   must not become an implicit hosted tenant.

These are transport isolation fixes, not changes to the Checkpoint 4 authority
model or Checkpoint 5 evidence model.

## Invariants

- Authentication establishes identity and tenant only; it never grants runtime
  authority.
- Tenant, principal, action, tool, arguments, target, purpose, upstream server,
  and approval bindings cannot be replaced after governance.
- Hosted governance initialization failure produces zero dispatches and never
  falls back to Community stdio.
- Pre-execution evidence failure produces zero dispatches.
- Post-dispatch uncertainty remains `UNKNOWN` and requests reconciliation.
- A consumed authorization cannot be replayed within, across, or after transport
  lifetimes.
- Operational WebSocket and webhook messages are delivered only to the
  authenticated event tenant.
- DNS rebinding remains an open P1 release blocker and is not changed here.

## Compatibility

Public REST and MCP request/response shapes remain unchanged. Internal webhook
emission gains an explicit tenant argument. WebSocket clients continue using the
existing endpoint and token query parameter; valid organization keys resolve to
tenant channels. Local unauthenticated mode remains explicit when authentication
is disabled.

## Implementation plan

1. Add failing tests for cross-tenant webhook emission and dashboard notification
   isolation.
2. Require an origin tenant for webhook emission and pass the authenticated or
   persisted tenant at every production call site.
3. Authenticate WebSocket tokens through existing credential verification and
   scope snapshots/events to the resolved tenant channel.
4. Add static and differential tests proving hosted, REST upstream, and approval
   adapters cannot directly dispatch or substitute canonical context.
5. Run Checkpoint 4/5 regressions, MCP/REST/upstream tests, full verification,
   and a separate read-only adversarial review.

## Self-review

The design adds no schema, authorization type, policy engine, retry model, or
network remediation. Webhooks and WebSockets are explicitly separated from tool
execution while still enforcing tenant transport isolation. Community stdio
remains a process-entry boundary rather than an untrusted request option.
