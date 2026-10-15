# WHITEPACT M13-S4 QUORUM RECOVERY & INDEPENDENT AUTHORITY

**Milestone:** M13-S4 — Priority C Enforcement  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Status:** **CLOSED / VERIFIED ON REAL POSTGRESQL**

---

## 1. Threat Model & Recovery Governance Principles

Emergency root recovery and organization resurrection are the highest-consequence actions in the WhitePact architecture. If an attacker or compromised administrator could unilaterally trigger recovery or manipulate quorum thresholds, enterprise customer authority would collapse.

### Core Governance Invariants:
1. **M-of-N Quorum Requirement:** No single individual can approve a recovery request. A mathematically enforced threshold (e.g., 2-of-3, 3-of-5) of distinct authorized administrators must explicitly cast approval votes.
2. **Anti-Self-Approval Rule:** The initiator of a recovery request is strictly prohibited from voting on their own request (`requester_user_id != voter_user_id`).
3. **Dynamic Pre-Execution Eligibility Recheck:** Approver credentials and organizational memberships are evaluated not only when votes are cast, but **dynamically re-evaluated immediately before recovery execution**. If an approver was demoted, suspended, or removed after voting, their vote is disqualified at execution time.
4. **Authority Attenuation:** Recovery execution restores **only** the authority scope explicitly specified in the approved proposed parameters; it can never restore broader privileges than requested.
5. **Root Key Proof of Possession:** The recovery execution ceremony requires a valid cryptographic signature from the customer's hardware root signing key (ECDSA P-256 / Ed25519) proving current physical possession.

---

## 2. Dynamic Membership Re-Evaluation Architecture

A major vulnerability in naive approval systems is "time-of-approval vs. time-of-execution" privilege retention. If Administrator Alice votes to approve a recovery request, but is terminated and demoted to an untrusted role 10 minutes later, executing the recovery request based on static historical votes constitutes a critical security bypass.

### WhitePact Dynamic Evaluation Query

```python
# Query distinct active administrator memberships dynamically at execution time
stmt = (
    select(web_memberships.c.user_id)
    .where(
        web_memberships.c.org_id == org_id,
        web_memberships.c.user_id.in_(approved_voter_ids),
        web_memberships.c.role.in_(["OWNER", "ADMIN"]),
        web_memberships.c.status == "ACTIVE",
    )
)
active_admin_ids = set((await conn.execute(stmt)).scalars().all())

# Recheck valid active votes against threshold
valid_active_votes = [v for v in approved_votes if v.voter_user_id in active_admin_ids]
if len(valid_active_votes) < threshold:
    raise quorum_not_met(
        f"Quorum requirement ({threshold}) not met after dynamic admin recheck. "
        f"Only {len(valid_active_votes)} valid active approver votes remain."
    )
```

---

## 3. Database Constraints & Concurrency Guarantees

In PostgreSQL, the quorum recovery state machine is backed by relational uniqueness and foreign key constraints:

### Uniqueness & Race Prevention:
1. **Duplicate Vote Rejection:** `authority_recovery_votes` enforces `UNIQUE(request_id, voter_user_id)`. Concurrent voting attempts by the same user on the same request fail closed via PostgreSQL `UniqueViolationError`.
2. **Atomic Recovery Execution:** The recovery execution transaction acquires an exclusive row lock (`SELECT FOR UPDATE`) on the `authority_recovery_requests` record. If the record has `status = 'EXECUTED'`, subsequent concurrent execution requests are rejected immediately with `recovery_already_executed()`.
3. **Action Digest Binding:** Every vote and the final execution request must provide an `action_digest` that exactly matches the SHA-256 digest of the canonical `proposed_parameters_json`. Any mutation of recovery parameters invalidates all existing votes.

---

## 4. Cryptographic Proof of Possession

Execution of a root recovery request requires a cryptographic proof of possession:
- **Challenge:** A non-repeating cryptographic challenge `wp_recov_pop_<nonce>`.
- **Payload:** SHA-256 over `(request_id, org_id, action_digest, challenge)`.
- **Signature:** Signed by the customer root private key using ECDSA (P-256) or Ed25519.
- **Verification:** The server validates the signature against the customer's registered `trust_fabric_trust_roots` public key. Forged signatures, modified payloads, or replayed challenges fail closed.

---

## 5. Test & Concurrency Evidence

All quorum recovery and anti-regression tests pass cleanly against real PostgreSQL:
- `tests/test_m13r3_security_regression.py::test_quorum_role_demotion_invalidates_recovery` **PASSED**
- `tests/test_m13r3_security_regression.py::test_quorum_anti_self_approval_and_duplicate_voting` **PASSED**
- `tests/test_m12fs_root_hardening.py::test_quorum_recovery_full_lifecycle_2_of_3` **PASSED**
- `tests/test_m12fs_root_hardening.py::test_quorum_pre_execution_deactivation_check` **PASSED**
- `tests/test_m12fs_root_hardening.py::test_recovery_request_digest_mismatch_rejected` **PASSED**
- `tests/test_m12fs_root_hardening.py::test_root_proof_of_possession_valid_and_forged` **PASSED**
- `tests/independent_m13r2/test_additional_readonly_probes.py::test_real_postgres_generated_ids_vote_uniqueness_and_rollback` **PASSED**
