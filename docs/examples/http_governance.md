# HTTP governance examples

These snippets map to real routes in `src/responsibleai/dashboard/app.py`.
Read this entire page before copying any command.

## Important: HTTP is not a self-contained stranger bootstrap today

Governed HTTP tool calls (`POST /api/governance/tools/call`) use the **same**
runtime path as hosted MCP:

1. Authenticate the org-scoped API key (`OrgContext`).
2. Build `GovernanceContext` from the **API key id** as principal (`ctx.key_id`).
3. **`AuthorityResolver`** loads **root authority**, **consent proof**, and **delegation**
   for that principal (purpose-bound, scope-bound).
4. `WhitePactRuntimeGateway` + `authorize_execution` + `InternalToolExecutor`.

There are **no** public HTTP APIs in this repository to create root authority records
or consent proofs. Those are customer/operator provisioning steps (UI, admin tooling,
or migration). **`POST /api/governance/delegations` alone does not make**
**`/api/governance/tools/call` succeed** — consent and root must already exist and
match the tool name, target, and **exact purpose** string.

### Canonical first-success path (verified local)

```bash
pip install -e ".[dashboard]"
python examples/quickstart_stranger_authority.py
```

That script seeds root + consent + delegation the same way the test suite does
(`tests/conftest.py::seed_runtime_authority`), then runs `apply_governance()` for
`rai_health` before and after `revoke_branch()`.

### What is still required for a copy-paste HTTP stranger path

- Operator workflow to mint **root authority** and **consent** for each org principal.
- Delegation (or consent scope) that includes the tool name (e.g. `rai_health`).
- Every governed call must pass the **same purpose** string recorded on consent.
- Org-scoped API key whose `key_id` equals the consent **grantee** / delegation **to_identity_id**.

Until those HTTP provisioning APIs exist, treat the curl blocks below as **isolated
endpoint references**, not one runnable end-to-end story.

---

## Prerequisites (when using HTTP)

- Dashboard: `uvicorn responsibleai.dashboard.app:app --port 8765`
- `RAI_AUTH_ENABLED=true` and an **org-scoped** key
- Principal already has root + consent + active delegation for the tool you call
- Role **ANALYST** or higher for governed tool calls; **ADMIN** for revocation

## Health (no auth)

```bash
curl -fsS http://127.0.0.1:8765/api/health
```

## Governed tool call (requires full authority chain)

Principal identity = API key id. Tool name = action type = target for MCP tools.

```bash
export BASE=http://127.0.0.1:8765
export API_KEY="your-org-scoped-key"
export PURPOSE="same-purpose-as-on-consent-record"

curl -fsS -X POST "$BASE/api/governance/tools/call" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"rai_health\",
    \"arguments\": {},
    \"purpose\": \"$PURPOSE\"
  }"
```

**Success:** JSON with `result` (tool output).  
**Denied:** JSON with `error` of `governance_denied` and `reason_codes` — no execution grant.

## Evidence (read)

```bash
curl -fsS "$BASE/api/governance/evidence?limit=5" \
  -H "Authorization: Bearer $API_KEY"
```

```bash
curl -fsS "$BASE/api/governance/evidence/verify" \
  -H "Authorization: Bearer $API_KEY"
```

## Delegation grant (ADMIN) — not sufficient alone

Grants authority in the delegation graph only after root/consent exist and scopes align.

```bash
curl -fsS -X POST "$BASE/api/governance/delegations" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "to_identity_id": "<api-key-id-not-arbitrary-string>",
    "granted_action_types": ["rai_health"],
    "constraints": {"allowed_targets": ["rai_health"]},
    "purpose": "same-purpose-as-consent",
    "granted_by": "org-admin"
  }'
```

## Revocation (ADMIN)

```bash
curl -fsS -X POST "$BASE/api/governance/delegations/<api-key-id>/revoke" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "offboard agent"}'
```

After revocation, a second `tools/call` with fresh resolution must return
`governance_denied` (same as `tests/test_mcp_governance_dispatch.py`).

## Python (in-process, full enforcement path)

```bash
python examples/quickstart_stranger_authority.py
python examples/08_whitepact_enterprise_scenario.py   # extended narrative
```

## Trust evaluation (orthogonal)

`POST /api/evaluate` scores model dimensions; it does **not** replace root/consent/delegation.
