# WHITEPACT — SECURITY ARCHITECTURAL DECISION RECORDS (ADRS)

**Document ID:** WP-M12S-ADR-014  
**Classification:** ARCHITECTURAL DECISION RECORDS (ADRs)  
**Date:** 2026-10-15  
**Audience:** All WhitePact Architects & Engineering Leads  
**Status:** **APPROVED & RECORDED**

---

## ADR-M12S-001: Server-Enforced Replay-Resistant Customer Root Authority Ceremony

### Context:
Prior to M12-S, internal repositories held records for root authority and consent, but there was no authenticated customer-facing onboarding journey to establish them. Organizations were created without explicit customer consent, relying on SQL seeding or internal fixture shortcuts.

### Decision:
Implement a 2-step owner bootstrap ceremony in `CustomerAuthorityService`:
1. `initiate_root_bootstrap`: Verifies caller is `Role.OWNER` in tenant `org_id`, issues a 32-byte URL-safe token and 16-byte hex nonce with a 900-second TTL, persisted with its SHA-256 hash.
2. `complete_root_bootstrap`: Atomically verifies token hash, nonce, and actor identity, marks record consumed, writes Trust Fabric root, mints canonical `RootAuthorityRecord` and `ConsentProof`, and records immutable audit log.

### Consequences:
- Positive: No client can manufacture root authority; replay attacks are impossible; tenant isolation is strictly enforced.
- Negative: Requires customer owner to complete an explicit ceremony before agents can be granted execution rights.

---

## ADR-M12S-002: Concurrency Control Without Revocation Epoch Drift (P0-08 Fix)

### Context:
Previously, `DelegationRepository.grant()` called `bump_epoch_on_connection()`, advancing `revocation_epoch` on every additive grant. This caused all previously issued, valid execution authorizations across the organization to become invalid instantly, inducing high failure rates and cache invalidation storms.

### Decision:
Preserve and enforce the P0-08 fix:
- Ordinary additive grants call `await lock_epoch(conn, org_id)` (`SELECT epoch ... FOR UPDATE`), serializing concurrent writers and preventing graph cycles without changing the epoch number.
- Revocation operations (`revoke_branch()`) continue to call `await bump_epoch_on_connection(conn, org_id)`, incrementing the epoch counter.

### Consequences:
- Positive: Eliminates false cache invalidation; in-flight jobs for unaffected agents run smoothly; concurrency safety is maintained.
- Verified by: `tests/test_delegation_revocation_verification.py` (4/4 passing on PostgreSQL 16).

---

## ADR-M12S-003: Single Unified Governance Bridge from Trust Fabric

### Context:
Codex M11 audit reported two disconnected authority subsystems: Trust Fabric and Canonical Governance. Maintaining two authority kernels creates security-critical synchronization gaps.

### Decision:
Unify all customer authority issuance in `CustomerAuthorityService`. Do not build a second authority kernel. Every Trust Fabric trust root update atomically mints a canonical `RootAuthorityRecord` and `ConsentProof` under the same transaction.

### Consequences:
- Positive: Single source of truth for runtime authority; `AuthorityResolver` remains the sole authority evaluation kernel.
- Negative: All agent delegation flows must route through `CustomerAuthorityService`.

---

## ADR-M12S-004: Invariant Separation of Registration from Execution Authority

### Context:
Common API patterns equate creating an agent with giving it permissions. In an autonomous enterprise system, an unattenuated agent creates extreme risk of prompt-injection escalation.

### Decision:
Enforce the invariant: **Registration != Authority**.
- Agent registration via `POST .../agents` provisions the agent in `trust_fabric_principals` with `"has_delegated_authority": false`.
- Any execution attempt by a newly registered agent raises `AuthorityDenied("DELEGATION_INVALID")`.
- Execution is permitted only after an explicit, attenuated delegation is granted via `POST .../delegations`.

### Consequences:
- Positive: Prevents unauthorized agent execution by design; satisfies the primary constitutional directive.
- Negative: Requires an extra onboarding step (delegation assignment) in the customer workflow.

---

## ADR-M12S-005: Multi-Approver Distinct-Human Quorum and Asymmetric Veto

### Context:
High-risk agent actions (such as wire transfers or data deletion) cannot safely rely on a single human approver. Furthermore, an agent or user might attempt to approve their own request.

### Decision:
Enforce in `ApprovalRepository`:
1. `RiskTier.HIGH` requires two distinct human approvals (`required_approvals = 2`).
2. Self-approval is strictly prohibited (`SelfApprovalError`).
3. Asymmetric Veto: Any single `DENIED` vote immediately vetoes and terminates the approval.
4. Quorum votes are tracked per unique user identity in `governance_approval_votes`.

### Consequences:
- Positive: Eliminates insider threat and rogue agent self-approval; adheres to two-man rule for high-risk operations.

---

## ADR-M12S-006: Nonce-Based Single-Use Execution Admission

### Context:
Allowing an `ExecutionAuthorization` to be reused creates replay vulnerabilities, where an agent or intercepted token can repeat actions multiple times.

### Decision:
Incorporate single-use cryptographic nonces into `ExecutionAuthorization` and enforce consumption via `admit_execution()` and `ExecutionNonceRepository`.
- Nonce consumption is recorded in PostgreSQL.
- Attempting to replay an authorization raises `AuthorizationAlreadyConsumedError`.
- Authorization must match current `revocation_epoch` at time of execution.

### Consequences:
- Positive: Guarantees single-use execution admission; prevents replay attacks.
