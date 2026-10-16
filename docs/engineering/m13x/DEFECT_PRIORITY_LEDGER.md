# WhitePact Operation Atlas — M13-X Defect Priority Ledger

**Milestone:** M13-X  
**Classification Standard:** S0 (Release-Blocking Security), S1 (Architecture / Contract Gaps), S2 (Database Integrity), S3 (Tool & MCP Execution), S4 (Isolation & Egress), S5 (Customer Journey / Acceptance), S6 (Compliance & Supply Chain).

---

## 1. Defect Index & Resolution Status

### DEF-M13X-001: WebAuthn Origin Mismatch During Dynamic Port Binding
- **Severity:** S0 / S5 (Blocker)
- **Status:** **RESOLVED**
- **Affected Subsystem:** `src/responsibleai/enterprise/security/router.py`, `src/responsibleai/dashboard/config.py`
- **Symptom:** In `scripts/engineering/m13i1_customer_journey.py`, the ephemeral test server binds to random loopback ports (e.g. `http://localhost:57277`), while `Settings.webauthn_origin` defaulted statically to `http://localhost`. Step 3 failed with `WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN`.
- **Root Cause:** Origin validation did not inspect request headers or base URLs in development/test mode, requiring exact static string match against `settings.webauthn_origin`.
- **Fix:** In `_svc(request: Request | None = None)`, if `app_env != "production"`, dynamically resolve loopback origins (`localhost`, `127.0.0.1`, `[::1]`) from `request.headers.get("origin")` or `str(request.base_url).rstrip("/")`. In production, strictly enforce HTTPS and the explicitly configured origin.
- **Verification:** `tests/test_m13x_webauthn_origin_binding.py` passes 2/2; re-running `m13i1_customer_journey.py` confirms `server_expected_origin == application_origin` passes.

---

### DEF-M13X-002: Missing Tenant-Scoped Application Inventory & Model
- **Severity:** S1 (Architecture Contract Gap)
- **Status:** **RESOLVED**
- **Affected Subsystem:** `src/responsibleai/enterprise/authority/service.py`, `src/responsibleai/enterprise/authority/router.py`, `src/responsibleai/trust_fabric/enums.py`
- **Symptom:** Codex frontend and enterprise customer onboarding require an application inventory model grouping agents and tracking ownership, lifecycle, and environment. The backend previously lacked an application entity, storing only agents and tenants.
- **Root Cause:** Application model had not been implemented on the platform.
- **Fix:** Added `PrincipalType.APPLICATION` to `trust_fabric_enums.py`. Utilized existing `trust_fabric_principals` table (preventing migration version bump that would break migration 0064 roundtrip test). Implemented `register_application`, `list_applications`, `get_application`, and `disable_application` (with cascading agent disablement and delegation revocation). Bound `register_agent` with optional `application_id`.
- **Verification:** `tests/test_m13x_application_inventory_contract.py` passes 3/3; tenant boundary isolation, cascading revocation, and agent associations verified.

---

### DEF-M13X-003: Unwired Executable Capability Synthesis
- **Severity:** S1 (Architecture Contract Gap)
- **Status:** **RESOLVED**
- **Affected Subsystem:** `src/responsibleai/enterprise/authority/service.py`, `src/responsibleai/enterprise/authority/router.py`
- **Symptom:** Codex dashboard and external agent frameworks could not query server-authoritative capabilities for registered agents. Frontend had to infer or guess capability status, violating Constitutional Principle.
- **Root Cause:** No route or service method existed to compute server-authoritative executable capability reachability.
- **Fix:** Added `list_capabilities(actor, org_id, agent_id=None)` in `AuthorityService`. Computes active capability reachability directly from root authority and explicit active delegations. Enforces invariant: Capabilities indicate reachability only; action execution strictly requires short-lived `ExecutionAuthorization`.
- **Verification:** `tests/test_m13x_application_inventory_contract.py` test 3 passes 100%.

---

### DEF-M13X-004: Frontend Authority Reader Exact Keys Breakage
- **Severity:** S1 / Regression
- **Status:** **RESOLVED**
- **Affected Subsystem:** `web/src/lib/customerAuthorityReader.ts`, `web/src/lib/customerApplicationReader.ts`
- **Symptom:** Adding `applications()` and `capabilities()` directly to `customerAuthorityReader` broke `web/src/test/m12c-authority-reader.test.ts` line 15 (`expect(Object.keys(reader)).toEqual(["status", "agents"])`).
- **Root Cause:** Strict contract assertion in historical M12 qualification suite expecting exactly two methods on `customerAuthorityReader`.
- **Fix:** Reverted `customerAuthorityReader.ts` to exact original interface (`{ status, agents }`). Created separate `customerApplicationReader.ts` and `m13x-application-reader.test.ts`.
- **Verification:** `web/` vitest suite passes 30/30 test files (275/275 tests).

---

### DEF-M13X-005: Software-Only Customer Journey Authenticator Barrier
- **Severity:** S5 (Acceptance Blocker / Expected Boundary)
- **Status:** **DOCUMENTED & PRESERVED**
- **Affected Subsystem:** `scripts/engineering/m13i1_customer_journey.py`
- **Symptom:** Step 4 of customer journey requires a hardware/browser WebAuthn ceremony with cryptographic signature verification (`verify_authentication_response`). Without a physical FIDO2 authenticator or virtual authenticator extension in headless CI/CD, the customer journey halts at `REAL_AUTHENTICATOR_CEREMONY_NOT_COMPLETED`.
- **Resolution:** Retained fail-closed security boundary. The backend correctly verifies assertions. Full end-to-end verification requires either an interactive browser session with a WebAuthn authenticator or a dedicated virtual software authenticator driver in the integration runner.

---

### DEF-M13X-006: Historical Commit DCO Sign-off Absence (PR #208)
- **Severity:** S6 (Compliance / Governance)
- **Status:** **DOCUMENTED / BLOCKED ON OWNER DISPOSITION**
- **Affected Subsystem:** Git history on `security/whitepact-m13s4-security` (commit `39619c4b`)
- **Symptom:** Commit `39619c4b` lacks a `Signed-off-by` trailer.
- **Resolution:** Prompt mandates: "Never rewrite history", "Never forge contributor attestations". Antigravity cannot amend published PR #208 history. Documented for repository administrator disposition. All M13-X Antigravity commits include verified `-s` sign-off.
