# WhitePact Enterprise Phase 4: Enterprise IAM, Privileged Access & Sovereign Recovery
## Architecture & Subsystem Design Specification

**Document:** `docs/superpowers/specs/2026-09-12-enterprise-iam-privileged-administration-design.md`
**Status:** APPROVED FOR IMPLEMENTATION
**Target Branch:** `feature/enterprise-iam-phase4`
**Baseline:** `53704a12269aea6eb467241a016c163d1e13e7df` (Phase-3 Frozen HEAD)

---

### Executive Summary

Phase 3 established the Global Trust Fabric — resolving principal identity, organizational relationships, and authority graphs. Phase 4 establishes the authoritative **Enterprise Privileged Control Plane** governing who may administer that trust infrastructure.

The core architecture centers on the **Privileged Surface Guard** canonical chokepoint (`authorize_privileged_operation`), enforcing:
- Multi-tier privileged risk modeling (`PRIVILEGED_STANDARD`, `PRIVILEGED_HIGH`, `PRIVILEGED_CRITICAL`).
- Dynamic Step-Up reauthentication with strict cryptographic nonces and time bounds.
- Full SCIM 2.0 provisioning with immediate cascading deprovisioning (zero ghost sessions/keys).
- Just-In-Time (JIT) access grants and strict Four-Eyes separation of duties.
- Controlled emergency break-glass sessions with explicit capability scoping and incident bindings.
- Sovereign Customer Root Recovery utilizing customer-held N-of-M cryptographic guardian threshold signatures, barring WhitePact platform operator backdoors.

---

### 1. Architectural Options Evaluated

#### Approach A: Middleware-Only Interceptor
*Concept:* Intercept all FastAPI routes using a single HTTP middleware that checks headers for step-up tokens, JIT headers, and approvals.
- *Pros:* Simple to write; intercepts requests early.
- *Cons:* Fails to protect internal service-to-service calls, background workers, or non-HTTP interfaces. Lacks context on business payloads (e.g. which resource is being mutated). Does not support programmatic authorization checks.
- *Verdict:* REJECTED.

#### Approach B: Ad-Hoc Service Helpers
*Concept:* Each repository or service independently queries an IAM table to verify permissions and step-up status.
- *Pros:* Localized changes.
- *Cons:* High risk of inconsistent enforcement, divergent risk tier classifications, fragmented audit logs, and missed security epoch checks.
- *Verdict:* REJECTED.

#### Approach C: Unified Canonical Guard & Domain Engine (Selected)
*Concept:* Implement a standalone `responsibleai.iam` subsystem centered on `authorize_privileged_operation` with dedicated domain engines:
1. `PrivilegedSurfaceGuard` (`src/responsibleai/iam/guard.py`): The single canonical authorization chokepoint.
2. `StepUpEngine` (`src/responsibleai/iam/step_up.py`): Evaluates OIDC `auth_time`, TOTP/MFA proofs, action-bound nonces.
3. `ScimService` (`src/responsibleai/iam/scim.py`): RFC 7643/7644 implementation triggering instant session/credential invalidation.
4. `SessionCredentialService` (`src/responsibleai/iam/session.py`, `src/responsibleai/iam/api_key.py`): Real-time session revocation and API key lineage tracking.
5. `JitFourEyesEngine` (`src/responsibleai/iam/jit.py`, `src/responsibleai/iam/four_eyes.py`): Time-bounded dynamic escalation and strict dual-custody enforcement.
6. `BreakGlassEngine` (`src/responsibleai/iam/break_glass.py`): Emergency scoped delegation bound to active incident tickets.
7. `SovereignRecoveryEngine` (`src/responsibleai/iam/recovery.py`, `src/responsibleai/iam/transfer.py`): Customer-controlled N-of-M guardian threshold ceremony.
8. `PrivilegedAttributionEngine` (`src/responsibleai/iam/attribution.py`): Immutable audit logging linked to the Checkpoint-5 evidence chain.
- *Verdict:* SELECTED. Provides airtight, testable, portable, and tamper-resistant security enforcement.

---

### 2. Subsystem Details & Data Contracts

