# WHITEPACT M13-S4 CONSEQUENTIAL EXECUTION SECURITY & AUTHORITY CHAIN

**Milestone:** M13-S4 — Priority F Enforcement  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Status:** **AUDITED & FAIL-CLOSED ENFORCEMENT VERIFIED**

---

## 1. Canonical Fourteen-Link Authority Chain

WhitePact guarantees that no autonomous AI agent, tool call, or background task can execute consequential mutations on customer systems without traversing the unbroken 14-link authority chain:

```text
 1. Constitution    ──> Fundamental enterprise security constraints (SPEC.md)
 2. Identity        ──> Verified caller/agent credentials & tenant affiliation
 3. Authority       ──> Customer root bootstrap & active delegation lineage
 4. Intent          ──> Structured, declared action proposal and parameters
 5. Policy          ──> Customer-configured governance rules (OPA/Cedar/Rules)
 6. Capability Graph──> Reachable tool and resource boundary analysis
 7. Risk            ──> Tier classification (Tier 1: Read-Only to Tier 4: Consequential)
 8. Approval        ──> Human-in-the-loop / Quorum authorization requirements
 9. Judgment        ──> Multi-model consensus / deterministic policy evaluation
10. Execution Grant ──> Cryptographically bound, short-lived, single-use token
11. Isolated Exec   ──> Container / Sandboxed runner with zero ambient authority
12. Controlled Egress──> DNS-pinned, validated, non-private outbound network proxy
13. Evidence        ──> Append-only SHA-256 cryptographic hash-chained audit record
14. Revocation      ──> Epoch-based instantaneous revocation of future and active grants
```

If **ANY** single link in this chain fails or evaluates to an ambiguous/unknown state, the entire request **fails closed** immediately.

---

## 2. Dispatcher Admission & Single-Use Execution Grants

### Supported Execution Dispatchers:
1. **MCP (Model Context Protocol) Tools:** Streamable HTTP / stdio tool dispatchers. Every tool invocation requires an explicit execution grant bound to `(action_id, tool_name, tenant_id, nonce, epoch)`.
2. **Subprocess Runner:** Ephemeral workspace execution with restricted POSIX capabilities, resource limits, and non-root UID.
3. **Container Backend (Docker / Containerd):** Strict isolation profiles with read-only root filesystems, memory/CPU bounds, and dropped network access.

### Single-Use Grant Invariant:
- Every execution grant carries a unique cryptographic nonce (`execution_nonce_reference`).
- Upon execution admission, the nonce is atomically marked as spent in the state store.
- Replaying the same grant token or attempting concurrent executions with the same grant fails closed with `409 Conflict` / `replayed_authorization_rejected`.

---

## 3. Revocation Epochs & Stale Privilege Invalidation

WhitePact decouples authorization lifespans from static token expiration using **Tenant Revocation Epochs**:
- Each tenant organization maintains a monotonic integer `revocation_epoch` in PostgreSQL.
- Every short-lived execution grant records the tenant's current epoch at issuance time.
- When an emergency containment, administrator revocation, or passkey de-registration occurs, `bump_epoch_on_connection()` atomically increments the tenant's revocation epoch.
- When an in-flight or queued execution grant reaches an executor, the executor compares `grant.epoch` against `tenant.current_epoch`.
- If `grant.epoch < tenant.current_epoch`, the grant is immediately rejected as **stale**, terminating execution before any side-effect can occur.

---

## 4. Safe Handling of UNKNOWN & Ambiguous States

In probabilistic AI evaluations or network partitions:
- An AI safety evaluator or guardrail returning `UNKNOWN`, `TIMEOUT`, or an unparseable response **never** defaults to allow.
- WhitePact's policy engine translates `UNKNOWN` directly into a hard deny (`GovernanceDecision.DENY` with reason code `EVALUATION_AMBIGUOUS_FAIL_CLOSED`).
- Consequential execution retries on network timeout are strictly forbidden without re-authorization, preventing duplicate mutation side effects.

---

## 5. Test & Enforcement Evidence

The complete consequential execution chain has been verified across multiple adversarial suites:
- `tests/test_isolation_egress_boundary.py::test_execution_boundary_unauthorized_action_rejected` **PASSED**
- `tests/test_isolation_egress_boundary.py::test_execution_boundary_stale_authorization_rejected` **PASSED**
- `tests/test_isolation_egress_boundary.py::test_execution_boundary_replayed_authorization_rejected` **PASSED**
- `tests/test_isolation_egress_boundary.py::test_cross_phase_isolation_egress_end_to_end_chain` **PASSED**
- `tests/test_isolation_fail_closed_default.py` **PASSED**
- `tests/test_m5_unknown_outcome_regression.py` **PASSED**
