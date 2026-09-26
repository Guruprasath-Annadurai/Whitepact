# HTTP and Python governance examples

These examples use **real** dashboard routes from `src/responsibleai/dashboard/app.py`.
Replace placeholders with your org-scoped API key and host.

## Prerequisites

- Dashboard running (`uvicorn responsibleai.dashboard.app:app --port 8765`)
- `RAI_AUTH_ENABLED=true` and an org-scoped key in `RAI_API_KEYS` / dashboard UI
- Key role at least **ANALYST** for read/governed tool calls; **ADMIN** for revocation

## Health (no auth)

```bash
curl -fsS http://127.0.0.1:8765/api/health
```

## Governed MCP tool over HTTP

`POST /api/governance/tools/call` runs `apply_governance` then the internal executor.
Callers are **not** authority; the server resolves policy and delegation.

```bash
export BASE=http://127.0.0.1:8765
export API_KEY="your-org-scoped-key"

curl -fsS -X POST "$BASE/api/governance/tools/call" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "rai_health",
    "arguments": {},
    "purpose": "quickstart smoke"
  }'
```

**Failure handling:** non-2xx HTTP, or JSON with `error: governance_blocked` / governance
unknown outcome — treat as **no execution grant**.

## Evidence (read)

```bash
curl -fsS "$BASE/api/governance/evidence?limit=5" \
  -H "Authorization: Bearer $API_KEY"
```

Chain verification:

```bash
curl -fsS "$BASE/api/governance/evidence/verify" \
  -H "Authorization: Bearer $API_KEY"
```

## Delegation grant and revoke

Grant (ADMIN):

```bash
curl -fsS -X POST "$BASE/api/governance/delegations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to_identity_id": "agent-demo",
    "granted_action_types": ["payment.execute"],
    "constraints": {"max_value_usd": 1000},
    "purpose": "demo",
    "granted_by": "admin"
  }'
```

Revoke branch (ADMIN):

```bash
curl -fsS -X POST "$BASE/api/governance/delegations/agent-demo/revoke" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "offboard agent"}'
```

After revocation, governed tool calls for that identity must fail closed when
authority is resolved from storage.

## Python (in-process, no HTTP)

Minimal allow/deny/evidence/revoke without inventing endpoints:

```bash
python examples/quickstart_stranger_authority.py
```

Full pipeline:

```bash
python examples/08_whitepact_enterprise_scenario.py
```

## Trust evaluation (orthogonal to authority graph)

```bash
curl -fsS -X POST "$BASE/api/evaluate" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "demo-model",
    "provider": "local",
    "fairness": 0.8,
    "privacy": 0.8,
    "security": 0.8,
    "robustness": 0.8,
    "compliance": 0.8,
    "authenticity": 0.8
  }'
```

This scores model dimensions; it does **not** replace delegation-based runtime authority.
