# WHITEPACT M13-R3 ATOMIC REPLAY PROOF

**Milestone:** M13-R3  
**Vulnerability Class:** Concurrent WebAuthn Assertion Reuse / Double Spend  
**CWE:** CWE-362 (Race Condition), CWE-294 (Authentication Bypass by Capture-replay)  
**Status:** FULLY REMEDIATED & PROVEN

---

## 1. Problem Definition & Codex M13-R2 Reproduction

In M13-R2, Codex independently reproduced a critical flaw where a single, counterless (counter value = 0), validly signed WebAuthn assertion was submitted concurrently across two parallel requests against `execute_emergency_containment`. 

Because passkeys (such as platform passkeys or iCloud Keychain authenticators) legitimately emit `sign_count = 0`, reliance on signature counter progression alone was insufficient. In the unpatched server boundary, the check for challenge validity and consumption was separated from the mutation transaction, allowing both concurrent transactions to read `consumed_at IS NULL`, pass verification, and commit two distinct privileged containment records and epoch bumps.

---

## 2. Server-Side Admission Boundary Fix

The remediation enforces transactional coupling of challenge consumption directly within the database transaction that executes the privileged operation:

1. **Deterministic Challenge Keying:**
   The WebAuthn `challenge` is base64url-encoded and hashed via SHA-256 to produce `challenge_hash = sha256(challenge_b64)`.
2. **Conditional Atomic Single-Winner Update:**
   Within `_verify_webauthn_stepup_on_conn`, the consumption is executed directly on the open PostgreSQL connection:
   ```python
   consume_res = await conn.execute(
       update(authority_step_up_challenges)
       .where(
           and_(
               authority_step_up_challenges.c.challenge_hash == challenge_hash,
               authority_step_up_challenges.c.consumed_at.is_(None),
           )
       )
       .values(consumed_at=now_iso)
   )
   if consume_res.rowcount != 1:
       raise webauthn_challenge_replay("Step-up challenge has already been consumed.")
   ```
3. **Fail-Closed Concurrency Serialization:**
   Under PostgreSQL's `READ COMMITTED` or `REPEATABLE READ` isolation level, the row-level update lock on the challenge row ensures that:
   - The first transaction to acquire the row lock updates `consumed_at = now_iso` (returning `rowcount == 1`).
   - The second concurrent transaction blocks until the first commits. Upon evaluating the updated row, its `consumed_at.is_(None)` predicate evaluates to `FALSE`, returning `rowcount == 0`.
   - The losing transaction raises `WEBAUTHN_CHALLENGE_REPLAY` and rolls back all mutations, leaving zero side-effects.

---

## 3. Cryptographic and Operational Binding Invariants

Each step-up challenge is cryptographically bound to:
- `org_id`: Tenant organization identifier (prevents cross-tenant replay).
- `user_id`: Authenticated actor user identifier.
- `action`: Specific privileged action identifier (e.g. `EMERGENCY_CONTAINMENT`).
- `operation_digest`: SHA-256 canonical JSON digest of exact operation parameters (e.g., target type, target id, containment action).
- `origin` & `rp_id`: WebAuthn Relying Party parameters verified against client data.

---

## 4. Empirical Test Evidence

Codex's original reproducer (`tests/independent_m13r2/test_concurrent_assertion_probe.py`) was executed unchanged against local PostgreSQL 16:

```bash
.venv/bin/pytest tests/independent_m13r2/test_concurrent_assertion_probe.py -o addopts="" -v
```

**Result:**
```text
tests/independent_m13r2/test_concurrent_assertion_probe.py::test_one_zero_counter_assertion_cannot_authorize_two_concurrent_mutations PASSED [100%]
```

- Concurrent requests launched: **2**
- Successful committed mutations: **1**
- Rejected replay requests: **1 (Exception: WEBAUTHN_CHALLENGE_REPLAY)**
- Double-spend prevented: **CONFIRMED**
