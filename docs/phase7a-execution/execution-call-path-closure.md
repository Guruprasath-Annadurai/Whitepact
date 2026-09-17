# WhitePact Phase 7A: Execution Call-Path and Single-Admission Closure

**Document Status:** CANONICAL SPECIFICATION PASS 4.1 (SECURITY CONSISTENCY REMEDIATION)
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
2. **Direct Executor Bypass & Replayability (4.1-F03):**
   - Production executor call sites:
     - `src/responsibleai/governance/execution.py:334` (`InternalToolExecutor.execute`)
     - `src/responsibleai/governance/upstream_executor.py:226` (`UpstreamMCPExecutor.execute`)
   - An `AdmissionReceipt` is NOT accepted by downstream executors.
   - Workers must call `claim_backend_start()` to acquire a `BackendExecutionClaim`.
   - Downstream executors require `BackendExecutionClaim` and call `assert_backend_start_claim(claim)` against PostgreSQL before container or socket invocation.
3. **Execution Scope Ambiguity (Hosted vs Community-Local):**
   - Self-hosted stdio transport contains a direct `dispatch_tool()` path that does not invoke hosted governance.
   - Hosted mode enforces `HOSTED_GOVERNANCE_STRICT = True`, rejecting direct un-governed tool execution with HTTP 403 Forbidden.

---

## 2. Production Call-Path Inventory & Tracing

### 2.1 Complete Production Call Paths

| Call Path | Execution Scope | Entry Point | `authorize_execution` Owner | Durable Issuance Owner | Queueing Owner | Worker Owner | `admit_execution` Owner | Backend Start Owner | Downstream Executor | Evidence Owner |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Path 1: Governed Local Tool** | HOSTED GOVERNED | `execute_governed_action` in `mcp/governance_integration.py` | `governance_integration.py:468` | `DurableExecutionAuthorizationIssuer.issue` (Mig 0049/0050) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution`) | `ExecutionAttemptRepository.claim_backend_start` | `InternalToolExecutor.execute(action, claim)` | `EvidenceStore` + `AuditLedger` |
| **Path 2: Approval Local Tool** | HOSTED GOVERNED | `resolve_approval_and_execute` in `mcp/governance_integration.py` | `governance_integration.py:816` | `ApprovalExecutionService.consume_and_issue` (Atomic TX) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution`) | `ExecutionAttemptRepository.claim_backend_start` | `InternalToolExecutor.execute(action, claim)` | `EvidenceStore` + `AuditLedger` |
| **Path 3: Upstream MCP Dispatch** | HOSTED GOVERNED | `dispatch_upstream_action` in `mcp/upstream_dispatch.py` | `upstream_dispatch.py:322` | `DurableExecutionAuthorizationIssuer.issue` (Mig 0049/0050) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution`) | `ExecutionAttemptRepository.claim_backend_start` | `UpstreamMCPExecutor.execute(action, claim, target)` | `EvidenceStore` + `AuditLedger` |
| **Path 4: Approval Upstream MCP** | HOSTED GOVERNED | `resolve_approval_and_execute` with upstream target | `governance_integration.py:816` | `ApprovalExecutionService.consume_and_issue` (Atomic TX) | `AdmissionController` + `FairExecutionScheduler` | `ResponsibleWorker` | `ResponsibleWorker` (`admit_execution`) | `ExecutionAttemptRepository.claim_backend_start` | `UpstreamMCPExecutor.execute(action, claim, target)` | `EvidenceStore` + `AuditLedger` |
| **Path 5: Hosted MCP `_call_tool`** | HOSTED GOVERNED | `server.py:_call_tool` (with hosted context) | Routed to `apply_governance()` -> Path 1/2/3/4 | Routes through centralized issuer | Routes through worker queue | `ResponsibleWorker` | `ResponsibleWorker` | `ExecutionAttemptRepository.claim_backend_start` | Routed to `InternalToolExecutor` or `UpstreamMCPExecutor` | `EvidenceStore` |
| **Path 6: Community Local stdio** | EXPLICIT NON-HOSTED LOCAL MODE | `server.py:_call_tool` (without hosted context) | None (Community mode) | None | None | None | None | None | Direct `dispatch_tool(name, args)` | None (Local stdio only) |
| **Path 7: Subprocess Isolation** | EXPLICIT NON-HOSTED LOCAL MODE | `isolation/subprocess_backend.py` | Development / local test only | None | None | None | None | None | Local host subprocess | None (Forbidden in hosted) |

---

## 3. Explicit Deployment & Scope Classification

### 3.1 Hosted / Enterprise Governed Mode
In hosted cloud, SaaS, and enterprise on-premise deployments:
- **Mandatory Invariant:** ALL consequential execution MUST pass through the complete chain:
  `runtime_execution_requests` -> `governance_execution_authorizations` -> `FairExecutionScheduler` -> `runtime_worker_leases` (fencing generation) -> preflight revalidation -> canonical `admit_execution()` -> `claim_backend_start()` -> `assert_backend_start_claim()` -> `ContainerIsolationBackend` (`--network=none`, limits) OR `UpstreamMCPExecutor` (`SafeNetworkBackend`) -> `EvidenceStore`.
- **Direct Dispatch Prohibition:** In hosted configuration, `server.py` checks `config.HOSTED_GOVERNANCE_STRICT == True`. If no governance context is present, the request fails closed immediately with HTTP 403 Forbidden. Direct `dispatch_tool()` is completely unreachable.

### 3.2 Community Local / Self-Hosted Direct Mode
- WhitePact supports a local single-user CLI mode over stdio where tools execute directly on the developer's laptop.
- **Explicit Trust Boundary:** Community local direct mode is a separate, non-governed deployment profile.
- **Enterprise Security Claims:** All enterprise security guarantees (auditability, non-repudiation, policy enforcement, container isolation, worker fencing) strictly apply to **Hosted Governed Mode** and explicitly exclude Community Local Direct Mode.

---

## 4. Centralized Durable Issuance Architecture

### 4.1 Principle: Non-Bypassable Durable Issuance
All 3 production `authorize_execution()` call sites route through `DurableExecutionAuthorizationIssuer.issue()`:

```python
class DurableExecutionAuthorizationIssuer:
    """Centralized durable issuer for ExecutionAuthorizations.
    Guarantees that `runtime_execution_requests`, `governance_execution_authorizations`,
    initial `runtime_execution_attempts` (PENDING), and `runtime_execution_fences`
    are durably committed to PostgreSQL in ONE transaction before handing to the
    admission controller or queue.
    """
    def __init__(
        self,
        request_repo: ExecutionRequestRepository,
        auth_repo: ExecutionAuthorizationRepository,
        attempt_repo: ExecutionAttemptRepository,
        fence_repo: ExecutionFenceRepository,
    ) -> None:
        self._request_repo = request_repo
        self._auth_repo = auth_repo
        self._attempt_repo = attempt_repo
        self._fence_repo = fence_repo

    async def issue(
        self,
        authorization: ExecutionAuthorization,
        action: ActionRequest,
        idempotency_key: str,
    ) -> ExecutionAuthorization:
        if authorization.decision not in (
            GovernanceDecision.ALLOW,
            GovernanceDecision.ALLOW_WITH_REDACTION,
        ):
            raise InvalidAuthorizationStateError(
                f"Cannot issue authorization with decision {authorization.decision}"
            )

        # Single PostgreSQL transaction: request + authorization + initial attempt + fence
        async with self._request_repo.transaction() as tx:
            await self._request_repo.create(action, idempotency_key=idempotency_key, tx=tx)
            await self._auth_repo.create(authorization, tx=tx)
            await self._attempt_repo.create_initial_attempt(
                execution_id=action.action_id,
                authorization_id=authorization.authorization_id,
                org_id=action.agent.organization_id,
                tx=tx,
            )
            await self._fence_repo.create_fence(execution_id=action.action_id, tx=tx)
        return authorization
