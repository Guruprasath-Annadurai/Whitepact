# WhitePact hosted developer journey

This is the minimum path a new developer can run against a hosted WhitePact
server. It uses the public client in `whitepact.client.WhitePactClient` and
the existing `/api/v1/governance/*` routes. It does not open a community
stdio session and it does not execute tools on the caller side.

The PyPI distribution name remains `rai-governance-platform`. Renaming that
distribution is a separate package lane and is not decided here.

## What is supported

1. Install the distribution that provides the `whitepact` command.
2. Point the client at an explicit `base_url` with an explicit API key.
3. `authenticate()` reads `GET /api/v1/governance/policy`. The organization
   id in that response is the tenant. A caller-supplied organization id is
   rejected when it disagrees, and it is never sent as authority.
4. `protect(tool, arguments, purpose=...)` calls
   `POST /api/v1/governance/tools/call`. The server evaluates the action.
   When the decision is allow, the server executes it through its own
   execution-authorization boundary. The client has no method that runs a
   tool locally and no parameter that accepts a grant.
5. A `REQUIRE_APPROVAL` decision returns `approval_id` and does not execute.
   `resolve_approval()` then `execute_approval()` resume that approval on
   the server.
6. `list_evidence()`, `get_attestation()`, and `inspect_execution_grant()`
   read stored evidence. A missing grant reference stays missing.
7. `query_audit()` reads `GET /api/v1/audit-log` for the authenticated
   tenant only.
8. `revoke_delegation()` and `revoke_passport()` call the hosted revoke
   routes. Those posts are not retried.

`whitepact connect` stores a base URL and a local organization label. It
probes `GET /api/health` without a credential. Success prints
`VERIFIED CONNECTION`. Failure still saves the context and prints
`SAVED UNVERIFIED CONTEXT`. Tokens are not written to the context file.

## What is not claimed

- Community MCP stdio (`whitepact-mcp` with `WHITEPACT_MCP_TRUST_DOMAIN=community`)
  is local and ungoverned. It is not this hosted journey.
- `WHITEPACT_MCP_TRUST_DOMAIN=enterprise` refuses ungoverned stdio. Hosted
  governed MCP is `whitepact-mcp-http` with server-side governance enabled.
- `whitepact replay` and `whitepact prove` operate on an exported evidence
  record, bundle, or capsule that already contains evidence. They validate
  hashes and refuse cross-tenant, tampered, forged, and incomplete input.
  They do not re-execute the original action.
- There is no client-side dry run that returns a spendable grant.

## Sketch

```python
from whitepact.client import WhitePactClient

with WhitePactClient("https://your-whitepact-host", api_key="wp_live_...") as client:
    authority = client.authenticate()
    decision = client.protect(
        "rai_health",
        {},
        purpose="developer-first-success",
        expected_organization_id=authority.organization_id,
    )
    evidence = client.list_evidence()
    if decision.decision == "REQUIRE_APPROVAL" and decision.approval_id:
        client.resolve_approval(decision.approval_id, "APPROVED")
        client.execute_approval(decision.approval_id)
    client.revoke_delegation("agent-id", reason="end of developer session")
```

Set a finite `timeout`. Safe reads may retry `429`, `502`, and `503`.
`protect`, approval resolve, approval execute, and revoke do not retry.
