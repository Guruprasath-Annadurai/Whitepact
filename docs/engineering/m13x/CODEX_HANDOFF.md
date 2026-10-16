# WhitePact Operation Atlas — M13-X Codex Review & Integration Handoff

**Issued To:** Codex (Product Integration Owner)  
**Issued By:** Antigravity (Security & Platform Execution Owner)  
**Milestone:** M13-X (Workstream inside M13 — NOT permission to start M14)  
**Release Status:** **GLOBAL PRODUCTION NO-GO**  
**Pull Request:** [#212](https://github.com/Guruprasath-Annadurai/Whitepact/pull/212) (`security/whitepact-m13x-platform`)  
**Base Commit:** `8cb692b97063cf2b63897d8bba07842be4b0d00a`  
**Exact-Head Commit:** `90acd672` (All 14 CI checks 100% green)  

---

## 1. WebAuthn Request-Origin Trust Boundaries

### Problem Solved
In local development, preview channels, and automated integration tests (such as `scripts/engineering/m13i1_customer_journey.py`), servers bind to dynamic, ephemeral loopback ports (e.g. `http://localhost:57277`). The previous implementation statically bound `rp_origin` to `http://localhost`, rejecting registrations and authentications with `WEBAUTHN_CONFIGURED_ORIGIN_DIFFERS_FROM_APPLICATION_ORIGIN`.

### Architecture & Trust Boundary
- **Development & Testing (`app_env != "production"`):**
  - In `src/responsibleai/enterprise/security/router.py:_svc(request)`, the server dynamically resolves loopback origins (`localhost`, `127.0.0.1`, `::1`) from `request.headers.get("origin")` or `str(request.base_url).rstrip("/")`.
  - The Relying Party ID (`rp_id`) defaults to `localhost`.
  - This preserves cryptographically enforced WebAuthn origin matching without requiring manual port reconfiguration.
- **Production (`app_env == "production"`):**
  - Dynamic resolution is strictly disabled.
  - The server strictly enforces the configured `settings.webauthn_origin` with mandatory HTTPS, cross-referencing `allowed_origins` and `web_public_url`.
- **Policy Compliance:**
  - Approved WP-M13-POL-002 Dual-Path WebAuthn requirements (Path A fresh assertion vs. Path B 300s operation-bound authorization) are preserved intact. The 300-second single-use duration is retained as an active founder-policy constant.

---

## 2. Application Disablement & Cascading Authority Revocation

### Problem Solved
Previously, applications were unmodeled and untracked. Disabling or terminating an application in the product layer did not propagate to underlying agent execution authority, risking zombie agent dispatch.

### Architecture & Guarantees
- **Tenant-Scoped Application Model:**
  - Stored in `trust_fabric_principals` with `principal_type="APPLICATION"` and `(id, org_id)` uniqueness.
  - No Alembic migration bump was introduced, preserving the immutable qualification test asserting migration revision 0064 (`test_m13r_migration_roundtrip.py`).
- **Endpoint:** `POST /api/enterprise/organizations/{org_id}/authority/applications/{app_id}/disable`
- **Cascading Revocation Mechanics:**
  1. Sets target application lifecycle state to `DISABLED`.
  2. Identifies all agents in the tenant bound to `application_id == app_id`.
  3. Transitions each associated agent to `PrincipalState.DISABLED`.
  4. Revokes all active delegations (`governance_delegations`) where `agent_id` belongs to the disabled set.
  5. Revokes all active consent proofs (`governance_consent_proofs`) associated with those delegations.
  6. Increments the organization’s revocation epoch where appropriate to invalidate in-flight tokens.
- **Constitutional Invariant:** A disabled application cannot retain any executing or reachable agents.

---

## 3. Tenant-Scoped Executable Capability Contracts

### Problem Solved
Codex’s inventory UI and external agent frameworks previously lacked server-authoritative insight into what actions an agent is actually authorized to execute, forcing frontends to infer capabilities from unvalidated client state.

### Architecture & Guarantees
- **Endpoints:**
  - `GET /api/enterprise/organizations/{org_id}/authority/capabilities`
  - `GET /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/capabilities`
- **Server-Authoritative Reachability:**
  - Synthesizes capabilities directly from live root authority records and explicit active delegations in `AuthorityService.list_capabilities()`.
  - Agents without active delegations receive status `PENDING_DELEGATION` with 0 execution authority.
  - Agents with active delegations receive status `AUTHORIZED` with explicit `action_type` and `allowed_targets` arrays.
- **Constitutional Enforcement Boundary:**
  - Capabilities indicate reachability only.
  - They **never** grant blanket or continuous authority. Consequential execution (e.g. MCP tool execution) strictly requires short-lived, single-use `ExecutionAuthorization` tokens issued by the judgment engine.
- **Client Library:**
  - Codex should consume `@/lib/customerApplicationReader` via `customerApplicationReader(session)`.
  - `customerAuthorityReader.ts` was preserved strictly unchanged to maintain historical test contract parity.

---

## 4. Remaining Real Authenticator & Customer Journey Blockers

### Observed Blocker
In `scripts/engineering/m13i1_customer_journey.py`, Step 3 (WebAuthn Origin Resolution) now succeeds 100%. The journey currently halts at Step 4 with:
```text
REAL_AUTHENTICATOR_CEREMONY_NOT_COMPLETED
```

### Technical Root Cause
- The WhitePact backend enforces genuine FIDO2/WebAuthn cryptographic verification using `webauthn.helpers.verify_authentication_response()`.
- The verification validates:
  1. Authenticator data flags (User Present, User Verified).
  2. Signature counter freshness (anti-replay).
  3. SHA-256 client data hash matching the server-issued challenge.
  4. Cryptographic signature over `auth_data || client_data_hash` using the credential’s stored public key.
- In automated headless script environments (without a physical Touch ID, YubiKey, or Windows Hello device), software scripts cannot forge valid private-key signatures.

### Path to Green Customer Acceptance
1. **Interactive Manual Acceptance:** Execute the journey through an interactive browser session where an operator taps a hardware authenticator.
2. **Headless Virtual Authenticator Driver:** Integrate Chrome DevTools Protocol (CDP) `WebAuthn.enable` with virtual authenticator emulation (available in Playwright/Puppeteer) in the integration test runner to synthesize real FIDO2 assertions without software workarounds or mock bypasses on the backend.
