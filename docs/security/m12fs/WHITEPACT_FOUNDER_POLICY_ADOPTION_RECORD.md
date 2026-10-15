# WHITEPACT — FOUNDER POLICY ADOPTION RECORD (M12-FS)

**Document ID:** WP-M12FS-POL-001  
**Milestone:** M12-FS  
**Status:** FORMALLY ADOPTED & IMPLEMENTED  
**Classification:** Internal Core Security Policy  
**Release Gate:** GLOBAL PRODUCTION NO-GO  

---

## 1. Formal Founder Decisions Overview

In the M12-FS Master Security Directive, the Founder approved two critical architectural policy directions:

### Founder Decision A: Phishing-Resistant Step-Up
> *"Privileged root-authority establishment and high-risk authority changes require phishing-resistant passkey/WebAuthn step-up."*

### Founder Decision B: Asymmetric Containment vs. Recovery Quorum
> *"Properly authorized emergency containment may proceed without multi-admin quorum. High-assurance root transfer and recovery require multi-admin quorum."*

---

## 2. Policy Adoption Matrix & Technical Parameters

| Policy Decision | Target Operation | Required Assurance Factor | Quorum Threshold | Non-Expansion Rule | Enforcing Layer |
|---|---|---|---|---|---|
| **Decision A** | `COMPLETE_ROOT_BOOTSTRAP` | WebAuthn Level 3 (UV=1, UP=1) | N/A (1-of-1 Owner) | N/A | PostgreSQL + Kernel Service |
| **Decision A** | `ROOT_KEY_ROTATION` | WebAuthn Level 3 (UV=1, UP=1) | M-of-N Quorum (default 2-of-3) | Zero privilege increase | Quorum Engine + Kernel |
| **Decision A** | `ROOT_TRANSFER` | WebAuthn Level 3 (UV=1, UP=1) | M-of-N Quorum (default 2-of-3) | Zero privilege increase | Quorum Engine + Kernel |
| **Decision B** | `EMERGENCY_CONTAINMENT` (`AGENT`) | Owner / Admin credentials (+ optional WebAuthn) | 1-of-1 Single Admin | Strictly Non-Expanding | Immediate Epoch Bump |
| **Decision B** | `EMERGENCY_CONTAINMENT` (`LOCKDOWN`) | Owner / Admin credentials (+ optional WebAuthn) | 1-of-1 Single Admin | Strictly Non-Expanding | Tenant Lockdown + Epoch Bump |
| **Decision B** | `ROOT_RECOVERY` | Multi-Admin WebAuthn Assertions | M-of-N Quorum (M ≥ 2, N ≥ 3) | Bound to explicit proposal | Quorum Engine + Pre-Execution Membership Validation |

---

## 3. Constitutional Invariants Preserved

1. **Registration != Authority:** Merely signing up an organization, account, or agent never creates runtime execution authority.
2. **Asymmetric Security Thresholds:** Emergency containment is fast, unblocked, and fail-safe (single-admin kill switch); authority creation, transfer, and recovery are slow, multi-party, and heavily verified (M-of-N quorum + passkey step-up).
3. **Non-Expansion Invariant:** Emergency containment can ONLY reduce, suspend, quarantine, or revoke authority; under no circumstances can an emergency procedure grant new privileges or expand existing scopes.
4. **Anti-Self-Approval:** A recovery requester is structurally forbidden from voting to approve their own request (`SELF_APPROVAL_BLOCKED`).
5. **Fresh Membership Invariant:** Quorum approval is re-evaluated immediately prior to execution (`_scan_active_memberships`). If an approving administrator has been revoked, suspended, or demoted between the vote and execution, their vote is pruned and execution fails closed if the threshold is no longer met.
