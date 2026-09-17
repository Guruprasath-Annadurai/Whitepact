# WhitePact Phase 7A: Execution Call-Path and Single-Admission Closure

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary & Problem Resolution

An exhaustive audit of the canonical codebase (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`) identified two critical authority integration challenges:
1. **Uncovered Issuance Path in Upstream Dispatch:**
   - Canonical `authorize_execution()` is called at 3 production sites:
     - `src/responsibleai/mcp/governance_integration.py:468` (`execute_governed_action`)
     - `src/responsibleai/mcp/governance_integration.py:816` (`resolve_approval_and_execute`)
     - `src/responsibleai/mcp/upstream_dispatch.py:322` (`dispatch_upstream_action`)
   - Prior drafts only assigned durable issuance persistence to `governance_integration.py`, leaving `upstream_dispatch.py` vulnerable to an issuance bypass where an authorization could enter queued or distributed execution without a durable PostgreSQL record in `governance_execution_authorizations`.
2. **Double `admit_execution()` Risk:**
   - Existing production `admit_execution()` call sites:
     - `src/responsibleai/governance/execution.py:334` (`InternalToolExecutor.execute`)
     - `src/responsibleai/governance/upstream_executor.py:226` (`UpstreamServer.execute`)
   - If the new Phase 7A worker invokes `admit_execution()` prior to dispatching to `InternalToolExecutor` or `UpstreamServer`, and those executors retain their existing internal call to `admit_execution()`, the second invocation will fail due to duplicate nonce consumption (`rowcount == 0`), aborting valid executions or corrupting state.

This specification definitively resolves both issues:
- **Centralized Durable Issuance:** All 3 `authorize_execution()` call sites are routed through a shared issuance boundary (`DurableExecutionAuthorizationIssuer.issue`), guaranteeing that every `ExecutionAuthorization` is durably committed to PostgreSQL before any `QueueTicket` is created.
- **Worker-Owned Single Admission (Option A):** The worker exclusively owns the canonical `admit_execution()` invocation immediately before execution. It binds a typed, unforgeable `AdmittedExecution` context that is handed off to `InternalToolExecutor.execute()` or `UpstreamServer.execute()`. Downstream executors consume this context and MUST NOT invoke `admit_execution()` again.

---

## 2. Production Call-Path Inventory & Tracing

### 2.1 Complete Production Call Paths

| Call Path | Entry Point | `authorize_execution` Owner | Durable Issuance Owner | Queueing Owner | Worker Owner | `admit_execution` Owner | Downstream Executor | Evidence Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Path 1: Governed Local Tool** | `execute_governed_action` in `mcp/governance_integration.py` | `governance_integration.py:468` | `DurableExecutionAuthorizationIssuer.issue` (`governance_execution_authorizations`) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (calls canonical `admit_execution`) | `InternalToolExecutor.execute(admitted_context)` -> `ContainerIsolationBackend` | `EvidenceStore` + `AuditLedger` |
| **Path 2: Approval Resolution** | `resolve_approval_and_execute` in `mcp/governance_integration.py` | `governance_integration.py:816` | `DurableExecutionAuthorizationIssuer.issue` (`governance_execution_authorizations`) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (calls canonical `admit_execution`) | `InternalToolExecutor.execute(admitted_context)` -> `ContainerIsolationBackend` | `EvidenceStore` + `AuditLedger` |
| **Path 3: Upstream MCP Dispatch** | `dispatch_upstream_action` in `mcp/upstream_dispatch.py` | `upstream_dispatch.py:322` | `DurableExecutionAuthorizationIssuer.issue` (`governance_execution_authorizations`) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (calls canonical `admit_execution`) | `UpstreamServer.execute(admitted_context)` with `SafeNetworkBackend` | `EvidenceStore` + `AuditLedger` |

---

## 3. Centralized Durable Issuance Architecture

### 3.1 Principle: Non-Bypassable Durable Issuance
To eliminate duplicate persistence logic and prevent future call-path leaks, Phase 7A introduces a centralized issuance boundary:
`src/responsibleai/governance/execution_issuer.py`: `DurableExecutionAuthorizationIssuer`.

```python
class DurableExecutionAuthorizationIssuer:
    """Centralized durable issuer for ExecutionAuthorizations.

    Guarantees that an ExecutionAuthorization is durably committed to PostgreSQL
    in `governance_execution_authorizations` before it can be handed to the
    admission controller or queued.
    """
    def __init__(self, repository: ExecutionAuthorizationRepository) -> None:
        self._repository = repository

    async def issue(
        self,
        authorization: ExecutionAuthorization,
    ) -> ExecutionAuthorization:
        # Enforce valid allow decision
        if authorization.decision not in (
            GovernanceDecision.ALLOW,
            GovernanceDecision.ALLOW_WITH_REDACTION,
        ):
            raise InvalidAuthorizationStateError(
                f"Cannot issue authorization with decision {authorization.decision}"
            )

        # Persist durably in PostgreSQL (status = 'ISSUED')
        await self._repository.create(authorization)
        return authorization
```

### 3.2 Integration Across All Call Sites
1. **`execute_governed_action` (`src/responsibleai/mcp/governance_integration.py`):**
   ```python
   auth = authorize_execution(policy_result, action, expected_epoch=epoch)
   await self._issuer.issue(auth)  # Durably committed to PostgreSQL
   ticket = await self._admission_controller.reserve_and_enqueue(auth, action)
   ```
2. **`resolve_approval_and_execute` (`src/responsibleai/mcp/governance_integration.py`):**
   ```python
   auth = authorize_execution(policy_result, action, expected_epoch=epoch)
   await self._issuer.issue(auth)  # Durably committed to PostgreSQL
   ticket = await self._admission_controller.reserve_and_enqueue(auth, action)
   ```
3. **`dispatch_upstream_action` (`src/responsibleai/mcp/upstream_dispatch.py`):**
   ```python
   auth = authorize_execution(policy_result, action, expected_epoch=epoch)
   await self._issuer.issue(auth)  # Durably committed to PostgreSQL
   ticket = await self._admission_controller.reserve_and_enqueue(auth, action)
   ```

### 3.3 Strict Invariant
- **Every `QueueTicket` references a durably committed `governance_execution_authorizations` row.**
- If the database write fails (e.g. timeout, disconnect, constraint violation), the request fails closed with HTTP 500/503.
- No `QueueTicket` is emitted; no item enters Redis or in-memory queues; unpersisted authority count = 0.

---

## 4. Single Admission Ownership & `AdmittedExecution` Context

### 4.1 Comparison of Admission Architecture Options

| Dimension | Option A: Worker Owns Admission (CHOSEN) | Option B: Executor Owns Admission | Option C: Shared Execution Proxy |
| :--- | :--- | :--- | :--- |
| **Admission Invocation Site** | `ResponsibleWorker.execute_task()` | `InternalToolExecutor.execute()` and `UpstreamServer.execute()` | Separate standalone execution service |
| **Last-Moment Preservation** | **EXCELLENT:** Invoked immediately before backend handoff, after queue wait and lease acquisition. | **EXCELLENT:** Invoked inside executor right before transport. | **FAIR:** Adds network RPC hop between admission and transport. |
| **Double-Admission Risk** | **ZERO:** Downstream executors accept `AdmittedExecution` context and do not admit. | **MODERATE:** Worker might inadvertently call admit, causing conflict. | **HIGH:** Complex ownership boundary across multiple hops. |
| **Upstream & Container Symmetry** | **PERFECT:** Identical admission flow for both local Docker and remote MCP servers. | **POOR:** Requires duplicating lease & epoch checks in multiple executors. | **POOR:** Requires new service daemon. |
| **Codebase Alignment** | **HIGH:** Minimal change to canonical contracts, highly testable. | **MEDIUM:** Inconsistent with Phase 7A worker isolation model. | **LOW:** High architectural complexity. |

### 4.2 Architecture Choice: OPTION A — Worker-Owned Admission
Phase 7A selects **Option A**. The worker process performs canonical `admit_execution()` exactly once, immediately before delegating side-effect execution to the concrete backend.

### 4.3 The Typed `AdmittedExecution` Context
To ensure downstream executors cannot be invoked without valid canonical admission, `admit_execution()` returns an immutable, unforgeable `AdmittedExecution` token:

```python
@dataclass(frozen=True)
class AdmittedExecution:
    """Proof of successful canonical admission for a specific execution attempt.

    This object cannot be casually forged: it is constructed ONLY within
    `admit_execution()` upon successful commit of the atomic PostgreSQL
    transaction (epoch verification, nonce consumption, authorization update).
    """
    execution_id: str
    authorization_id: str
    organization_id: str
    principal_id: str
    action_digest: str
    target_fingerprint: str | None
    lease_id: str
    admitted_at: datetime
    nonce: str

    def __post_init__(self) -> None:
        if not self.authorization_id or not self.nonce or not self.action_digest:
            raise ValueError("Malformed AdmittedExecution context")
```

### 4.4 Downstream Executor Signatures & Guardrails
1. **`InternalToolExecutor.execute` (`src/responsibleai/governance/execution.py`):**
   ```python
   async def execute(
       self,
       action: GovernedAction,
       admitted_context: AdmittedExecution,
       workspace: EphemeralWorkspace | None = None,
   ) -> ToolResult:
       # Verify that admitted_context matches action
       if admitted_context.action_digest != compute_action_digest(action):
           raise SecurityBindingMismatchError("Admitted action digest mismatch")
       if admitted_context.organization_id != action.agent.organization_id:
           raise SecurityBindingMismatchError("Admitted organization mismatch")

       # DO NOT call admit_execution() again.
       # Proceed directly to IsolationBroker / ContainerIsolationBackend.execute()
       return await self._broker.execute(action, workspace=workspace)
   ```
2. **`UpstreamServer.execute` (`src/responsibleai/governance/upstream_executor.py`):**
   ```python
   async def execute(
       self,
       action: GovernedAction,
       admitted_context: AdmittedExecution,
       target: UpstreamTarget,
   ) -> UpstreamResult:
       # Verify that admitted_context matches action
       if admitted_context.action_digest != compute_action_digest(action):
           raise SecurityBindingMismatchError("Admitted action digest mismatch")
       if admitted_context.organization_id != action.agent.organization_id:
           raise SecurityBindingMismatchError("Admitted organization mismatch")

       # Verify target fingerprint hasn't drifted
       if admitted_context.target_fingerprint:
           check_target_fingerprint(target, admitted_context.target_fingerprint)

       # DO NOT call admit_execution() again.
       # Proceed directly through SafeNetworkBackend to external MCP endpoint
       return await self._safe_network.dispatch_http(target, action)
   ```

---

## 5. Preservation of Last-Moment Admission

Canonical admission MUST occur as late as safely possible:
- **NOT** at request arrival time.
- **NOT** before entering the wait queue.
- **NOT** before acquiring the distributed worker lease.
- **NOT** before pre-flight binding revalidation.

The worker executes canonical admission:
1. Dequeues `QueueTicket` from fair scheduler.
2. Acquires exclusive `ACTIVE` lease in `runtime_worker_leases`.
3. Performs pre-flight revalidation (organization active, principal valid, BreakGlass unexpired, action digest match).
4. **LAST MOMENT:** Calls canonical `admit_execution()`, atomically executing in PostgreSQL:
   - Row-level lock on `governance_revocation_epochs` (`lock_epoch`).
   - Epoch freshness check (`current == expected`).
   - Insertion of single-use `nonce` into `governance_execution_nonces`.
   - Conditional atomic update of `governance_execution_authorizations` (`status = 'ISSUED' -> 'CONSUMED'`, `expires_at > now`).
   - Assertion of `rowcount == 1`.
5. Receives `AdmittedExecution` context.
6. Immediately passes `AdmittedExecution` to `InternalToolExecutor` or `UpstreamServer` for container/network execution.

There is zero async wait or queueing between Step 4 and Step 6.

---

## 6. Direct / Legacy Execution Bypass Audit

A complete scan of the canonical codebase (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`) was performed for direct invocations of execution backends:

