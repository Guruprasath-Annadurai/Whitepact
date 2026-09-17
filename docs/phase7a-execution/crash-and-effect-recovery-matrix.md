# WhitePact Phase 7A: Comprehensive Crash & Effect Recovery Matrix

**Document Status:** CANONICAL SPECIFICATION PASS 4.1 (SECURITY CONSISTENCY REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`

---

## 1. Overview & Recovery Principles

In distributed runtime systems, failures can occur at any millisecond across the lifecycle.
WhitePact adheres to four non-negotiable recovery principles:
1. **Never Replay Uncertain Side Effects:** If bytes may have reached a network socket or an isolated container began running, automatic blind replay is strictly prohibited.
2. **PostgreSQL Is the Singular Source of Truth:** Memory queues, Redis caches, and process variables are ephemeral. Visible durable state in PostgreSQL dictates post-crash behavior.
3. **Evidence Integrity Does Not Invalidate Confirmed Effects:** If a side effect succeeded but an evidence write subsequently failed, the system records an incomplete evidence audit event rather than pretending the effect never occurred.
4. **Universal Capacity Release:** Every capacity slot reserved at enqueue time is released upon terminal exit or reclaimed by the background capacity reconciler.

---

## 2. Comprehensive A–Q Crash Recovery Matrix

| Lifecycle Point | Visible Durable State After Restart | Automatic Retry Permitted? | Same Authorization Reusable? | New Authorization Required? | Reconciliation Required? | Expected Evidence / Audit Record | Capacity Release |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Before durable request creation** | None (PostgreSQL transaction not started). | YES (Client may resubmit). | N/A (Not created). | YES (New request). | NO | None (Request never reached durable boundary). | Slot not yet reserved. |
| **B. After durable request but before authorization issuance** | Impossible: Request, Auth, Attempt, and Fence committed in SAME atomic transaction. | N/A | N/A | N/A | NO | Rollback clean; no partial records. | N/A |
| **C. After issuance before queue insertion** | `runtime_execution_requests` present, `governance_execution_authorizations` (ISSUED), `runtime_execution_attempts` (PENDING, lease fields NULL). | YES (Re-queue daemon detects unqueued ISSUED authorization). | YES (Authorization unexpired & unadmitted). | NO | NO | `AUDIT_AUTHORIZATION_ISSUED` present; queue reconciliation event emitted. | Released if drop or timeout. |
| **D. After queue insertion before lease** | Request present, Auth ISSUED, QueueTicket in Redis/memory. | YES (Remains in queue until dequeued). | YES | NO | NO | None (Standard queue latency). | Released on queue drop/expiry. |
| **E. After lease before admission** | Lease ACTIVE (expired after heartbeat timeout), Attempt LEASED, Auth ISSUED. | YES (Reaper marks lease EXPIRED, attempt FAILED_PRE_EXECUTION; re-enqueues ticket if attempts < max). | YES (Nonce not consumed). | NO | NO | `AUDIT_WORKER_HEARTBEAT_TIMEOUT`, attempt marked `FAILED_PRE_EXECUTION`. | Released on lease expiry/requeue. |
| **F. During admission transaction** | Transaction rolls back. Auth remains ISSUED, Nonce uninserted. | YES (Re-attempt after lease expiration). | YES | NO | NO | DB error logged; zero partial records. | Released on abort. |
| **G. After admission commit before backend-start claim** | Auth CONSUMED, Nonce inserted, Attempt ADMITTED, Lease ACTIVE (expired). | **NO** (Nonce is already burned). | **NO** (Authorization is CONSUMED). | **YES** | NO (Guaranteed `NO_EFFECT`). | `AUDIT_ADMISSION_COMMITTED`, `AUDIT_ATTEMPT_ABORTED_PRE_EXECUTION` (No effect began). | Released by supervisor reaper. |
| **H. During backend-start claim transaction** | Transaction rolls back. Attempt remains ADMITTED. | **NO** | **NO** | **YES** | NO (Guaranteed `NO_EFFECT`). | `AUDIT_BACKEND_START_FAILED_TX`. | Released on rollback. |
| **I. After backend-start claim before container launch** | Attempt BACKEND_STARTING, effect_state EFFECT_STARTING. | **NO** (Automatic replay forbidden). | **NO** | **YES** | YES (Verify container was not spawned). | `AUDIT_BACKEND_START_COMMITTED`, reaper marks `UNCERTAIN` pending verification. | Released by supervisor. |
| **J. During local container execution** | Attempt RUNNING, Docker container ID registered, lease ACTIVE (expired). | **NO** (Automatic replay forbidden). | **NO** | **YES** | YES (Inspect Docker container exit status & stdout). | Container orphan cleaned by reaper; attempt marked `FAILED` or `UNCERTAIN`. | Released by supervisor. |
| **K. Before external transmission** | Attempt BACKEND_STARTING, effect_state EFFECT_STARTING. Socket not opened. | **NO** (Automatic replay forbidden). | **NO** | **YES** | YES (Upstream check via `effect_id`). | `AUDIT_EFFECT_ABORTED_PRE_TRANSMIT`. | Released by supervisor. |
| **L. After external transmission before response** | Attempt RUNNING, effect_state EFFECT_TRANSMITTING. | **NO** (STRICTLY FORBIDDEN). | **NO** | **YES** | **YES** (Mandatory upstream query via `effect_id`). | Attempt marked `UNCERTAIN`, `AUDIT_EFFECT_TRANSMIT_DISRUPTED`. | Released on transition to UNCERTAIN. |
| **M. After response before durable outcome** | Effect finished on remote server. Outcome not yet committed. | **NO** | **NO** | **YES** | **YES** (Upstream reconciliation via `effect_id`). | Attempt marked `UNCERTAIN`, reconciler updates to `COMPLETED` once response recovered. | Released on transition to UNCERTAIN. |
| **N. After durable outcome before evidence** | Attempt COMPLETED / FAILED, outcome committed, evidence write failed. | **NO** (Do NOT replay effect). | **NO** | **YES** | NO (Effect already final). | `AUDIT_EVIDENCE_PERSISTENCE_FAILED`. Reconstructed evidence bundle stored. | Released upon terminal attempt update. |
| **O. After evidence before attempt finalization** | Outcome committed, evidence committed, attempt state RUNNING. | NO | NO | NO | NO | Reaper observes completed evidence and marks attempt `COMPLETED`. | Released by reaper. |
| **P. After attempt finalization before lease release** | Attempt COMPLETED, lease ACTIVE (expired). | NO | NO | NO | NO | Reaper releases lease cleanly; zero impact on execution result. | Released by reaper. |
| **Q. After lease release before capacity release** | Lease COMPLETED, capacity reservation unreleased in Redis. | NO | NO | NO | NO | Background capacity reconciler audits active leases and releases orphaned slot. | Reconciler releases slot. |

---

## 3. Detailed Recovery Handling for Key Failure Modes

### 3.1 Failure Point G: Admission Committed, Crash Before Backend Start
- **Durable State:** Nonce is inserted into `governance_execution_nonces`. Authorization status is `CONSUMED`. Attempt status is `ADMITTED`.
- **Physical Fact:** No container was started, and no network packet was transmitted.
- **Safety Invariant:** Because the permit's single-use nonce is already consumed in PostgreSQL, neither this worker nor any other worker may resume execution using this permit.
- **Resolution:** The `WorkerSupervisor` detects lease expiry on an attempt in state `ADMITTED`. It transitions the attempt to `FAILED_PRE_EXECUTION` with reason code `ADMISSION_TIMED_OUT_BEFORE_BACKEND_START`, releases the capacity reservation, and terminates the attempt. The client receives a terminal response and may request a fresh authorization if desired.

### 3.2 Failure Point L: Crash During Remote Transmission (`UNCERTAIN`)
- **Durable State:** Attempt is `RUNNING`, `effect_state` is `EFFECT_TRANSMITTING`, `effect_id` is recorded.
- **Physical Fact:** An HTTP request was sent to an upstream MCP server. The server may have executed the action, crashed mid-execution, or dropped the connection.
- **Safety Invariant:** Automatic re-execution could double-charge credit cards, delete duplicate records, or execute redundant mutations.
- **Resolution:**
  1. The supervisor transitions the attempt to `UNCERTAIN` and `effect_state = 'EFFECT_UNCERTAIN'`, and releases the capacity slot.
  2. The system triggers asynchronous reconciliation using the stable `effect_id` as the query key.
  3. If the upstream server confirms the request was received and processed, the reconciler records the result and marks the attempt `COMPLETED`.
  4. If the upstream server confirms the request was never received, the attempt is marked `FAILED`.
  5. If the upstream server cannot determine the outcome, the execution remains permanently `UNCERTAIN`, requiring human administrator decision.

### 3.3 Failure Point N: Evidence Persistence Failure After Confirmed Side Effect
- **Durable State:** The side-effect succeeded cleanly. However, a database connection blip caused the evidence repository write to fail.
- **Fatal Error to Avoid:** Retrying the tool or external request to "get fresh evidence." This duplicates the real-world side-effect.
- **Resolution:** The worker transitions the attempt to `COMPLETED` with an explicit audit annotation: `evidence_status = 'INCOMPLETE'`. Capacity is released. A background evidence recovery worker reconstructs the cryptographic evidence bundle from stdout/result logs and the committed durable outcome row without re-running the tool.