```

---

## 5. Executor Signatures & Durable Claim Verification (4.1-F03)

Executors do NOT accept `AdmissionReceipt`. They require `BackendExecutionClaim`:

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

    # 2. Durable state verification against PostgreSQL
    await self._attempt_repo.assert_backend_start_claim(claim)

    # 3. Transition to RUNNING and invoke container
    await self._attempt_repo.mark_running(claim.attempt_id)
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

    # 2. Durable state verification against PostgreSQL
    await self._attempt_repo.assert_backend_start_claim(claim)

    # 3. Target verification & IP Pinning via SafeNetworkBackend
    resolved_ip = await self._safe_network.validate_target_and_resolve_ip(target)
    if claim.target_fingerprint:
        check_target_fingerprint(claim, compute_upstream_target_fingerprint(target))

    # 4. Durable transition to EFFECT_TRANSMITTING immediately pre-socket
    await self._attempt_repo.mark_transmitting(claim.attempt_id)

    # 5. Socket transmission with stable effect_id
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
5. Canonical admission transaction combining nonce insert and authorization status update (`rowcount == 1`).
6. Universal epoch invalidation covering all 14 authority mutations.
7. Monotonic worker fencing (`0052_runtime_worker_leases` & `runtime_execution_fences`).
8. Durable attempt and effect state machine (`0051_runtime_execution_attempts`).
9. One-shot backend-start claim (`claim_backend_start` with `rowcount == 1` returning `BackendExecutionClaim`).
10. Downstream executor verification (`assert_backend_start_claim`) closing direct bypass.
11. Target resolution and IP pinning in `SafeNetworkBackend`.
12. Synchronous lease expiry checking in backend-start fence.
13. Complete append-only request immutability trigger.
14. Universal capacity reservation and release on all terminal paths.
15. Preservation of `SafeNetworkBackend` and container isolation.