| Backend / Component | Direct Invocations Found | Classification | Verification & Protection |
| :--- | :--- | :--- | :--- |
| **`InternalToolExecutor.execute`** | 1 production site (`governance_integration.py:488`) | **ROUTED THROUGH PHASE 7A GATE** | Replaced by worker dispatch loop in Phase 7A. Direct callers adapted to require `AdmittedExecution`. |
| **`UpstreamServer.execute`** | 1 production site (`upstream_dispatch.py:340`) | **ROUTED THROUGH PHASE 7A GATE** | Replaced by worker dispatch loop in Phase 7A. Requires `AdmittedExecution`. |
| **`ContainerIsolationBackend.execute`** | 1 internal site (`isolation/broker.py:112`) | **ROUTED THROUGH PHASE 7A GATE** | Accessible only via `IsolationBroker` inside `InternalToolExecutor`. Cannot be reached directly. |
| **`SafeNetworkBackend`** | 1 internal site (`upstream_executor.py:245`) | **ROUTED THROUGH PHASE 7A GATE** | Mandatory component of `UpstreamServer.execute`. Egress rules, SSRF protection, and DNS pinning preserved. |
| **Webhook Transport** | 0 direct unmediated sites | **NON-CONSEQUENTIAL / NONE** | No standalone webhook dispatch exists outside governed MCP tool calls. |
| **MCP Upstream Transport** | 1 production site (`mcp/client.py`) | **ROUTED THROUGH PHASE 7A GATE** | Invoked strictly via `UpstreamServer.execute`. |

