# WHITEPACT — M12-SR OPEN DEFECT & RESIDUAL RISK REGISTER
## FORMAL TRACKING OF RESIDUAL ITEMS, POLICY GATES & DEFERRED ENHANCEMENTS

- **Author:** Antigravity (Principal Security Architect)
- **Review Milestone:** M12-SR
- **Release Gate Impact:** **GLOBAL PRODUCTION NO-GO (Strictly Enforced)**
- **Total Open Defects / Governance Blocks:** 5

---

## 1. DEFECT CLASSIFICATION & RISK MATRIX

| Defect ID | Title & Subsystem | Severity | Impact on Local Dev | Impact on Production | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-M12SR-01** | Founder Decision A: Production Root WebAuthn Assurance Pending | **HIGH** | None (Local dev uses session auth) | **BLOCKING (Gate S12)** | Open (Awaiting Founder Sign-off) |
| **DEF-M12SR-02** | Founder Decision B: Multi-Admin Quorum Root Recovery Pending | **HIGH** | None (Single owner permitted in test) | **BLOCKING (Gate S12)** | Open (Awaiting Founder Sign-off) |
| **DEF-M12SR-03** | Feature Registry Entry #87: Merkle Evidence Missing | **MEDIUM** | None (Hash-chain witness log active) | Non-blocking (Marketing disclaimer mandated) | Open (Remediated via Registry Disclaimer) |
| **DEF-M12SR-04** | Deprecation of Legacy Static `RAI_API_KEYS` | **LOW** | None (Emits warning in test preflight) | Non-blocking (Restricted to non-owner role) | Open (Slated for M13 Removal) |
| **DEF-M12SR-05** | Native Linux Cgroups/Namespaces on Non-Linux Hosts | **LOW** | None (Graceful fallback to sandboxed subprocess) | Non-blocking (Production Linux containers supported) | Documented Invariant |

---

## 2. DETAILED DEFECT ENTRIES

### DEF-M12SR-01: Founder Security Decision A Pending
- **Component:** `CustomerAuthorityService`, `WebIdentityRepository`
- **Description:** Establishing canonical customer root authority in production requires formal founder approval to mandate phishing-resistant WebAuthn / Passkey hardware step-up credentials. Email-verified sessions are insufficient for high-assurance enterprise deployments.
- **Risk Evaluation:** High. Compromised owner passwords could allow unauthorized root authority bootstrap in production environments without hardware MFA.
- **Remediation Action:** Founders must sign `docs/security/m12sr/WHITEPACT_FOUNDER_SECURITY_DECISIONS.md`.
- **Target Resolution:** Prior to M13 Production Qualification.

---

### DEF-M12SR-02: Founder Security Decision B Pending
- **Component:** `CustomerAuthorityService`, `EnterpriseIAM`
- **Description:** Recovery and re-issuance of revoked canonical root authority currently allows unilateral action by any single owner. High-assurance tenants require M-of-N multi-admin quorum for root re-issuance.
- **Risk Evaluation:** High. Rogue or compromised single owner can replace root authority unilaterally.
- **Remediation Action:** Founders must sign `docs/security/m12sr/WHITEPACT_FOUNDER_SECURITY_DECISIONS.md`.
- **Target Resolution:** Prior to M13 Production Qualification.

---

### DEF-M12SR-03: Feature Registry Entry #87 (Merkle Evidence)
- **Component:** `docs/m12/feature-registry.json`, `responsibleai.governance.evidence`
- **Description:** Historical materials referred to "Merkle evidence structures". Forensic audit confirmed the repository implements linear SHA-256 hash chaining and Ed25519 digital signatures, but not Merkle tree inclusion proofs.
- **Risk Evaluation:** Medium. Reputational/marketing risk if false claims of Merkle trees are made. Technical risk is zero because the linear hash chain is cryptographically sound.
- **Remediation Action:** Registry entry #87 has been updated with explicit limitation. Marketing claims of Merkle trees are prohibited. RFC for true Merkle tree DAG scheduled for M13.
- **Target Resolution:** Milestone M13.

---

### DEF-M12SR-04: Legacy Static `RAI_API_KEYS` Deprecation
- **Component:** `src/responsibleai/enterprise/preflight.py`
- **Description:** Legacy static API keys passed via environment variable `RAI_API_KEYS` emit a `DeprecationWarning`. They are permanently restricted to non-production scope and cannot issue enterprise credentials or root authority.
- **Risk Evaluation:** Low. Fail-closed guards prevent static keys from accessing enterprise root surfaces.
- **Remediation Action:** Fully excise `RAI_API_KEYS` in Milestone M13 in favor of `EnterpriseIAM.issue_api_key()`.
- **Target Resolution:** Milestone M13.

---

### DEF-M12SR-05: Non-Linux Host Fallback for Container Containment
- **Component:** `src/responsibleai/sandbox/linux_containment.py`
- **Description:** When running tests on macOS (Darwin), Linux namespaces and cgroups v2 are unavailable. The containment layer falls back to restricted subprocess sandboxing.
- **Risk Evaluation:** Low for production (production workloads target Linux kernel hosts with full namespace support).
- **Remediation Action:** Enforce host platform verification during production Kubernetes/container initialization.
- **Target Resolution:** Milestone M13 Infrastructure Integration.

---

## 3. CONCLUSION

No open defect compromises the fail-closed security invariants of the codebase. The two high-severity governance items (DEF-01 and DEF-02) are cleanly gated by **Release Gate S12** and **GLOBAL PRODUCTION NO-GO**.
