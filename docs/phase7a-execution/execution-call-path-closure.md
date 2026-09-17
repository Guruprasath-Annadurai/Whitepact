# WhitePact Phase 7A: Execution Call-Path and Single-Admission Closure

**Document Status:** CANONICAL SPECIFICATION PASS 4.4 (SECURITY BOUNDARY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0049_runtime_execution_requests.py` through `0052_runtime_worker_leases.py`

---

## 1. Executive Summary & Problem Resolution

An exhaustive audit of the canonical codebase (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`) identified critical authority integration challenges:
1. **Uncovered Issuance Path in Upstream Dispatch:**
   - Canonical `authorize_execution()` is called at 3 production sites:
     - `src/responsibleai/mcp/governance_integration.py:468` (`execute_governed_action`)
     - `src/responsibleai/mcp/governance_integration.py:816` (`resolve_approval_and_execute`)
     - `src/responsibleai/mcp/upstream_dispatch.py:322` (`dispatch_upstream_action`)
   - All 3 call sites route through `DurableExecutionAuthorizationIssuer.issue()`.
2. **Atomic Admission & Attempt Transition (F4.2-01):**
   - Canonical admission in `ExecutionNonceRepository.consume()` atomically updates authorization `ISSUED -> CONSUMED` and attempt `LEASED -> ADMITTED` in the same PostgreSQL transaction (`rowcount == 1`).
3. **Synchronous Lease Revalidation at Final CAS (F4.3-01):**
   - Both `claim_local_effect_start()` and `claim_external_effect_transmission()` synchronously verify the CURRENT active unexpired lease under row lock (`FOR UPDATE`). A stalled zombie worker whose lease expired or was superseded fails closed, independent of background reaper timing.
4. **Non-Reconstructible Backend Claim & Action Binding (F4.3-02):**
   - `claim_backend_start()` generates raw `backend_start_token` and stores only its SHA-256 hash on `runtime_execution_attempts`. The final pre-effect CAS checks `backend_start_token_hash`, verifies the immutable durable request `action_digest`, and clears `backend_start_token_hash = NULL`.
5. **Target Fingerprint Contract (F4.3-03):**
   - `BackendExecutionClaim` carries `target_fingerprint: str | None` sourced from durable authorization. Upstream execution enforces that caller cannot override durable target fingerprint, validates resolved target via `SafeNetworkBackend`, and pins IP before final CAS.
6. **Execution Scope Ambiguity (Hosted vs Community-Local):**
   - Hosted mode enforces `HOSTED_GOVERNANCE_STRICT = True`, rejecting direct un-governed tool execution with HTTP 403 Forbidden.

---

## 2. Production Call-Path Inventory & Tracing

### 2.1 Complete Production Issuance Call Sites

| Call Site File & Line | Calling Function | Purpose | Upstream / Local | Target Invocation Path |
| :--- | :--- | :--- | :--- | :--- |
| `src/responsibleai/mcp/governance_integration.py:468` | `execute_governed_action` | Policy-governed local action execution | Local Container | Internal tool dispatch (`InternalToolExecutor.execute`) |
| `src/responsibleai/mcp/governance_integration.py:816` | `resolve_approval_and_execute` | Post-approval execution after human grant | Local or Upstream | Routes to internal executor or upstream dispatch depending on target |
| `src/responsibleai/mcp/upstream_dispatch.py:322` | `dispatch_upstream_action` | Direct policy-governed upstream MCP dispatch | Upstream Network | Network egress dispatch (`UpstreamMCPExecutor.execute` via `SafeNetworkBackend`) |

---

## 3. End-to-End Call Path Taxonomy