### Summary of Audit:
- Total production consequential paths inspected: **6**
- Production bypasses found: **0**
- Unmediated network or tool invocations: **0**

---

## 7. Activation Gate (Task 10 Dispatcher Gate)

To guarantee that the worker dispatcher and execution workers cannot be activated prematurely, Task 10 enforces an explicit activation gate.

### Mandatory Preconditions for Task 10 Activation:
1. **All Issuance Paths Closed:**
   - Durable issuance verified for `execute_governed_action`.
   - Durable issuance verified for `resolve_approval_and_execute`.
   - Durable issuance verified for `dispatch_upstream_action`.
   - PostgreSQL persistence precedes queueing in 100% of cases.
2. **Single Admission Proven:**
   - Worker owns canonical `admit_execution()`.
   - `InternalToolExecutor` requires `AdmittedExecution` and does not call `admit_execution()`.
   - `UpstreamServer` requires `AdmittedExecution` and does not call `admit_execution()`.
   - Double-admission test proves zero duplicate nonce consumption.
3. **Target Fingerprint & Safe Network Preserved:**
   - Upstream target drift detection verified.
   - `SafeNetworkBackend` remains mandatory on all external HTTP/MCP calls.

No execution dispatcher may be activated before all preconditions pass.

---

## 8. Test Plan for Call-Path & Admission Closure

