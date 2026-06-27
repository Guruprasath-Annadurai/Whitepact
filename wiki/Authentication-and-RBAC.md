# Authentication and RBAC

## Overview

ResponsibleAI uses Bearer token authentication with role-based access control. Tokens are stored hashed (SHA-256) in the database — the plaintext is never stored.

---

## Enabling auth

```bash
# Auth is ON by default — set at least one key
RAI_API_KEYS=key1,key2,key3 uvicorn responsibleai.dashboard.app:app --port 8765

# Disable auth (development only)
RAI_AUTH_ENABLED=false uvicorn ...
```

When `RAI_AUTH_ENABLED=true` and no keys are configured, every request returns `403`.

---

## Making authenticated requests

```bash
curl -H "Authorization: Bearer your-key-here" \
     http://localhost:8765/api/metrics
```

```python
import httpx

async with httpx.AsyncClient() as client:
    resp = await client.get(
        "http://localhost:8765/api/metrics",
        headers={"Authorization": "Bearer your-key-here"},
    )
```

---

## RBAC roles

| Role | Level | Capabilities |
|---|---|---|
| OWNER | 4 | All operations including org management and key revocation |
| ADMIN | 3 | All operations except org deletion |
| ANALYST | 2 | Read/write evaluations, costs, scans |
| VIEWER | 1 | Read-only access to scores, drift, compliance |

Routes declare their minimum required role:

```python
@app.get("/api/metrics")
async def metrics(_auth: OrgContext = Depends(require_role(Role.ANALYST))):
    ...
```

---

## Organisation management

### Create an org

```bash
curl -X POST http://localhost:8765/api/orgs \
  -H "Authorization: Bearer owner-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "slug": "acme", "monthly_budget_usd": 5000}'
```

### Create an API key for the org

```bash
curl -X POST http://localhost:8765/api/orgs/{org_id}/keys \
  -H "Authorization: Bearer owner-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "prod-service-key", "role": "ANALYST"}'
```

Response includes the plaintext key **once** — store it securely. It cannot be retrieved again.

### Revoke a key

```bash
curl -X DELETE http://localhost:8765/api/orgs/{org_id}/keys/{key_id} \
  -H "Authorization: Bearer owner-key"
```

---

## API key security properties

- Stored as SHA-256 hash — database breach does not expose plaintext keys
- Rate limited independently — each key has its own bucket (no shared IP pool)
- Revocable without rotating other keys
- `last_used_at` tracked on every authenticated request

---

## OIDC / SSO (optional)

For enterprise OIDC integration (Okta, Azure AD, Auth0), the `AsyncJWKSClient` validates JWTs via JWKS endpoint:

```bash
# Set OIDC provider
RAI_OIDC_ISSUER=https://your-company.okta.com
RAI_OIDC_JWKS_URI=https://your-company.okta.com/oauth2/v1/keys
RAI_OIDC_AUDIENCE=https://responsibleai.your-company.com

uvicorn responsibleai.dashboard.app:app --port 8765
```

Claims mapping: `sub` → user ID, `org_id` / `tenant_id` → org, `roles` / `groups` → RBAC role.

---

## Rate limiting

Default: `100 requests / minute` per API key.

```bash
# Override global default
RAI_RATE_LIMIT_DEFAULT=200/minute uvicorn ...

# Use Redis for distributed rate limiting (multi-instance deployments)
RAI_REDIS_URL=redis://redis-host:6379/0 uvicorn ...
```

When Redis is not configured, limits are tracked in-memory and reset on restart.
