# WHITEPACT — FRESH DATABASE CUSTOMER GOLDEN JOURNEY
## END-TO-END QUALIFICATION OF INDEPENDENTLY ENFORCED CUSTOMER AUTHORITY

- **Author:** Antigravity (Principal Security Architect)
- **Qualification Suite:** `tests/test_customer_root_authority_bootstrap.py`
- **Method:** `TestCustomerRootAuthorityBootstrap::test_end_to_end_customer_authority_bootstrap_journey`
- **Database Engine:** PostgreSQL 16 / SQLite Clean Database
- **Execution Result:** **PASSED (100% Deterministic Reproduction)**

---

## 1. PURPOSE & ARCHITECTURAL INVARIANT

This document proves that an authentic enterprise customer can onboard, establish canonical root authority, grant explicit scoped consent, register an agent, delegate attenuated permissions, execute permitted actions, reject unauthorized actions, and trigger emergency revocation **starting from an empty database without any backdoor, pre-seeded SQL fixture, or administrative shortcut**.

---

## 2. STEP-BY-STEP REPRODUCTION TRACE

### Step 1: Customer Identity Registration & Verification
1. Call `WebIdentityRepository.register("Alice Founder", "founder@enterprise.com", "SecurePass123!@#")`.
   - Generates web user record `usr_...` with `disabled=0` and pending email verification.
2. Call `WebIdentityRepository.verify_email(token)`.
   - Updates `email_verified_at = NOW()`.
   - *Security Invariant:* An unverified email address cannot create workspaces or establish authority.

### Step 2: Enterprise Workspace Creation
1. Call `EnterpriseIAM.create_workspace(actor_user_id=user_id, name="Enterprise Alpha", slug="enterprise-alpha", kind="ORGANIZATION")`.
   - Persists organization record `org_...`.
   - Inserts membership into `web_memberships` with `role="OWNER"`.
2. Generate authenticated browser session:
   - Call `WebIdentityRepository.create_session(user_id, org_id=org_id)`.
   - Sets cookies `wp_session` and `wp_csrf`.
   - Header `X-WP-CSRF` populated.

### Step 3: Server-Enforced Bootstrap Ceremony Initiation
1. HTTP Request:
   ```http
   POST /api/enterprise/organizations/org_3a7b.../authority/bootstrap/initiate
   Cookie: wp_session=...; wp_csrf=...
   X-WP-CSRF: ...
   Content-Type: application/json

   {
     "ttl_seconds": 900
   }
   ```
2. Server Actions:
   - Verifies caller is verified `OWNER` of `org_3a7b...`.
   - Confirms no canonical root or Trust Fabric root currently exists for this tenant.
   - Generates server-minted challenge token (`wp_boot_...`) and cryptographic nonce (`wp_nonce_...`).
   - Inserts record into `trust_fabric_bootstrap_records` with `claimed_by_principal_id = user_id`.
3. Response:
   ```json
   {
     "ceremony_id": "wp_brec_688c227...",
     "organization_id": "org_3a7b...",
     "token": "wp_boot_s6tN4F1h...",
     "nonce": "wp_nonce_3b8a1c...",
     "expires_at": "2026-10-15T12:00:00+00:00",
     "bound_owner_id": "usr_alice..."
   }
   ```

### Step 4: Atomic Ceremony Completion & Consent Recording
1. HTTP Request:
   ```http
   POST /api/enterprise/organizations/org_3a7b.../authority/bootstrap/complete
   Cookie: wp_session=...; wp_csrf=...
   X-WP-CSRF: ...
   Content-Type: application/json

   {
     "token": "wp_boot_s6tN4F1h...",
     "nonce": "wp_nonce_3b8a1c...",
     "root_public_key": "pk_ed25519_customer_root_abc123",
     "scope_description": "Production customer authority boundary for financial research agents",
     "purpose": "Financial Analysis & Data Extraction",
     "allowed_action_types": ["tool:read", "database:query"],
     "allowed_targets": ["finance-db/*", "market-data/v1/*"],
     "key_algorithm": "Ed25519",
     "consent_method": "CRYPTOGRAPHIC_CEREMONY"
   }
   ```
2. Server Atomic Transaction (`lock_epoch`):
   - Acquires exclusive row lock on tenant revocation epoch.
   - Verifies constant-time hash equality of token.
   - Verifies single-use nonce has not been consumed (`consumed_at IS NULL`).
   - Verifies timestamp has not expired (`now < expires_at`).
   - Verifies `claimed_by_principal_id == actor.user_id`.
   - Sets `consumed_at = NOW()`.
   - Inserts canonical record into `governance_root_authority_records`.
   - Inserts canonical record into `governance_consent_proofs`.
   - Bridges to `trust_fabric_trust_roots` and `trust_fabric_principals`.

### Step 5: Verification of "Registration Alone is Not Authority"
1. Register machine agent:
   - Call `CustomerAuthorityService.register_agent(actor, org_id=org_id, name="Analyzer Agent")`.
   - Agent entity `ag_18c4...` created in database.
2. Evaluate Authority on Undelegated Agent:
   - Dispatch `ActionRequest(action_type="database:query", resource="finance-db/accounts")` with `AgentContext(agent_id="ag_18c4...")`.
   - Call `AuthorityResolver.resolve_authority(...)`.
   - **Result: `AuthorityDenied("No active delegation from root to agent")`**.
   - *Proof:* Merely possessing an identity or API key confers zero execution rights.

### Step 6: Attenuated Delegation Issuance
1. Owner issues delegation:
   - Call `CustomerAuthorityService.delegate_to_agent(actor, org_id=org_id, agent_id="ag_18c4...", granted_action_types=["database:query"], allowed_targets=["finance-db/public/*"])`.
   - Persists edge in `governance_delegations` signed by root authority.

### Step 7: Permitted Action Execution
1. Dispatch in-scope request:
   - `ActionRequest(action_type="database:query", resource="finance-db/public/reports")`.
2. Resolution:
   - `AuthorityResolver.resolve_authority(...)` traces delegation back to root.
   - Confirms resource matches delegation target (`finance-db/public/*`) AND root consent (`finance-db/*`).
   - **Result: `AUTHORITY_CONFIRMED (ALLOWED)`**.

### Step 8: Out-of-Scope Action Rejection
1. Dispatch out-of-scope request:
   - `ActionRequest(action_type="database:delete", resource="finance-db/public/reports")`.
2. Resolution:
   - Action type `database:delete` is neither in delegation nor in root consent.
   - **Result: `AuthorityDenied (DENIED - Action outside authorized scope)`**.

### Step 9: Emergency Root Revocation & Zero-Residual Enforcement
1. Trigger emergency kill-switch:
   - Call `CustomerAuthorityService.revoke_root_authority(actor, org_id=org_id, root_id=root_id, reason="Emergency drill")`.
   - Sets `revoked_at = NOW()` on root authority record.
   - Increments tenant revocation epoch (`bump_epoch`).
2. Subsequent in-scope request:
   - Dispatch identical in-scope request from Step 7.
   - `AuthorityResolver.resolve_authority(...)` detects revoked root and incremented epoch.
   - **Result: `AuthorityDenied("Root authority has been revoked")`**.

---

## 3. INDEPENDENT COMMAND-LINE REPRODUCTION

To reproduce this exact golden path from the shell:
```bash
cd /Users/ag/.gemini/antigravity/scratch/whitepact-m12s
uv run pytest tests/test_customer_root_authority_bootstrap.py -k test_end_to_end_customer_authority_bootstrap_journey -o addopts="" -v
```

Execution verified passing with 0 failures and complete audit trail.
