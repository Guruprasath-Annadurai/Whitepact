# WHITEPACT M13-S4 DEFECT & RISK REGISTER (P0 / P1 / P2)

**Milestone:** M13-S4 — Defect Accounting & Risk Tracking  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Production Gate:** **GLOBAL NO-GO**  
**Review Gate:** Mandatory Independent Codex Retest

---

## 1. P0 Priority Defect Register (Release-Blocking)

| ID | Title / Vulnerability Description | Initial Status | M13-S4 Status | Remediation & Verification Proof |
| :--- | :--- | :--- | :--- | :--- |
| **P0-A** | **Atomic WebAuthn Replay Under Concurrency**<br>Concurrent transactions could double-spend zero-counter WebAuthn assertions due to non-atomic read-modify-write patterns. | OPEN | **CLOSED / PROVEN** | Implemented single-winner conditional `UPDATE` on `authority_step_up_challenges` within the exact same PostgreSQL transaction as operation mutation. Verified by `test_concurrent_assertion_probe.py`. |
| **P0-B** | **Non-Durable Containment & False Positive Status**<br>Process termination failures could report `status = 'CONTAINED'` or crash mid-flight without a persistent incident audit record. | OPEN | **CLOSED / PROVEN** | Pre-termination durable commitment pattern writes `TERMINATION_PENDING` before external process I/O. Partial failures report `PARTIALLY_FAILED` / `UNRESOLVED`. Verified by `test_durable_crash_probe.py`. |
| **P0-C** | **Static Quorum Admin Deactivation Regression**<br>Recovery requests evaluated approver roles only at vote time, allowing demoted or suspended admins to push quorum across threshold at execution. | OPEN | **CLOSED / PROVEN** | Implemented dynamic pre-execution membership and role recheck immediately before recovery execution. Anti-self-approval enforced. Verified by `test_m13r3_security_regression.py`. |
| **P0-D** | **WebAuthn Dual-Path Policy Bypass (WP-M13-POL-002)**<br>Break-glass or single-use ticket reuse could bypass fresh WebAuthn step-up on consequential recovery actions. | OPEN | **CLOSED / PROVEN** | Path A (fresh assertion) and Path B (single-use pre-verified ticket) enforce strict tenant, session, credential, operation, and digest binding. Ticket reuse prevented via atomic DB consumption. Scope restricted. |
| **P0-E** | **Distributed Containment Tracking Ambiguity**<br>Empty local tracking registry on one worker node was treated as confirmation of physical execution termination across a cluster. | OPEN | **CLOSED / PROVEN** | Cross-worker execution tracking explicitly returns `UNRESOLVED` when an execution ID is absent from local worker registry. Verified by `test_cross_worker_tracking_probe.py`. |

---

## 2. P1 Priority Defect Register (Hardening & Reliability)

| ID | Title / Description | Status | Target Milestone | Assessment & Disposition |
| :--- | :--- | :--- | :--- | :--- |
| **P1-01** | **WebAuthn Path B Ticket Lifetime Duration**<br>Current default validity window is 300 seconds (5 minutes). | **FLAGGED FOR FOUNDER** | M13-R4 / M14 | Antigravity recommends founder policy reduction to 120 seconds to limit exposure window of unconsumed tickets. |
| **P1-02** | **Native Linux Container Host Qualification**<br>Direct kernel-level UID 65534 mapping and cgroups v2 limits require native Linux kernel. | **OPEN (ENVIRONMENT GATE)** | M14 CI Pipeline | macOS development runs correctly record `QUALIFICATION_SKIP`; final Linux qualification requires Ubuntu 24.04 bare-metal runner. |
| **P1-03** | **Linear Hash Chain vs. Merkle Witness Spec Parity**<br>SPEC.md conceptual references to "Merkle proofs" vs. actual linear SHA-256 hash chain implementation. | **RECONCILED IN DOCS** | M13-S4 | Truthfully documented in `WHITEPACT_M13S4_EVIDENCE_AND_AUDIT.md`; linear hash chain certified; Merkle claims explicitly disclaimed. |

---

## 3. P2 Priority Defect Register (Quality & Ergonomics)

| ID | Title / Description | Status | Target Milestone | Assessment & Disposition |
| :--- | :--- | :--- | :--- | :--- |
| **P2-01** | **Pytest Pyproject Coverage Overhead**<br>Global `--cov` flag causes single test file invocations to compute full-tree branch coverage taking 45s+. | **MITIGATED IN CLI** | M14 | Targeted runs use `-o addopts=""` for sub-second execution while preserving full coverage in CI matrix. |
| **P2-02** | **Frontend CanonicalPanels Dashboard Synchronization**<br>Codex product workspace contains pending UI integration for recovery and containment views. | **HANDOFF TO CODEX** | M13-P3 | Security API contracts published in `WHITEPACT_M13S4_SECURITY_API_CONTRACT.md` for seamless frontend binding. |

---

## 4. Production Gate Conditions

WhitePact maintains a **GLOBAL NO-GO** for production release. Acceptance of M13-S4 security engineering is conditioned upon:
1. All P0 defects remaining closed with zero regressions across the 36-test suite.
2. Independent Codex review and verification of branch `security/whitepact-m13s4-security`.
3. Founder ratification of ticket lifetime policy (WP-M13-POL-002).
4. CI execution on native Linux runners for container isolation suites.