| Call Path | Execution Mode | Initial Entrypoint | Issuance Site | Durable Issuance Mechanism | Admission & Queueing | Dispatch & Worker | Execution Linearization & Claim | Pre-Effect CAS | Downstream Execution Backend | Evidence & Audit Pipeline |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Path 1: Governed Local Tool** | HOSTED GOVERNED | `execute_governed_action` in `mcp/governance_integration.py` | `governance_integration.py:468` | `DurableExecutionAuthorizationIssuer.issue` (Mig 0049/0050) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution` + `LEASED->ADMITTED`) | `claim_backend_start` -> `claim_local_effect_start` | `InternalToolExecutor.execute(action, claim)` | `EvidenceStore` (evidence_status=`COMMITTED`) |
| **Path 2: Approval Local Tool** | HOSTED GOVERNED | `resolve_approval_and_execute` in `mcp/governance_integration.py` | `governance_integration.py:816` | `ApprovalExecutionService.consume_and_issue` (Atomic TX) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution` + `LEASED->ADMITTED`) | `claim_backend_start` -> `claim_local_effect_start` | `InternalToolExecutor.execute(action, claim)` | `EvidenceStore` (evidence_status=`COMMITTED`) |
| **Path 3: Upstream MCP Dispatch** | HOSTED GOVERNED | `dispatch_upstream_action` in `mcp/upstream_dispatch.py` | `upstream_dispatch.py:322` | `DurableExecutionAuthorizationIssuer.issue` (Mig 0049/0050) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution` + `LEASED->ADMITTED`) | `claim_backend_start` -> `claim_external_effect_transmission` | `UpstreamMCPExecutor.execute(action, claim, target)` | `EvidenceStore` (evidence_status=`COMMITTED`) |
| **Path 4: Approval Upstream MCP** | HOSTED GOVERNED | `resolve_approval_and_execute` with upstream target | `governance_integration.py:816` | `ApprovalExecutionService.consume_and_issue` (Atomic TX) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution` + `LEASED->ADMITTED`) | `claim_backend_start` -> `claim_external_effect_transmission` | `UpstreamMCPExecutor.execute(action, claim, target)` | `EvidenceStore` (evidence_status=`COMMITTED`) |

---

## 4. Universal Durable Authority Chain

Every execution follows this unified control chain:
```
ActionRequest
  -> Policy Evaluation
  -> DurableExecutionAuthorizationIssuer.issue() [Atomic PostgreSQL TX]
       (runtime_execution_requests, governance_execution_authorizations,
        initial runtime_execution_attempts [PENDING, evidence_status=PENDING],
        runtime_execution_fences)
  -> AdmissionController.reserve_execution()
  -> QueueTicket enqueued
  -> FairExecutionScheduler.dequeue()
  -> Worker acquires lease (status=ACTIVE, generation=N)
  -> Stage 1 Early Invalidation
  -> Stage 2 Pre-flight Revalidation
  -> Canonical admit_execution() [Atomic PG TX: LEASED -> ADMITTED, rowcount == 1]
  -> claim_backend_start() [Atomic PG TX: ADMITTED -> BACKEND_STARTING, stores token_hash, returns BackendExecutionClaim]
  -> Atomic Pre-Effect CAS [Revalidates Lease FOR UPDATE + Action Digest + Consumes Token, rowcount == 1]
       (claim_local_effect_start OR claim_external_effect_transmission)
  -> ContainerIsolationBackend OR UpstreamMCPExecutor (SafeNetworkBackend)
  -> Durable Outcome Row
  -> EvidenceStore (evidence_status = 'COMMITTED')
  -> Attempt Terminal Update (COMPLETED)
  -> Finalize Lease & Release Capacity
```

---

## 5. Executor Signatures & Pre-Effect Atomic CAS (F4.3-01, F4.3-02, F4.3-03)

Executors do NOT accept `AdmissionReceipt`. They require `BackendExecutionClaim`. They execute an atomic CAS transaction with `rowcount == 1` immediately prior to container or socket invocation:

### 5.1 `InternalToolExecutor.execute`
```python
async def execute(
    self,
    action: ActionRequest,
    claim: BackendExecutionClaim,
    workspace: EphemeralWorkspace | None = None,
) -> ToolResult:
    # 1. Structural binding checks
    if claim.action_digest != compute_action_digest(action):
        raise SecurityBindingMismatchError("Action digest mismatch")
    if claim.organization_id != action.agent.organization_id:
        raise SecurityBindingMismatchError("Organization mismatch")

    # 2. Atomic Pre-Effect CAS in PostgreSQL (F4.3-01, F4.3-02)
    # Synchronously revalidates active unexpired lease under lock,
    # asserts durable action_digest match, verifies and consumes token hash,
    # and transitions state from BACKEND_STARTING to RUNNING asserting rowcount == 1
    await self._attempt_repo.claim_local_effect_start(claim)

    # 3. Invoke isolated container
    return await self._container_backend.execute(action, workspace=workspace)
```

