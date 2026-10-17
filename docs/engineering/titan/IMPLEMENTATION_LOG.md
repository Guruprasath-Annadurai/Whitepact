# WhitePact Operation TITAN — Implementation Log

**Milestone:** M13  
**Owner:** Antigravity / Argon  
**Target:** Enterprise Authority, Security Hardening, and Distributed Invariant Enforcement  

---

## 1. Schema & Database Migrations

### Migration `0065_bootstrap_require_passkey_stepup.py`
- Added `require_passkey_stepup` column (`sa.Integer`, default `0`, non-nullable) to `trust_fabric_bootstrap_records`.
- Backward compatibility: Existing bootstrap records default to `0`. Reversible via standard `downgrade()`.

---

## 2. WebAuthn Origin & RP-ID Binding (`src/responsibleai/enterprise/security/router.py`)

- **Function `resolve_webauthn_origin_and_rp_id(request)`:**
  - Evaluates `app_module.settings.app_env`.
  - In `production`:
    - Strict check: `settings.webauthn_origin` must start with `https://`.
    - Enforces `webauthn_rp_id` matching the origin hostname.
    - Explicitly rejects missing origin or plain `http://` with `ConfigurationError`.
    - Header inspection is discarded to prevent hostile spoofing through untrusted reverse proxies.
  - In `development` / `test`:
    - Safely resolves loopback bindings (`localhost`, `127.0.0.1`, `::1`).
    - Ephemeral test ports (e.g. `http://localhost:54321`) are bound dynamically to the Relying Party origin.
- **Wired into Step-Up Challenges (`src/responsibleai/enterprise/authority/service.py`):**
  - Updated `create_passkey_stepup_challenge` to record resolved origin and RP-ID into `authority_step_up_challenges`.

---

## 3. Transactional Application Disablement & Cascade (`src/responsibleai/enterprise/authority/service.py`)

- **Single-Connection Transactional Execution:**
  - `disable_application` opens `async with self._engine.raw.begin() as conn:`.
  - Step 1: Acquires tenant row lock via `lock_epoch(conn, org_id)`.
  - Step 2: Updates `trust_fabric_principals` record for `application_id` to `lifecycle_state = "DISABLED"`.
  - Step 3: Queries all agent principals associated with the application.
  - Step 4: Updates all associated agents to `lifecycle_state = "DISABLED"`.
  - Step 5: Invokes `self._delegations.revoke_branches_on_conn(conn, org_id, agent_ids, ...)`:
    - Recursively traverses delegation DAG from root agent down to all downstream sub-agents.
    - Sets `revoked_at` and `revoked_by` on all branch delegations.
    - Sets `revoked_at` on all associated `governance_consent_proofs`.
  - Step 6: Advances tenant revocation epoch on `conn` via `bump_epoch_on_connection(conn, org_id)`.
  - Step 7: Emits atomic audit record on `conn`.
- **Atomic Rollback Guarantee:**
  - If any step inside the block raises an exception, PostgreSQL aborts the entire transaction.
  - Proved in `test_postgres_disable_application_transactional_rollback`.

---

## 4. Concurrency Serialization in Agent Registration

- **`CustomerAuthorityService.register_agent`:**
  - When `application_id` is supplied, registration executes inside `async with self._engine.raw.begin() as conn:`.
  - Acquires `lock_epoch(conn, org_id)` before querying the application.
  - Checks `app_rec["lifecycle_state"] == "ACTIVE"`.
  - If the application is disabled (or was disabled while waiting for the lock), registration immediately rejects with `EnterpriseError(code="FORBIDDEN")` / `CONTAINMENT_INVALID_TARGET`.
  - Guaranteed: No active agent can be created under a disabled application.

---

## 5. Server-Authoritative Capability Projection (`src/responsibleai/enterprise/authority/service.py`)

- **`CustomerAuthorityService.list_capabilities`:**
  - Evaluates root temporal validity: `issued_at`, `not_before`, `expires_at`, `revoked_at`.
  - Inspects root owner consent proof (`governance_consent_proofs`) bound to root.
  - Inspects tenant application lifecycle state: if parent application is `DISABLED`, status is `DISABLED`.
  - Validates full authority delegation chain (`_get_authority_chain_on_conn`): root to intermediate to leaf agent.
  - Checks agent-specific consent proof validity. If expired, marks capability `EXPIRED`.
  - Reconciles `org_authority_ceilings`: intersects allowed action types and glob-matched targets; rejects unauthorized actions with `POLICY_DENIED`.
  - Evaluates ordered `governance_policies`:
    - `DENY` or `QUARANTINE` -> marks status `POLICY_DENIED`.
    - `REQUIRE_APPROVAL` -> marks `requires_approval = True`.
  - Injects provenance identifiers (`root_id`, `delegation_id`, `consent_id`) on all generated capability records.

---

## 6. Precondition Enforcement in Workspace & Organization Updates

- **`src/responsibleai/dashboard/app.py`:**
  - `web_update_organization` inspects `expected_organization_id` against the authenticated session cookie `wp_session.org_id`.
  - If they do not match, returns `409 Conflict` with `{"code": "WORKSPACE_CONTEXT_CONFLICT"}`.
  - In `src/responsibleai/db/org_repository.py`: `update_org_name` accepts `expected_name`.
  - Executes conditional update `WHERE id = :org_id AND name = :expected_name`.
  - If rowcount is 0 due to concurrent rename, raises `OrganizationStateConflictError` mapped to `409 Conflict` with `{"code": "ORGANIZATION_STATE_CONFLICT"}`.

---

## 7. Client Reader Hardening (`web/src/lib/customerApplicationReader.ts`)

- Implemented type-safe validator `readCustomerApplication(data: unknown): CustomerApplication`.
- Enforces presence and string validity of `id`, `name`, `environment`, `lifecycle_state`, `created_at`, `agent_count`.
- Rejects unexpected enums, missing attributes, or non-ISO timestamps without fabricating default values.
