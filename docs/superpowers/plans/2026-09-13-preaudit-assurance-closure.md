# WhitePact Pre-Audit Assurance Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete all first-party enterprise assurance work that WhitePact can legitimately finish without paid independent audit or certification.

**Architecture:** Build one evidence-first assurance layer over the existing compliance artifacts. Add missing management-system policies/readiness packs, reconcile stale readiness assumptions, and finish with a closure report that distinguishes internally complete work from genuine external dependencies.

**Tech Stack:** Markdown compliance artifacts, Git/GitHub evidence, existing Python/CI/security controls, CSA CAIQ/AI-CAIQ evidence, existing WhitePact governance/security documentation.

**Spec:** `docs/superpowers/specs/2026-09-13-preaudit-assurance-closure-design.md`

## Global Constraints

- Never claim external certification, audit, legal review or independent pentest without external evidence.
- Preserve existing documented limitations instead of converting roadmap intent into implemented status.
- Treat provider certifications as inherited/shared evidence only, never WhitePact certification.
- Final production claims must later bind to an exact V1 release SHA.
- Prefer evidence references already present in the repository over duplicate prose.

---

### Task 1: Land governance foundations

**Files:**
- Create: `compliance/AI_GOVERNANCE_POLICY.md`
- Create: `compliance/RISK_MANAGEMENT_POLICY.md`

- [ ] Port the already-reviewed policy text from the signed CSA readiness branch.
- [ ] Preserve explicit non-certification and non-independence boundaries.
- [ ] Ensure risk register includes independent-assurance, resilience, prompt-injection, secret, supply-chain and solo-maintainer risks.

### Task 2: Build the master assurance index

**Files:**
- Create: `compliance/ENTERPRISE_ASSURANCE_MASTER_INDEX.md`

- [ ] Define control families and canonical evidence sources.
- [ ] Map each family to SOC 2, ISO/IEC 27001, ISO/IEC 42001, CSA STAR, STAR for AI, GDPR/DPDP/EU AI Act, NIST and buyer questionnaires.
- [ ] Record implementation status and external dependencies.

### Task 3: Complete ISO management-system readiness

**Files:**
- Create: `compliance/ISO_27001_ISMS_READINESS.md`
- Create: `compliance/ISO_42001_AIMS_READINESS.md`

- [ ] Define scope, interested parties, objectives and risk methods.
- [ ] Create Statement-of-Applicability-style control mapping for ISO/IEC 27001.
- [ ] Define AI inventory, AI impact/risk triggers, lifecycle controls and management-review inputs for ISO/IEC 42001.
- [ ] Explicitly separate implementation readiness from accredited certification.

### Task 4: Complete privacy and regulatory readiness

**Files:**
- Create: `compliance/PRIVACY_REGULATORY_READINESS_2026-09-13.md`

- [ ] Map existing privacy controls to GDPR operational obligations.
- [ ] Map India DPDP Act/Rules operational readiness and effective-timeline dependencies.
- [ ] Reconcile EU AI Act role analysis and the general application date already in force as of 2026-09-13.
- [ ] Flag counsel-only interpretation issues.

### Task 5: Refresh SOC 2 and CSA readiness

**Files:**
- Create: `compliance/SOC2_READINESS_ADDENDUM_2026-09-13.md`
- Create: `compliance/CSA_STAR_SUBMISSION_READINESS_2026-09-13.md`

- [ ] Correct stale SOC 2 assumptions that predate the hosted reference deployment.
- [ ] Record the remaining operating-evidence, oversight and external-auditor dependencies.
- [ ] Record the current CAIQ / AI-CAIQ submission path and claim boundaries.

### Task 6: Finish external-assurance handoff packs

**Files:**
- Create: `compliance/PENTEST_READINESS_PACKAGE.md`
- Create: `compliance/LEGAL_COMMERCIAL_READINESS.md`

- [ ] Define pentest scope, trust boundaries, test surfaces, safe rules of engagement and evidence requirements.
- [ ] Inventory legal/commercial documents and label which are internally complete drafts versus counsel/insurer/company-officer actions.

### Task 7: Close and verify the assurance package

**Files:**
- Create: `compliance/PREAUDIT_CLOSURE_2026-09-13.md`

- [ ] Enumerate internally completed work.
- [ ] Enumerate only genuine external/elapsed-time blockers.
- [ ] Confirm no artifact claims certification or independent assurance without evidence.
- [ ] Review the branch diff and open a PR to `main`.
