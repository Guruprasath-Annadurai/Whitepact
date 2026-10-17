# WhitePact Operation TITAN — Defect Register

**Milestone:** M13  
**Status:** ALL TRACKED DEFECTS RESOLVED  

---

## 1. DEF-TITAN-001: WebAuthn Origin Constructor Accepted Plain HTTP in Production

- **Severity:** P0 / Critical Security
- **Origin:** Codex independent review in PR #211 / `tests/test_m13i2_atlas_origin_configuration.py`
- **Symptom:** When initialized with `app_env="production"` and an explicit `http://` origin (e.g., `http://example.com`), the service accepted the unencrypted origin instead of raising `ConfigurationError` or `ValueError`.
- **Root Cause:** Origin validation only checked URL syntax without enforcing scheme `https` under `app_env == "production"`.
- **Correction:** In `resolve_webauthn_origin_and_rp_id` (`src/responsibleai/enterprise/security/router.py`), enforced that production mode rejects any non-HTTPS origin with `ConfigurationError("Production WebAuthn origin must use https://")` and strictly validates against `settings.webauthn_rp_id`.
- **Verification:** `tests/test_m13i2_atlas_origin_configuration.py::test_production_rejects_explicit_plain_http_origin` PASSED.

---

## 2. DEF-TITAN-002: WebAuthn Allowed Untrusted Forwarded / Hostile Origin Headers

- **Severity:** P0 / High Security
- **Origin:** Security review of dynamic origin binding in ATLAS PR #212
- **Symptom:** `request.headers.get("origin")` was being parsed without validating against allowed loopback hosts, potentially permitting external spoofed host headers to dictate Relying Party parameters.
- **Root Cause:** Dynamic origin binding lacked host-allowlist sanitization and trusted forwarded headers in production.
- **Correction:**
  - Production strictly ignores request headers and relies solely on `settings.webauthn_origin` and `settings.webauthn_rp_id`.
  - Non-production strictly permits only loopback interfaces (`localhost`, `127.0.0.1`, `::1`). External or non-loopback headers are discarded and fall back to safe local bindings.
- **Verification:** `tests/test_m13x_webauthn_origin_binding.py` (4/4 tests PASSED).

---

## 3. DEF-TITAN-003: Disabling Application Leaked Concurrency Race with Agent Registration

- **Severity:** P0 / High Concurrency & Authority
- **Origin:** Architectural review of distributed worker execution
- **Symptom:** If `register_agent` ran concurrently with `disable_application`, an agent could be registered with `lifecycle_state="ACTIVE"` after the parent application was disabled, leaving an orphaned executable agent.
- **Root Cause:** `register_agent` and `disable_application` operated without tenant-level or application-level row locking.
- **Correction:** Implemented connection-level transaction serialization using `lock_epoch(conn, org_id)` and immediate check of parent application state on the same connection. If parent application is not `ACTIVE`, `register_agent` fails closed with `EnterpriseError(code="FORBIDDEN")` / `CONTAINMENT_INVALID_TARGET`.
- **Verification:** `test_postgres_concurrent_register_agent_vs_disable_application_serialization` running 6 concurrent registration workers against `disable_application` on real PostgreSQL proved 0 active agents remain under the disabled application.

---

## 4. DEF-TITAN-004: Application Disablement Did Not Revoke Multi-Hop Delegations or Invalidate In-Flight Permits

- **Severity:** P0 / Critical Authority Invariant
- **Origin:** Threat Model: Cross-worker revocation guarantees
- **Symptom:** Disabling an application updated `trust_fabric_principals` and immediate child delegations, but did not cascade down transitive sub-delegations (e.g. Agent A -> Agent B) or bump the organization's revocation epoch in the same transaction. Pre-issued `ExecutionAuthorization` permits on worker B could execute.
- **Root Cause:** Lack of recursive/branch revocation on a single transactional connection and omission of `bump_epoch_on_connection`.
- **Correction:** Implemented `revoke_branches_on_conn` in `DelegationRepository` to recursively revoke all descendant delegations and consents in a single atomic transaction, paired with `bump_epoch_on_connection`. Worker B rejects pre-issued permits with `StaleRevocationEpochError` during `admit_execution`.
- **Verification:** `test_postgres_disable_application_atomic_cascade_and_cross_worker_grant_invalidation` PASSED on real PostgreSQL.

