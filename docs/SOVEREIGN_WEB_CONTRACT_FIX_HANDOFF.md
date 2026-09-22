# SOVEREIGN_WEB_CONTRACT_FIX_HANDOFF

## Branch and SHA

- **Fix branch:** `cursor/whitepact-sovereign-v1-web-contract-fix`
- **Base (Sovereign Core):** `32ff559bea1476d1257a73fa8d9955f6c2724e64`
- **Integrate:** latest commit on the fix branch after push (see `git rev-parse HEAD` on branch)

## Contract

- **Path:** `contracts/sovereign-v1-web.json`
- **Root cause:** File was never published on Sovereign Core `32ff559` (referenced by tests/docs only).
- **Semantics:** Documents internal `/api/sovereign/*` plus browser-safe `/api/web/sovereign/*` mirrors for AVAILABLE/EXPERIMENTAL features.
- **Tenancy:** Browser requests use `WebTenantBody` (no `organization_id`); tenant is derived from `wp_session`.

## Browser-safe routes (`/api/web/sovereign`)

| Surface | Method | Path |
|--------|--------|------|
| Status | GET | `/api/web/sovereign/status` |
| Capabilities | GET | `/api/web/sovereign/capabilities` |
| X-Ray | POST | `/api/web/sovereign/xray` |
| Explain | POST | `/api/web/sovereign/explain` |
| Trace | POST | `/api/web/sovereign/trace` |
| Authority effective | POST | `/api/web/sovereign/authority/effective` |
| Authority compare | POST | `/api/web/sovereign/authority/compare` |
| Authority drift | POST | `/api/web/sovereign/authority/drift` |
| Blast radius | POST | `/api/web/sovereign/simulate/blast-radius` |
| Mission simulation | POST | `/api/web/sovereign/simulate/mission` |
| Shadow | POST | `/api/web/sovereign/shadow` |
| Policy lint/validate | POST | `/api/web/sovereign/policy/lint` |
| Policy test | POST | `/api/web/sovereign/policy/test` |
| Policy diff | POST | `/api/web/sovereign/policy/diff` |
| Policy simulate | POST | `/api/web/sovereign/policy/simulate` |
| Gauntlet | POST | `/api/web/sovereign/gauntlet` |
| Flight recorder | POST | `/api/web/sovereign/flight-recorder` |
| Time machine | POST | `/api/web/sovereign/time-machine` |
| Evidence correlation | POST | `/api/web/sovereign/evidence/correlate` |
| Capsule create | POST | `/api/web/sovereign/capsules` |
| Capsule validate | POST | `/api/web/sovereign/capsules/validate` |
| Capsule reproduce | POST | `/api/web/sovereign/capsules/reproduce` |
| Authority BOM (EXPERIMENTAL) | POST | `/api/web/sovereign/authority-bom` |

**Not exposed to browser:** raw `/api/sovereign/*` (service-to-service / SDK only).

## Auth and tenant derivation

- **Mechanism:** `wp_session` cookie → `WebIdentityRepository.get_principal` → `require_web_csrf` (`X-WP-CSRF` + `wp_csrf` cookie).
- **Implementation:** `src/responsibleai/sovereign/web_auth.py`, bound via `bind_web_identity_repository` in dashboard startup.
- **Tenant:** `principal.org_id` only; `organization_id` in JSON body/query/headers → HTTP 400.
- **Cross-tenant:** `SovereignTenantIsolationError` → HTTP 404 (no existence leak).
- **Unauthenticated:** HTTP 401; CSRF failure: HTTP 403; no org membership: HTTP 409.

## Codex / `SovereignApi.ts` updates

- Point browser client calls at `/api/web/sovereign/*` (not `/api/sovereign/*`).
- Remove `organization_id` from browser request bodies; rely on session org.
- Send `X-WP-CSRF` on all POSTs; include cookies.
- Keep capability negotiation on GET `/api/web/sovereign/capabilities`.
- Preserve UNKNOWN/MISSING/UNAVAILABLE/EXPERIMENTAL and gauntlet status enums from contract `$defs`.

## Tests (fix branch)

- `tests/sovereign/` — 86 passed (includes contract, web auth, tenant isolation, zero-effect, gauntlet).
- Alembic single head: `0061`.

## Known limitations

- Authority **expected** remains manifest/CLI-side; no separate HTTP surface on Core.
- Policy **validate** is an alias of **lint** (same route).
- Browser GET status/capabilities remain unauthenticated mirrors of Core negotiation.