#### A. Data Models & Database Migration (`0044_enterprise_iam_privileged_admin.py`)
- Linear migration stacking directly on `0043_global_trust_fabric`.
- Tables created:
  - `iam_step_up_nonces`: Single-use, action-bound cryptographic nonces.
  - `iam_sessions`: Interactive and bearer sessions with revocation epochs, status, and principal bindings.
  - `iam_api_key_lineage`: Detailed lineage, fingerprints, rotation chain, and scopes.
  - `iam_scim_users`: Provisioned user mappings, external IDs, active statuses.
  - `iam_scim_groups`: Group definitions and multi-tenant membership bindings.
  - `iam_jit_grants`: Time-bounded temporary role and capability elevations.
  - `iam_four_eyes_requests`: Dual-custody requests, approval signatures, and execution statuses.
  - `iam_break_glass_sessions`: Incident-bound emergency capability authorizations.
  - `iam_recovery_policies`: N-of-M guardian public keys and threshold definitions.
  - `iam_recovery_challenges`: Challenge nonces, guardian partial signatures, and root replacement records.
  - `iam_privileged_audit_log`: Tamper-evident hash-chained privileged execution records.

#### B. Canonical Authorization Chokepoint
Signature:
```python
async def authorize_privileged_operation(
    *,
    db: DatabaseEngine,
    caller_principal_id: str,
    org_id: str,
    action: PrivilegedAction,
    target_resource_id: str | None = None,
    step_up_proof: StepUpProof | None = None,
    four_eyes_approval_id: str | None = None,
    jit_grant_id: str | None = None,
    break_glass_session_id: str | None = None,
    action_context: dict[str, Any] | None = None,
) -> PrivilegedAuthorizationResult
```

Execution steps:
1. **Tenant & Principal Verification:** Validate `caller_principal_id` belongs to `org_id` and is in `ACTIVE` lifecycle state. Cross-tenant callers immediately trigger `CrossTenantAccessError`.
2. **Platform Backdoor Check:** Disallow WhitePact platform operator identities from acting as customer root or bypassing customer tenant policies.
3. **Risk Tier Determination:** Map `action` to `PRIVILEGED_STANDARD`, `PRIVILEGED_HIGH`, or `PRIVILEGED_CRITICAL`.
4. **Base Role & JIT Evaluation:** Check if caller holds the base role (e.g. `ADMIN`, `OWNER`) or holds an active, unexpired JIT grant for this specific action.
5. **Step-Up Verification:** If risk is `HIGH` or `CRITICAL`, evaluate `step_up_proof`. Require fresh proof (≤15 min for HIGH, ≤5 min for CRITICAL) and verify action-bound nonce single-use consumption.
6. **Four-Eyes Verification:** If risk is `CRITICAL` or action requires dual custody, verify approved `four_eyes_approval_id`. Assert `approver_principal_id != requester_principal_id` and assert approver has independent credentials.
7. **Break-Glass Override Evaluation:** If `break_glass_session_id` is supplied, verify session is `ACTIVE`, not expired, capability matches requested action, and incident binding is valid.
8. **Epoch Invalidation Check:** Ensure session or credential was issued after the tenant's current revocation epoch.
9. **Tamper-Evident Audit Logging:** Hash all decision parameters and write atomically to `iam_privileged_audit_log`.

---

### 3. Sovereign Root Recovery Design
- Root authority is held solely by customer keys.
- Recovery policy establishes $M$ registered guardian public keys (Ed25519) and a threshold $N$ ($1 < N \le M$).
- Recovery workflow:
  1. Initiate recovery: Generates a cryptographically random challenge bound to `org_id` and new proposed root public key.
  2. Guardian signatures: $N$ distinct guardians sign `SHA256(challenge_id || org_id || new_root_key || timestamp)`.
  3. Finalize recovery: Once $N$ valid signatures are verified, atomically:
     - Update `trust_fabric_trust_roots` with the new root public key and principal.
     - Revoke old root credentials and all active sessions for the previous root principal.
     - Advance tenant revocation epoch by +1.
     - Record immutable recovery event in audit log.
- **Zero Operator Backdoor:** No WhitePact master key can sign or bypass the guardian threshold.

---

### 4. Quality, Performance & Verification Strategy
- **Unit & Component Tests:** TDD for each subsystem covering all positive and negative security invariants.
- **Adversarial Red-Team Suite:** 50 targeted attack vectors covering spoofing, replay, race conditions, Cyrillic homoglyphs, privilege escalation, cross-tenant leaks, and revoked credential reuse.
- **Real PostgreSQL 17 Verification:** Verify migration `0044` up/down/re-up on live Postgres, test concurrent JIT/Four-Eyes requests under concurrency.
- **Zero Regression:** Ensure all 3,133 existing tests continue to pass.
