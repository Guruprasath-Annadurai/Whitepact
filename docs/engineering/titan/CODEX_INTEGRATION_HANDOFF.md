# WhitePact Operation TITAN — Codex Integration Handoff

**Issued To:** Codex (Product Integration Lead & Independent Qualification)  
**Issued By:** Antigravity / Argon (Platform & Security Engineering)  
**Source Branch:** `antigravity/whitepact-m13-titan`  
**Milestone:** M13  
**Status:** QUALIFIED PLATFORM CHECKPOINT • **GLOBAL PRODUCTION NO-GO**  

---

## 1. Overview for Codex

Codex identified critical discrepancies during review of PR #211 and PR #212, specifically around:
1. WebAuthn origin constructor failing closed on plain HTTP or missing origins in production.
2. Proof of single-transaction atomicity and rollback for `disable_application`.
3. Multi-worker grant invalidation across PostgreSQL instances.
4. Concurrency race conditions between `register_agent` and `disable_application`.
5. Strict capability projection truthfulness reflecting expired roots/consents and active policies.
6. Defensive client validation without coercion.
7. Multi-tab workspace drift and optimistic concurrency preconditions on organization renaming.

All required security and platform contracts are now fully implemented and verified. This checkpoint is ready for clean integration review by Codex.

---

## 2. API & Integration Contracts

### 2.1 WebAuthn Ceremony Configuration
- **Production (`app_env == "production"`):**
  - Requires `settings.webauthn_origin` with `https://`.
  - Requires `settings.webauthn_rp_id` matching origin hostname.
  - Plain `http://` or omitted origins raise `ConfigurationError`.
  - Re-verified via `tests/test_m13i2_atlas_origin_configuration.py` (3/3 passing).

### 2.2 Application Disablement & Cascading Revocation
- **Endpoint:** `POST /api/enterprise/organizations/{org_id}/authority/applications/{app_id}/disable`
- **Guarantees:**
  - Single database transaction on PostgreSQL.
  - Cascades down full delegation tree to all downstream agents.
  - Automatically bumps tenant revocation epoch.
  - In-flight execution permits on other workers fail admission with `StaleRevocationEpochError`.
  - Concurrent `register_agent` calls targeting this application are serialized behind the epoch lock and rejected with `EnterpriseError(code="FORBIDDEN")` / `CONTAINMENT_INVALID_TARGET`.
  - Exactly 0 active agents remain under the disabled application.

### 2.3 Capability Projection
- **Endpoints:**
  - `GET /api/enterprise/organizations/{org_id}/authority/capabilities`
  - `GET /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/capabilities`
- **Output Record Contract:**
  ```json
  {
    "capability_id": "cap_agent_123_read_data",
    "agent_id": "agent_123",
    "organization_id": "org_456",
    "application_id": "app_789",
    "kind": "DELEGATED_ACTION",
    "action_type": "read_data",
    "allowed_targets": ["db:customers"],
    "status": "AUTHORIZED",
    "requires_approval": false,
    "requires_passkey_stepup": false,
    "root_id": "root_abc",
    "delegation_id": "del_def",
    "consent_id": "consent_ghi",
    "constraints": {},
    "authority_enforced": true
  }
  ```
- **Status Enum Values:** `AUTHORIZED`, `POLICY_DENIED`, `EXPIRED`, `REVOKED`, `DISABLED`, `PENDING_DELEGATION`.
- **Invariants:**
  - If parent app is disabled -> `DISABLED`.
  - If root authority or consent proof is expired -> `EXPIRED`.
  - If root authority or delegation is revoked -> `REVOKED`.
  - If denied by org authority ceiling or governance policy -> `POLICY_DENIED`.
  - If requiring human approval -> `requires_approval: true`.

### 2.4 Organization Rename Preconditions
- **Endpoints:**
  - `PATCH /api/web/organization`
  - `PATCH /api/web/organizations/{target_org_id}`
- **Precondition Headers / Body Parameters:**
  - `expected_organization_id`: Must match active session cookie `wp_session.org_id`. Mismatch returns `409 Conflict` with `{"code": "WORKSPACE_CONTEXT_CONFLICT"}`.
  - `expected_name`: Optimistic lock against concurrent rename. Stale name returns `409 Conflict` with `{"code": "ORGANIZATION_STATE_CONFLICT"}`.

### 2.5 TypeScript Client Reader
- Module: `web/src/lib/customerApplicationReader.ts`
- Strict validation without coercion: Throws `CustomerApplicationReaderError` on invalid backend responses.

---

## 3. How Codex Can Review & Replay Proofs

1. Check out branch `antigravity/whitepact-m13-titan`.
2. Run PostgreSQL test suite:
   ```bash
   PYTHONPATH=src pytest tests/test_m13_titan_security_contracts.py -o addopts="" -v
   ```
3. Run WebAuthn and application inventory tests:
   ```bash
   PYTHONPATH=src pytest tests/test_m13i2_atlas_origin_configuration.py tests/test_m13x_webauthn_origin_binding.py tests/test_m13x_application_inventory_contract.py -o addopts="" -v
   ```
4. Run client tests and linter:
   ```bash
   cd web && npm test src/test/m13x-application-reader.test.ts && npm run lint
   ```
5. Verify clean full-source Ruff:
   ```bash
   ruff check src/ tests/ sdk/python/
   ruff format --check src/ tests/ sdk/python/
   ```