The following automated tests will be authored during Phase 7A implementation:

1. `tests/runtime/test_durable_issuance_all_paths.py`:
   - Proves `execute_governed_action` persists authorization before queueing.
   - Proves `resolve_approval_and_execute` persists authorization before queueing.
   - Proves `dispatch_upstream_action` persists authorization before queueing.
   - Proves that DB disconnect or write failure produces HTTP 500/503 with zero `QueueTicket` emissions.
2. `tests/runtime/test_single_admission_internal_tool.py`:
   - Mock `admit_execution` and assert `call_count == 1` across entire execution lifecycle.
   - Verify `InternalToolExecutor.execute` succeeds with valid `AdmittedExecution`.
   - Verify calling `InternalToolExecutor.execute` without `AdmittedExecution` raises `TypeError`.
3. `tests/runtime/test_single_admission_upstream.py`:
   - Mock `admit_execution` and assert `call_count == 1` across entire upstream dispatch lifecycle.
   - Verify `UpstreamServer.execute` succeeds with valid `AdmittedExecution`.
   - Verify `SafeNetworkBackend` is invoked with resolved target.
4. `tests/runtime/test_double_admission_rejection.py`:
   - Manually trigger a simulated second `admit_execution` attempt with the same authorization.
   - Assert `AuthorizationAlreadyConsumedError` is raised and tool/network execution is aborted.
5. `tests/runtime/test_admitted_context_integrity.py`:
   - Attempt to execute `InternalToolExecutor` with an `AdmittedExecution` containing a modified `action_digest`.
   - Assert `SecurityBindingMismatchError` is raised immediately.
   - Attempt to execute with an `AdmittedExecution` from a different tenant (`organization_id`).
   - Assert `SecurityBindingMismatchError` is raised immediately.
6. `tests/runtime/test_upstream_target_drift.py`:
   - Change resolved IP address or fingerprint between policy evaluation and execution.
   - Assert `TargetFingerprintMismatchError` is raised before network dispatch.
