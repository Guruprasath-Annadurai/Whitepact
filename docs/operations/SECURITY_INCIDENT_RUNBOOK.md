# Security Incident Runbook

## Triggers

- Suspected API key or signing key leak
- Cross-tenant access report
- Evidence tampering
- Revocation bypass
- Unauthorized consequential MCP execution

## Immediate steps

1. **Contain:** rotate compromised secrets; invalidate sessions; bump revocation epochs where applicable.
2. **Preserve:** export audit logs, deployment SHA, config version (no secrets in ticket).
3. **Scope:** identify tenants and time window.
4. **Recover:** redeploy known-good digest after keys rotated.

## Key rotation

Document which key class failed (JWT, field encryption, webhook HMAC, upstream tokens). Field encryption rotation may require re-encryption plan — treat as SEV0.

## Communication

Technical summary only; no secret values in chat or tickets.