---

## 5. DEF-TITAN-005: Mid-Transaction Failure Left Inconsistent Application / Agent State

- **Severity:** P0 / Data Integrity
- **Origin:** Transactional safety review
- **Symptom:** If any downstream step in `disable_application` failed (e.g. audit logger error or database partition), earlier mutations (app disablement or partial agent disablement) were not automatically rolled back if executed across separate connections.
- **Root Cause:** Individual repository calls opened separate connection/transaction scopes.
- **Correction:** Refactored `CustomerAuthorityService.disable_application` to execute all operations (`lock_epoch`, app state update, agent state updates, branch delegation revocations, consent revocations, epoch bump, and audit recording) within `async with self._engine.raw.begin() as conn:`.
- **Verification:** `test_postgres_disable_application_transactional_rollback` PASSED on real PostgreSQL with simulated mid-transaction failure, proving 100% rollback across all tables.

---

## 6. DEF-TITAN-006: Capability Projection Inferred Authority Without Validating Expiration & Policy

- **Severity:** P0/P1 / Authority Truthfulness
- **Origin:** Codex integration feedback on capability inventory
- **Symptom:** `list_capabilities` did not reflect root authority expiration, consent proof expiration, or policy denials, returning `AUTHORIZED` even when underlying authority was invalid.
- **Root Cause:** Capability list was queried statically from delegations without reconciling with `governance_root_authority_records`, `governance_consent_proofs`, `org_authority_ceilings`, or `governance_policies`.
- **Correction:** Re-architected `CustomerAuthorityService.list_capabilities` into a server-authoritative engine that validates root temporal bounds, consent validity, parent application state, org ceilings, and policy rules (`REQUIRE_APPROVAL`, `DENY`, `QUARANTINE`).
- **Verification:** `test_capability_projection_evaluates_root_expiry_consent_app_state_and_policies` PASSED.

---

## 7. DEF-TITAN-007: Client Application Reader Coerced Missing / Malformed Data

- **Severity:** P1 / Client Contract Integrity
- **Origin:** Independent TypeScript audit
- **Symptom:** `customerApplicationReader.ts` fell back to default strings or fabricated dummy dates when receiving invalid backend responses.
- **Root Cause:** Permissive TypeScript parsing logic.
- **Correction:** Rewrote `customerApplicationReader.ts` to perform strict schema validation; any missing required field, non-ISO date, or invalid enum value throws `CustomerApplicationReaderError` without coercion.
- **Verification:** `web/src/test/m13x-application-reader.test.ts` (12/12 unit tests PASSED).

---

## 8. DEF-TITAN-008: Organization Rename Allowed Cross-Workspace Session Drift & Lost Updates

- **Severity:** P1 / Concurrency & Workspace Context
- **Origin:** UI multi-tab drift review
- **Symptom:** Renaming an organization via `/api/web/organization` or `/api/web/organizations/{target_id}` updated the database even if the user's active session cookie was switched to a different workspace in another tab, or if another user modified the name concurrently.
- **Root Cause:** Absence of workspace context matching and optimistic concurrency checks.
- **Correction:** Added `expected_organization_id` check against session cookie (raising `409 Conflict` with `code="WORKSPACE_CONTEXT_CONFLICT"`) and `expected_name` optimistic lock (raising `409 Conflict` with `code="ORGANIZATION_STATE_CONFLICT"`).
- **Verification:** `test_organization_rename_workspace_and_concurrency_preconditions` PASSED.
