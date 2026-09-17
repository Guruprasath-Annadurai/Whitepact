# WhitePact Phase 7A: Authority Mutation & Revocation Epoch Coverage Matrix

**Document Status:** CANONICAL SPECIFICATION PASS 4 (SECURITY REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`

---

## 1. Problem Statement: Time-of-Check to Time-of-Use (TOCTOU)

In an asynchronous execution engine, an authorization is issued at `T0`, enqueued in a multi-tenant queue, and dequeued by a worker at `T1` (which may be seconds or minutes later).
If an administrator revokes a policy, suspends an organization, terminates an emergency BreakGlass session, or revokes a principal between `T0` and `T1`, the queued authorization MUST NOT be admitted or executed.

Canonical WhitePact provides a centralized epoch mechanism: `governance_revocation_epochs` and `lock_epoch(conn, organization_id, scope="governance")`.
When canonical `admit_execution()` runs under row lock, it asserts that `expected_epoch == current_epoch`. If the epoch was incremented, admission fails closed immediately with `StaleRevocationEpochError`.

However, the independent security audit revealed that not all mutable authority sources currently advance the `"governance"` epoch upon modification. This document closes every gap.

---

## 2. Comprehensive Authority Mutation Audit Matrix

| Mutable Authority Source | Durable Owner / Repository | Must Bump Governance Epoch? | Existing Implementation (`13e8de0`) | Pass 4 Specification Adaptation |
| :--- | :--- | :--- | :--- | :--- |
| **Organization Suspension / Deletion** | `OrgRepository` (`organizations`) | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Any tenant status change invalidates all pending queued work. |
| **Principal Disable / Status Change** | `WebIdentityRepository` / IAM | **YES** | **NO:** Updates user row without epoch bump | **PASS 4 ADAPTATION:** Principal status changes (deactivation, lockout) MUST call `bump_epoch_on_connection(conn, org_id, "governance")` in the same transaction. |
| **Principal Deletion / Purge** | `DeletionOrchestrator` / IAM | **YES** | **NO:** Deletes rows without epoch bump | **PASS 4 ADAPTATION:** Principal deletion MUST call `bump_epoch_on_connection(conn, org_id, "governance")` before committing. |
| **IAM Session Revocation** | `iam/session.py` (`SessionService`) | **YES** | **PARTIAL:** Only bumps `scope="iam_session"` | **PASS 4 ADAPTATION:** Session revocation MUST bump BOTH `scope="iam_session"` AND `scope="governance"` (aligning with `transfer.py` and `recovery.py`). |
| **IAM Session Expiry** | Timestamp Derived | **NO** | Derived dynamically: `now >= expires_at` | Preserved. Pre-flight check evaluates `expires_at > now`. Zero background churn. |
| **Delegation Revocation** | `DelegationRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Invalidation of delegated permits is immediate. |
| **Consent Withdrawal** | `ConsentProofRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Invalidation of consent-based permits is immediate. |
| **BreakGlass Termination** | `iam/break_glass.py` (`BreakGlassService`) | **YES** | **NO:** Only updates `iam_break_glass_sessions` status | **PASS 4 ADAPTATION:** `terminate_break_glass()` MUST call `bump_epoch_on_connection(conn, org_id, "governance")` in the same transaction. |
| **Policy Modification / Deletion** | `PolicyRepository` / `PolicyLifecycle` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Invalidation of policy-derived permits is immediate. |
| **Authority Ceiling Modification** | `OrgAuthorityCeilingRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Ceiling adjustments invalidate queued execution permits. |
| **Autonomy Budget Modification** | `OrgAutonomyBudgetRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Budget updates invalidate queued permits. |
| **Tool Trust / Risk Modification** | `ToolTrustRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Tool score degradation invalidates queued permits. |
| **Upstream Server Modification** | `UpstreamServerRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Upstream URL/credential updates invalidate queued permits. |
| **Root Authority Modification** | `RootAuthorityRepository` | **YES** | YES: Calls `bump_epoch_on_connection(conn, org_id)` | Preserved. Root key/trust changes invalidate queued permits. |

---

## 3. Atomic Linearization Guarantee

By guaranteeing that all 14 authority mutations advance `governance_revocation_epochs.epoch` under a row lock:
1. **Zero TOCTOU Window:** No separate, racy "preflight check" is needed as the ultimate security boundary. The canonical admission database transaction is the singular, non-bypassable linearization point.
2. **Deterministic Rejection:** If an authorization was issued at epoch `N`, and ANY authority mutation occurred while the authorization waited in queue, the database epoch becomes `N+1`.
3. **Fail-Closed Admission:** In `ExecutionNonceRepository.consume()`:
   ```sql
   SELECT epoch FROM governance_revocation_epochs
   WHERE organization_id = :org_id AND scope = 'governance'
   FOR UPDATE;
   ```
   If `current_epoch != expected_epoch`, the transaction immediately aborts with `StaleRevocationEpochError`. No nonce is consumed; no execution is admitted.
