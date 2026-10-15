# WHITEPACT — CONSEQUENTIAL EXECUTION ENFORCEMENT MATRIX

**Document ID:** WP-M12S-EXEC-007  
**Classification:** RUNTIME ENFORCEMENT MATRIX & AUDIT  
**Audience:** Security Architects, Runtime Engineers, Integration Leads  
**Modules:** `responsibleai.governance.execution`, `responsibleai.governance.upstream_executor`, `responsibleai.mcp.server`, `responsibleai.isolation.broker`  
**Status:** QUALIFIED

---

## 1. EXECUTIVE OVERVIEW

WhitePact's execution architecture ensures that no consequential tool, API call, or containerized command can execute without independently verified runtime authority.

### The Enforcement Chain:
$$\text{Authenticated Context} \longrightarrow \text{Canonical Authority} \longrightarrow \text{Policy \& Risk Evaluation} \longrightarrow \text{Single-Use Nonce Admission} \longrightarrow \text{Isolated Execution} \longrightarrow \text{Evidence Logging}$$

---

## 2. DISPATCHER ENFORCEMENT COVERAGE MATRIX

| Dispatcher Path | Tenant Scoped | Consent Verified | Capability Lattice | Policy Checked | Risk Tiered | Approval Quorum | Short-Lived Token | Single-Use Nonce | Target Drift Guard | Isolation Bound | Tamper-Proof Evidence | Conservative UNKNOWN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`InternalToolExecutor`** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** (30s) | **YES** | N/A (Internal) | **YES** (OCI/Broker) | **YES** | **YES** |
| **`UpstreamMCPExecutor`** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** (30s) | **YES** | **YES** (Fingerprint) | **YES** | **YES** | **YES** |
| **MCP stdio Transport** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | N/A | **YES** | **YES** | **YES** |
| **MCP HTTP Transport** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **CrewAI Consumer** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **LangChain Consumer** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **LlamaIndex Consumer** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** | **YES** |
| **Webhooks Gateway** | **YES** | N/A | N/A | **YES** | N/A | N/A | **YES** (HMAC) | **YES** | **YES** | N/A | **YES** | **YES** |

---

## 3. KEY ENFORCEMENT INVARIANTS

### 1. Single-Use Nonce Admission (`admit_execution`)
- Every `ExecutionAuthorization` carries a unique cryptographic nonce (`uuid.uuid4().hex`) and the tenant's current `revocation_epoch`.
- When presented to an executor, `admit_execution()` calls `ExecutionNonceRepository.consume(nonce, expected_epoch)`.
- If the nonce was already used (replay), or if the database's epoch has incremented (revocation), execution is refused immediately with `ExecutionNotAuthorizedError`.

### 2. Execution Permit v2 Target Fingerprint Drift Protection
- Upstream MCP servers can experience configuration drift between evaluation time and execution time (e.g., DNS repoint, credential rollover, or tool definition changes).
- At evaluation time, `compute_upstream_target_fingerprint()` computes an SHA-256 fingerprint over the server's resolved endpoint, TLS certificate pin, and tool schema.
- At consumption time, `check_target_fingerprint()` recomputes the fingerprint from live state. Any drift raises `AuthorizationTargetDriftError` and halts dispatch.

### 3. Backup Defense & Readiness Chokepoint
- Before executing any consequential tool, `InternalToolExecutor` calls `assert_restore_readiness_admitted()`.
- If disaster recovery procedures, point-in-time recovery archives, or audit pipelines are degraded, destructive or mutating executions fail closed.

### 4. Conservative UNKNOWN External-Effect Handling
- If a network partition or socket timeout occurs after an external tool has been invoked (HTTP 504, TCP RST, or broker timeout), WhitePact treats the outcome as **UNKNOWN**.
- Nonce consumption remains committed (preventing automated blind retries).
- The action is marked with reason code `REASON_EXECUTION_UNKNOWN` and queued for manual human reconciliation rather than assumed to have failed or succeeded.