### 5.2 `UpstreamMCPExecutor.execute`
```python
async def execute(
    self,
    action: ActionRequest,
    claim: BackendExecutionClaim,
    target: UpstreamTarget,
) -> UpstreamResult:
    # 1. Structural binding checks
    if claim.action_digest != compute_action_digest(action):
        raise SecurityBindingMismatchError("Action digest mismatch")
    if claim.organization_id != action.agent.organization_id:
        raise SecurityBindingMismatchError("Organization mismatch")

    # 2. Target verification & IP Pinning via SafeNetworkBackend (F4.3-03)
    target_fingerprint = compute_upstream_target_fingerprint(target)
    if claim.target_fingerprint is not None and claim.target_fingerprint != target_fingerprint:
        raise TargetFingerprintMismatchError("Target fingerprint does not match durable authorized fingerprint")
    if claim.target_fingerprint is None and target_fingerprint is not None:
        raise TargetFingerprintMismatchError("Target fingerprint required by target but missing from durable claim")

    resolved_ip = await self._safe_network.validate_target_and_resolve_ip(target)

    # 3. Atomic Pre-Effect CAS immediately pre-socket (F4.3-01, F4.3-02, F4.3-03)
    # Synchronously revalidates active unexpired lease under lock,
    # asserts durable action_digest and target_fingerprint match,
    # verifies and consumes token hash, and transitions state to RUNNING / EFFECT_TRANSMITTING
    await self._attempt_repo.claim_external_effect_transmission(claim)

    # 4. Socket transmission to pinned IP with stable effect_id
    return await self._safe_network.dispatch_http_pinned(
        target, action, pinned_ip=resolved_ip, idempotency_key=claim.effect_id
    )
```

---

## 6. Activation Gate (Task 10 Dispatcher Gate)

Task 10 (Dispatcher & Worker Activation) remains strictly closed until all prerequisites are implemented and tested:
1. Durable immutable request storage (`0049_runtime_execution_requests`).
2. Tenant-scoped idempotent issuance (`UNIQUE(organization_id, idempotency_key)`).
3. All 3 production issuance paths closed via PostgreSQL persistence.
4. Atomic approval consumption and authorization issuance (`UNIQUE(approval_id)`).
5. Canonical admission transaction combining nonce insert, authorization status update, and attempt transition `LEASED -> ADMITTED` (`rowcount == 1`).
6. Universal epoch invalidation covering all 26 audited authority mutations across 13 domain subsystems.
7. Monotonic worker fencing (`0052_runtime_worker_leases` & `runtime_execution_fences`).
8. Durable attempt state machine (`0051_runtime_execution_attempts`, `evidence_status` column).
9. One-shot backend-start claim generating raw `backend_start_token` and storing `backend_start_token_hash` on attempt.
10. Atomic pre-effect CAS transitions (`claim_local_effect_start` & `claim_external_effect_transmission`) synchronously revalidating active unexpired lease `FOR UPDATE` and closing read/write races.
11. Pre-effect CAS validation of durable request `action_digest` and single-use consumption of token hash (`NULL`).
12. Upstream execution binding to durable `target_fingerprint` and IP pinning in `SafeNetworkBackend`.
13. Strict evidence precedence: EvidenceStore record committed while attempt remains `RUNNING`, followed by terminal CAS to `COMPLETED` (`evidence_status = 'COMMITTED'`).
14. Deterministic crash recovery for Crash Point O via supervisor EvidenceStore inspection.
15. Complete append-only request immutability trigger rejecting all UPDATE/DELETE.
16. Universal capacity reservation and release on all terminal paths.
