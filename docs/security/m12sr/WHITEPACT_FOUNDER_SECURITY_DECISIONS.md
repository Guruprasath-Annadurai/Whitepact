# WHITEPACT — FOUNDER SECURITY DECISION RECORD
## PRODUCTION ROOT ASSURANCE & EMERGENCY REVOCATION POLICIES

- **Status:** **PENDING FOUNDER APPROVAL (RELEASE GATE S12 LOCKED)**
- **Author:** Antigravity (Principal Security Architect)
- **Coordinator:** GPT-6 (WhitePact CTO)
- **Applicability:** Milestone M12-SR / Milestone M13 Production Qualification
- **Current Gate State:** **GLOBAL PRODUCTION NO-GO**

---

## CONTEXT & OBJECTIVE

WhitePact's constitutional governance model dictates that all downstream agent actions depend upon the cryptographic and legal validity of the customer root authority.

While the two-step ceremony implemented in M12-SR provides cryptographic single-use nonces, anti-replay, and temporal bounds, activating production customer workspaces requires founder resolution on two fundamental trust and governance decisions.

---

## DECISION RECORD A: PRODUCTION ROOT ASSURANCE

### The Problem
Can simple email-verified browser sessions (username/password cookies) be permitted to mint and modify the organization's canonical root authority in production? Or must production workspaces mandate phishing-resistant hardware credentials (WebAuthn / Passkeys / FIDO2) or qualified enterprise federation (OIDC / SAML with MFA)?

### Option Comparison

| Option | Security Assurance | Operational Friction | Phishing Resistance | Enterprise IdP Dependency |
| :--- | :--- | :--- | :--- | :--- |
| **Option A1 (Status Quo)**: Password + Email Verification Only | **LOW** | Lowest (Standard web signup) | **NONE** (Vulnerable to phishing & credential stuffing) | None |
| **Option A2 (Recommended Default)**: Mandatory WebAuthn / Passkey Hardware Step-Up | **VERY HIGH** | Low (TouchID / FaceID / YubiKey biometric prompt) | **ABSOLUTE** (Cryptographically bound to origin) | None (Self-contained browser API) |
| **Option A3**: Enterprise IdP Federation Only (SAML/Okta/Azure AD) | **HIGH** | High (Requires IT enterprise SSO setup) | Depends on IdP policy | High (External dependency) |

### Principal Security Architect Recommendation: Option A2 (WebAuthn / Passkey Step-Up)
- **Mechanism:** Before minting or modifying canonical root authority, the server issues a WebAuthn challenge (`require_identity_assurance=True`). The user verifies identity via local biometric/hardware security key.
- **Enterprise Federation Compatibility:** Enterprises using Okta/Entra ID satisfy this requirement if their IdP assertion carries strong authentication assurance (AMR `mfa` / `fido2`).
- **Emergency / Interruption Recovery:** The user registers a backup passkey or securely downloads a single-use break-glass recovery key during initial setup.

### Founder Approval Sign-Off Block
- [ ] **APPROVED Option A2 (Recommended)**: Require WebAuthn / Passkey step-up for all production root ceremonies.
- [ ] **APPROVED Option A1 (Interim Pilot Only)**: Allow email-verified sessions for non-consequential sandboxes only.
- [ ] **REJECTED / REQUEST REVISION**: Specify alternative assurance criteria.

**Current State: BLOCKED (Awaiting Founder Signature)**

---

## DECISION RECORD B: EMERGENCY AUTHORITY REVOCATION & BREAK-GLASS

### The Problem
When an organization suspects root key compromise, rogue agent activity, or administrative breach, how should emergency containment and root recovery be structured?
If an emergency revocation requires multi-party quorum, an active rogue agent could execute damaging operations during the voting window. Conversely, if a single owner can unilaterally transfer root authority without checks, a compromised owner account can seize complete control of the tenant.

### Proposed Governance Separation

WhitePact proposes a strict **separation of powers**:

1. **Immediate Unilateral Containment (Kill-Switch)**:
   - Any verified Organization Owner can trigger an **immediate unilateral emergency revocation** (`POST /api/enterprise/organizations/{org_id}/authority/root/{root_id}/revoke`).
   - This increments the tenant revocation epoch (`bump_epoch`), immediately invalidating all outstanding short-lived execution grants across all agents in zero milliseconds.
   - Requires strong step-up authentication.
   - Emits high-priority tamper-evident audit evidence.
2. **Quorum-Gated Root Recovery & Transfer**:
   - Re-issuing a new canonical root authority after revocation, or transferring ownership to a new entity, cannot be performed unilaterally if the organization has more than one registered administrator.
   - Requires **M-of-N administrative quorum** (default 2-of-3) or approved enterprise break-glass recovery procedure.
3. **No Silent Privilege Expansion**:
   - Break-glass procedures can **only restrict or reset** privileges; they can never silently expand permissions beyond the customer's recorded consent boundaries.

### Founder Approval Sign-Off Block
- [ ] **APPROVED Proposed Separation (Immediate Unilateral Revoke + Quorum Recovery)**.
- [ ] **APPROVED Unilateral Only (Single-owner controls both revoke and re-issue)**.
- [ ] **APPROVED Quorum Only (Both revoke and re-issue require 2-of-N sign-off)**.

**Current State: BLOCKED (Awaiting Founder Signature)**

---

## 3. RELEASE IMPACT

Until the WhitePact founders formally select and sign off on Decisions A and B:
- Release Gate **S12 remains LOCKED**.
- Platform status remains **GLOBAL PRODUCTION NO-GO**.
- Safe engineering and independent integration testing proceed without disruption.
