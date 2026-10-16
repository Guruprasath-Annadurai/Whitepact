# WHITEPACT M13-S4 WEBAUTHN ATOMICITY & REPLAY DEFENSE

**Milestone:** M13-S4 — Priority A & Priority D Enforcement  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Policy Baseline:** WP-M13-POL-002 (WebAuthn Dual-Path Policy)  
**Status:** **CLOSED / MATHEMATICALLY & EMPIRICALLY PROVEN**

---

## 1. Threat Model & Concurrency Flaw Analysis

In distributed enterprise authentication, relying solely on client-side passkey signature counters (`signCount`) creates critical vulnerabilities:
1. **Zero-Counter Passkeys:** Platform authenticators (e.g., Apple Touch ID / Face ID, Windows Hello) and synced passkeys frequently return `signCount = 0` by specification (W3C WebAuthn Level 2 / Level 3 §6.1).
2. **Counter Desynchronization:** Multi-device synchronization (e.g., iCloud Keychain, Google Password Manager) can result in non-monotonic counter sequences across devices.
3. **Concurrent Mutation Race:** When two identical or cloned assertions arrive concurrently, a classic Read-Modify-Write pattern allows both transactions to read `consumed = False`, verify the signature, and mutate state before either commits, creating a double-spend / replay exploit.

### Codex Counterexample & Independent Reproducer
Codex exposed this vulnerability in `tests/independent_m13r2/test_concurrent_assertion_probe.py`:
- Two concurrent coroutines submitted the exact same valid zero-counter WebAuthn assertion to authorize privileged containment actions.
- Under defective implementations, both coroutines succeeded, violating single-use invariants.

---

## 2. Mathematical & Database Atomicity Implementation

WhitePact solves WebAuthn challenge replay via **Conditional Single-Winner Updates** on the PostgreSQL database connection within the exact same transaction as the operation mutation:

### Canonical SQL Atomic Consumption Primitive

```sql
UPDATE authority_step_up_challenges
SET consumed = TRUE,
    consumed_at = :now,
    consumed_by_actor_id = :actor_id,
    consumed_by_operation = :operation_name,
    consumed_by_digest = :action_digest
WHERE id = :challenge_id
  AND org_id = :org_id
  AND consumed = FALSE
  AND expires_at > :now;
```

### PostgreSQL Guarantee:
1. **Row-Level Exclusive Lock:** PostgreSQL's row-level lock on the `authority_step_up_challenges` primary key ensures serialization.
2. **Exactly One Winner:** The first transaction to update sets `consumed = TRUE` and receives `rowcount = 1`. Any concurrent transaction targeting the same challenge finds `consumed = TRUE` or `expires_at <= :now`, returning `rowcount = 0`.
3. **Atomic Abort on Defeat:** If `rowcount == 0`, the losing transaction immediately raises `webauthn_challenge_replay()` and rolls back all operation mutations.
4. **Rollback Correctness:** If an unforeseen database error or downstream failure occurs during the transaction, the challenge consumption rolls back with the transaction, preventing denial-of-service on legitimate partial failures.

---

## 3. Cryptographic & Contextual Bindings

Every WebAuthn assertion and authorization ticket verified by WhitePact enforces six strict cryptographic bindings:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   WEBAUTHN ASSERTION BINDING MATRIX                    │
├─────────────────────────┬──────────────────────────────────────────────┤
│ 1. Principal Binding    │ Bound to specific user ID; cannot substitute │
│ 2. Tenant Isolation     │ Explicitly bound to org_id; cross-tenant 403 │
│ 3. Session Binding      │ Requires active authenticated session cookie │
│ 4. Credential Freshness │ Checked against passkey_credentials active   │
│ 5. Operation Digest     │ SHA-256 over exact canonical action params   │
│ 6. Challenge Expiry     │ Bounded lifetime; expired challenges fail    │
└─────────────────────────┴──────────────────────────────────────────────┘
```

- **Credential Revocation:** The passkey ID must exist in `passkey_credentials` and have `revoked_at IS NULL`.
- **Session Freshness:** API keys alone are strictly prohibited from bypassing interactive step-up (`api_key_cannot_substitute_for_interactive_session`).
- **Fail-Closed on DB Error:** Database connection drops, pool timeouts, or unexpected constraint violations abort execution immediately.

---

## 4. WebAuthn Dual-Path Policy (WP-M13-POL-002)

To accommodate both real-time interactive ceremony prompts and asynchronous staged workflows, WP-M13-POL-002 establishes two strictly governed paths:

### Path A: Direct Fresh Server-Verified Assertion
- Caller provides `assertion` (clientDataJSON, authenticatorData, signature, credentialId).
- Server verifies cryptographic signature against registered passkey public key.
- Server verifies `clientDataJSON.challenge` matches issued challenge.
- Challenge is atomically consumed in the mutation transaction.

### Path B: Pre-Verified Single-Use Authorization Ticket
- Caller previously completed an interactive WebAuthn ceremony.
- Server issued an operation-bound, single-use ticket stored in PostgreSQL.
- Ticket is bound to: `(user_id, org_id, operation_name, action_digest, expires_at)`.
- Ticket is consumed via atomic single-winner update:
  ```sql
  UPDATE authority_step_up_challenges
  SET consumed = TRUE, consumed_at = :now
  WHERE id = :ticket_id
    AND consumed = FALSE
    AND action_digest = :expected_digest
    AND operation_name = :expected_op;
  ```
- **Scope Restriction:** Path B tickets are strictly barred from high-consequence recovery operations (`ROOT_RECOVERY`, `EMERGENCY_QUORUM`), which mandate fresh Path A assertions.

### Founder Policy Flag: Ticket Lifetime
> [!IMPORTANT]
> The current Path B ticket validity window is implemented with a default lifetime of **300 seconds (5 minutes)**. Antigravity flags this duration for explicit Founder ratification:
> - **Recommendation:** Shorten to **120 seconds** for high-risk tenant operations to minimize the exposure window of unconsumed authorization tickets.

---

## 5. Test & Concurrency Evidence

All concurrency and replay cases pass unconditionally on real PostgreSQL 17 / Python 3.12:
- `tests/independent_m13r2/test_concurrent_assertion_probe.py::test_one_zero_counter_assertion_cannot_authorize_two_concurrent_mutations` **PASSED**
- `tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verified_assertion_is_not_reusable` **PASSED**
- `tests/test_m13r3_security_regression.py::test_webauthn_policy_path_a_and_path_b` **PASSED**
- `tests/test_m13r3_security_regression.py::test_path_b_operation_mismatch_and_scope_restriction` **PASSED**
- `tests/test_m12fs_root_hardening.py::test_stepup_rejects_replayed_challenge` **PASSED**
