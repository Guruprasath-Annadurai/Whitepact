# Architecture

## Overview

ResponsibleAI is three Python packages in one repository:

| Package | Role |
|---|---|
| `responsibleai` | Core governance engines + REST API + MCP server |
| `biasbuster` | Bias evaluation CLI and demographic probes |
| `privacylabel` | Federated learning and differential privacy |

All three are installed together from the `rai-governance-platform` PyPI distribution.

---

## Request lifecycle

```
Client Request
      │
      ▼
 FastAPI app (responsibleai.dashboard.app)
      │
      ├─ AuditMiddleware    → writes to audit_log table (every request)
      ├─ SecurityHeaders    → CSP, X-Frame-Options, HSTS
      ├─ RateLimiter        → per-org bucket (SHA-256 of Bearer token)
      │
      ▼
 Auth dependency (get_org_context)
      │  Bearer token → SHA-256 hash → org_api_keys lookup
      │  Returns: OrgContext(org_id, role, key_id)
      │
      ▼
 Route handler
      │
      ├─ TrustScoreEngine.compute()      → deterministic 6-dim score
      ├─ ComplianceEngine.evaluate()     → NIST/EU/ISO scoring
      ├─ GuardrailsEngine.scan()         → regex PII + toxicity
      ├─ HallucinationDetector.analyze() → TF-IDF self-consistency
      ├─ RedTeamSimulator.run_all()      → adversarial payload analysis
      ├─ CostTracker.record()            → token cost persistence
      │
      ├─ DB repositories (async SQLAlchemy)
      │     TrustRepository, CostRepository, AuditRepository, ...
      │
      └─ WebhookManager.fire()           → async delivery + DB retry queue
```

---

## Database layer

```
AsyncEngine (aiosqlite or asyncpg)
      │
      ├─ DatabaseEngine        wraps raw engine, handles init + WAL pragma
      ├─ TrustRepository       CRUD for trust_scores
      ├─ CostRepository        CRUD for token_usage
      ├─ AuditRepository       append-only audit_log
      ├─ OrgRepository         organizations + org_api_keys
      ├─ EvalRepository        eval_runs + eval_baselines
      └─ WebhookDeliveryRepository  delivery log + retry queue
```

Schema is managed by Alembic. `DatabaseEngine.init()` also calls `metadata.create_all()` as a safety net for development.

**Tables (v1.1.0):**

| Table | Purpose |
|---|---|
| `token_usage` | Per-request token costs |
| `trust_scores` | Model trust score history |
| `organizations` | Multi-tenant orgs |
| `org_api_keys` | API keys hashed (SHA-256) per org |
| `audit_log` | Immutable request audit trail |
| `eval_runs` | Comparison/benchmark run results |
| `eval_baselines` | Regression baselines per model/suite |
| `webhook_deliveries` | Delivery log + retry state machine |

---

## MCP server

The MCP server runs as a separate process (`responsibleai-mcp`) communicating over stdio. It instantiates core engines in-process (no network call needed for computation tools). For data-retrieval tools (`rai_cost_estimate` summary), it calls the REST API.

```
Claude Code ──stdio──► responsibleai-mcp
                             │
                   ┌─────────┴──────────┐
                   │  In-process        │   REST call
                   │  TrustScoreEngine  │──►  http://localhost:8765
                   │  GuardrailsEngine  │
                   │  ComplianceEngine  │
                   │  HallucinationDet. │
                   │  RedTeamSimulator  │
                   └────────────────────┘
```

---

## Rate limiting

Slowapi is configured with a custom key function:

```python
def _get_rate_limit_key(request):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        return "key:" + sha256(token)[:24]   # per-org bucket
    return get_remote_address(request)        # fallback to IP
```

This ensures each API key (and therefore each org) gets an independent rate limit bucket. When `RAI_REDIS_URL` is set, counters are stored in Redis and survive restarts.

---

## Webhook delivery

```
fire(event, data)
      │
      ├─ WebhookDeliveryRepository.create()     [status=pending]
      │
      └─ _deliver() — attempt #1
            │  success → record_attempt(success=True)  [status=delivered]
            │  fail    → record_attempt(success=False) [status=retrying, next_retry_at=now+Ns]
            │
            └─ Background retry worker (every 30s)
                  └─ pending_retries() → re-deliver each
                        retry delays: 1s → 5s → 30s → 2min → 10min
                        exhausted    → [status=failed]
```

Delivery log persists across server restarts. Status machine: `pending → retrying → delivered | failed`.

---

## Security model

| Layer | Mechanism |
|---|---|
| Transport | TLS (terminator, e.g., nginx or load balancer) |
| Authentication | SHA-256 hashed Bearer token lookup in `org_api_keys` |
| Authorization | RBAC: OWNER(4) > ADMIN(3) > ANALYST(2) > VIEWER(1) |
| Payload signing | HMAC-SHA256 on webhook deliveries (`X-RAI-Signature-256`) |
| PII | GuardrailsEngine redacts before logging |
| Headers | CSP, X-Frame-Options, X-Content-Type-Options on all responses |
| Rate limiting | Per-org SHA-256 keyed bucket |
| Exceptions | Global handler — no raw tracebacks reach clients |
