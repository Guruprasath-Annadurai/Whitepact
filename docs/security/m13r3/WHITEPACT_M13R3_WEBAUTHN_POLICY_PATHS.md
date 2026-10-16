# WHITEPACT M13-R3 WEBAUTHN POLICY PATHS (WP-M13-POL-002)

**Milestone:** M13-R3  
**Policy Identifier:** WP-M13-POL-002  
**Subject:** Dual-Path High-Assurance WebAuthn Authorization Architecture  
**Status:** FULLY IMPLEMENTED & PROVEN

---

## 1. Constitutional Requirements

WP-M13-POL-002 mandates that all high-risk, privileged mutations (specifically `EMERGENCY_CONTAINMENT`) must be authorized via one of two—and only two—mutually exclusive, cryptographically defensible paths:

- **Path A:** Direct, fresh, server-verified WebAuthn assertion bound to the exact tenant, user, action, and operation parameters.
- **Path B:** Pre-verified, single-use, short-lived (300-second maximum) authorization ticket minted from a genuine, verified WebAuthn ceremony.

Any generic MFA flag, client-supplied bypass, bearer API-key override, or unverified step-up is strictly forbidden and rejected at the server boundary.

---

## 2. Path A Specification: Fresh Server-Verified Assertion

1. **Challenge Issuance:** Caller requests a challenge via `create_authority_stepup_challenge` specifying `org_id`, `action`, and `operation_digest`.
2. **Client Signing:** Authenticator signs the challenge together with client data and authenticator data.
3. **Atomic Verification & Execution:** Caller submits `webauthn_assertion` directly to `execute_emergency_containment`.
   - The challenge is verified against the database and atomically consumed in the same database transaction.
   - Signature, counter progression (or verified passkey cryptographic proof), user presence (UP), and user verification (UV) are checked.
   - The operation executes with zero residual validity.

---

## 3. Path B Specification: Pre-Verified Single-Use Authorization Ticket

Path B accommodates decoupled workflows (such as asynchronous dispatch or coordinated supervisor containment) where the interactive passkey ceremony occurs moments prior to execution:

1. **Ticket Minting:** Caller invokes `create_preverified_stepup_authorization` with a genuine `webauthn_assertion` verifying the challenge for the exact planned operation.
2. **Server Verification:**
   - Full WebAuthn assertion verification is executed.
   - Challenge is atomically consumed.
   - A short-lived ticket `authorization_id = wp_authz_<uuid>` is minted and stored in `authority_step_up_challenges` with `action = "PREVERIFIED:EMERGENCY_CONTAINMENT"`, `expires_at = now + 300s`, `consumed_at = NULL`.
3. **Execution & Atomic Single-Use Consumption:**
   - Caller invokes `execute_emergency_containment(..., stepup_authorization_id=authz_id)`.
   - The ticket is looked up, checked against caller identity, session, organization, and exact `operation_digest`.
   - The ticket is atomically consumed:
     ```sql
     UPDATE authority_step_up_challenges
     SET consumed_at = :now
     WHERE challenge_hash = :hash AND consumed_at IS NULL
     ```
   - If `rowcount != 1`, the call fails with `WEBAUTHN_CHALLENGE_REPLAY`.
4. **Strict Scope Restrictions:**
   - Pre-verified tickets are **strictly barred** for root bootstrap, key rotation, and sovereign recovery. Attempting to create a ticket for any action other than `EMERGENCY_CONTAINMENT` raises `CONTAINMENT_FORBIDDEN` ("strictly barred").
   - Any modification to the operation parameters (such as changing the target agent ID or action) produces an `operation_digest` mismatch, failing closed.

---

## 4. Empirical Test Evidence

From `tests/test_m13r3_security_regression.py`:
- `test_webauthn_policy_path_a_and_path_b`:
  - Path A execution: **PASSED (Status: CONTAINED)**
  - Path B minting & first consumption: **PASSED (Status: CONTAINED)**
  - Path B replay with same ticket: **PASSED (Rejected with WEBAUTHN_CHALLENGE_REPLAY)**
- `test_path_b_operation_mismatch_and_scope_restriction`:
  - Attempted minting for `EXECUTE_RECOVERY_REQUEST`: **PASSED (Rejected: strictly barred)**
  - Attempted consumption with target mismatch: **PASSED (Rejected: Operation digest mismatch)**
- From `tests/independent_m13r2/test_m13r_verified_containment.py`:
  - `test_api_key_cannot_substitute_for_interactive_session`: **PASSED**
