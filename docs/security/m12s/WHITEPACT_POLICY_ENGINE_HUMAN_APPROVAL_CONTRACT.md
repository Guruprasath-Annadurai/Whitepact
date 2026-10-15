# WHITEPACT — POLICY ENGINE & HUMAN APPROVAL CONTRACTS

**Document ID:** WP-M12S-POLICY-006  
**Classification:** NORMATIVE SPECIFICATION & SECURITY CONTRACT  
**Audience:** Codex Engine Integrators, Dashboard Developers, Security Auditors  
**Modules:** `responsibleai.governance.policy`, `responsibleai.governance.approval`, `responsibleai.db.approval_repository`  
**Status:** IMPLEMENTED & AUDITED

---

## 1. TAXONOMY OF GOVERNANCE EFFECTS VS. POLICY DECISIONS

Codex M11 identified potential ambiguity between ordered policy-rule evaluations and canonical governance verdicts. WhitePact enforces a strict hierarchy:

```
[Agent ActionRequest]
         |
         v
+-----------------------------------------------------------+
| 1. Authority Resolver (Identity, Root, Consent, Chain)    |  --> DENY if outside authority
+-----------------------------------------------------------+
         |
         v
+-----------------------------------------------------------+
| 2. Policy Rule Evaluation (Ordered Rules & Pattern Match) |
|    - DENY rules take precedence                           |
|    - QUARANTINE rules isolate runaway agents              |
|    - REDACT rules sanitize sensitive payload arguments   |
|    - REQUIRE_APPROVAL rules mandate human intervention     |
|    - ALLOW permits execution if all checks pass           |
+-----------------------------------------------------------+
         |
         v
+-----------------------------------------------------------+
| 3. Risk Assessment (Risk Tier: MINIMAL, LOW, MED, HIGH)   |
|    - HIGH Risk enforces 2-human distinct quorum           |
+-----------------------------------------------------------+
         |
         v
+-----------------------------------------------------------+
| 4. Canonical Governance Decision                          |
|    (ALLOW | ALLOW_WITH_REDACTION | REQUIRE_APPROVAL |      |
|     DENY | QUARANTINE)                                    |
+-----------------------------------------------------------+
```

### Hierarchy of Precedence:
$$\text{QUARANTINE} > \text{DENY} > \text{REQUIRE\_APPROVAL} > \text{ALLOW\_WITH\_REDACTION} > \text{ALLOW}$$

Under no circumstances can an `ALLOW` rule override an authority denial or an upstream security constraint.

---

## 2. HUMAN APPROVAL CONTRACT & INVARIANTS

When a decision results in `REQUIRE_APPROVAL`, an `ApprovalRequest` is persisted to `governance_approvals`.

### Invariant 1: Multi-Approver Distinct-Human Quorum
- Actions classified under `RiskTier.HIGH` mandate a quorum of **two distinct human approvals** (`required_approvals = 2`).
- Each vote is recorded in `governance_approval_votes`.
- The approval transitions from `PENDING` to `APPROVED` only when the number of unique approving identities equals or exceeds `required_approvals`.
- **Asymmetric Veto:** A single `DENIED` vote immediately vetoes and closes the approval as `DENIED`, regardless of pending or affirmative votes.

### Invariant 2: Self-Approval Prevention
- The identity that proposed or initiated the action (`requested_by`) cannot approve its own request.
- Attempting self-approval raises `SelfApprovalError(approval_id, resolved_by)`. This check is enforced in the database kernel, independent of any UI or API role checks.

### Invariant 3: Single Vote per Identity (Replay Guard)
- A single user identity can cast at most one vote per approval.
- Enforced by PostgreSQL unique constraint: `UNIQUE (approval_id, resolver_identity_id)`. Concurrent duplicate votes raise `AlreadyVotedError`.

### Invariant 4: Exact-Action SHA-256 Digest Binding
- At creation time, the server computes `action_digest`:
  $$\text{SHA-256}(\text{canonical\_json}(\text{org\_id}, \text{principal\_id}, \text{action\_type}, \text{target}, \text{arguments}, \text{purpose}))$$
- When the approved action is subsequently presented for execution, `matches_action()` verifies that the presented action is byte-identical to what was approved.
- Any modification of arguments (e.g., changing payment amount from $10 to $1,000) causes an immediate rejection with `ApprovalActionMismatchError`.

### Invariant 5: Exactly-Once Execution (Consumption Guard)
- Resolving an approval to `APPROVED` does not execute it.
- When execution resumes, `ApprovalRepository.consume()` atomically transitions status from `APPROVED` to `CONSUMED`.
- Attempting to replay an already executed approval raises `ApprovalNotApprovedError("status=CONSUMED")`.

### Invariant 6: Temporal Expiry
- Approvals have a default TTL of 24 hours (`DEFAULT_APPROVAL_TTL_HOURS`).
- An expired approval cannot be voted on or consumed; raises `ApprovalExpiredError`.

### Invariant 7: Revocation Invalidation Between Approval & Execution
- If an agent's delegation or the customer's root authority is revoked while an approval is pending or after it has been approved:
  - The revocation increments `revocation_epoch`.
  - When the caller attempts to execute via `InternalToolExecutor`, `admit_execution` verifies `authorization.revocation_epoch == current_epoch`.
  - Execution fails closed with `ExecutionNotAuthorizedError`.

---

## 3. NEGATIVE FIXTURES & TEST MATRICES FOR CODEX

Codex product integrations should validate against the following negative test cases:

```python
# Fixture 1: Self-Approval Attempt
approval = await approvals.create_from_decision(action, require_approval_decision)
with pytest.raises(SelfApprovalError):
    await approvals.resolve(approval.approval_id, resolved_by=action.agent.identity.identity_id, outcome=ApprovalStatus.APPROVED)

# Fixture 2: Argument Tampering Between Approval and Consumption
approval = await approvals.resolve(approval.approval_id, resolved_by="human_approver_1", outcome=ApprovalStatus.APPROVED)
tampered_action = replace(action, arguments={"amount": 999999})
with pytest.raises(ApprovalActionMismatchError):
    await approvals.consume(approval.approval_id, tampered_action)

# Fixture 3: Replay After Consumption
await approvals.consume(approval.approval_id, action)
with pytest.raises(ApprovalNotApprovedError):
    await approvals.consume(approval.approval_id, action)  # Second execution fails closed
```
