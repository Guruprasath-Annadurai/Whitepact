# WhitePact Internal Management Review — 2026-09-13

**Review type:** First-party ISMS/AIMS/pre-audit management review  
**Reviewer/owner:** WhitePact maintainer / service owner  
**Baseline:** `main@8f8ef53f0460c99115f5656dfa4d31775bca4d6a` plus `compliance/preaudit-assurance-closure-2026-09-13`  
**Independence:** None — this is founder/maintainer self-review, not independent audit

## 1. Purpose

Review WhitePact's security, privacy, AI governance and enterprise-assurance posture before V1 enterprise release, identify decisions/actions that can be completed internally, and isolate the items that genuinely require external assurance, legal authority, elapsed operating time or unfinished V1 engineering.

## 2. Significant changes reviewed

The project has materially expanded from a general responsible-AI platform into an AI/agent runtime governance and assurance product with:

- deterministic governance decisions;
- approval/evidence/revocation controls;
- agent/MCP integration surfaces;
- stronger identity/authority work;
- supply-chain and release hardening;
- OpenSSF/SBOM/provenance evidence;
- hosted reference-service documentation;
- formal AI governance/risk/readiness artifacts.

These changes justify re-scoping assurance evidence around WhitePact rather than relying on older ResponsibleAI-era wording.

## 3. Current strengths

### Governance/security

- protected main branch with required checks;
- formal vulnerability disclosure and recurring security/dependency/secret scans;
- RBAC/SSO/MFA and tenant-scoped authorization controls;
- approval, evidence and audit mechanisms;
- incident-response runbook and prior tabletop exercise;
- vendor-risk and continuity documentation;
- release signing/SBOM/provenance/supply-chain controls.

### AI governance

- explicit distinction between probabilistic AI output and deterministic governance decisions;
- documented AI system scope and inventory;
- human approval/deny/quarantine concepts;
- agent/tool shared-responsibility boundaries;
- NIST AI RMF, EU AI Act, OWASP agent-security and ISO 42001 support mappings;
- new AIMS readiness structure and AI/privacy impact-assessment template.

### Assurance preparation

- SOC 2 readiness material and current-state addendum;
- ISO/IEC 27001 ISMS readiness structure;
- ISO/IEC 42001 AIMS readiness structure;
- CSA STAR / STAR for AI submission-readiness pack;
- privacy/regulatory readiness map;
- RoPA/data-flow baseline;
- master evidence index and operating-evidence register;
- pentest handoff package;
- legal/commercial readiness register.

## 4. Material residual risks/findings

| ID | Finding | Rating | Decision / action |
|---|---|---|---|
| MR-001 | No independent penetration test/security assessment | High | Accept temporarily for pre-audit stage; prepare independent engagement using pentest package before strong enterprise trust claims where feasible |
| MR-002 | No SOC 2 report | High for some enterprise buyers | Readiness complete internally; external CPA/auditor and operating evidence required |
| MR-003 | No ISO 27001/42001 certificates | Medium/High depending buyer | Management-system readiness established; external certification bodies required |
| MR-004 | CSA registry publication not confirmed | Medium | Submission pack ready; authorized applicant must use current portal/workbooks and await publication |
| MR-005 | Solo-maintainer concentration / weak separation of duties | Medium | Continue automation/traceability; add real independent oversight when feasible |
| MR-006 | Cross-region/high-availability evidence limited | High for strict availability commitments | Do not overpromise SLA; close through V1 production architecture/operating evidence before selling stronger resilience |
| MR-007 | Retention schedule requires operating/automation proof | Medium | Manual procedure adopted; implement/verify technical enforcement and retain OE-013 evidence |
| MR-008 | Final V1 exact-SHA evidence not yet frozen | High | Mandatory release gate: freeze exact SHA, rerun full suite, bind SBOM/provenance/deployment evidence |
| MR-009 | Legal/contractual documents not attorney reviewed | Medium | Keep claim warning; use counsel for material enterprise agreements when engaged |
| MR-010 | Production key-rotation/restore/revocation evidence must remain current | Medium | Collect under operating-evidence register; never infer operation from written procedure alone |

## 5. Security/privacy/AI objectives review

The newly established objectives are appropriate for the current stage:

- fail closed on critical governance/evidence failures where designed;
- prevent unauthorized/cross-tenant action;
- preserve exact-release traceability;
- keep security scanning and protected change control active;
- maintain quarterly risk reviews;
- maintain AI/data inventories on material change;
- preserve honest public trust boundaries;
- collect operating evidence prospectively.

No objective is considered permanently achieved merely because a policy exists; ongoing evidence is required.

## 6. External and internal inputs

### External context

- enterprise buyers increasingly request independent assurance and standardized security questionnaires;
- ISO/IEC 27001 and ISO/IEC 42001 remain relevant certification targets;
- CSA STAR and STAR for AI provide self-assessment registry pathways before Level 2/third-party assurance;
- EU AI Act general application is now in force as of 2026-08-02 subject to its phased provisions;
- India DPDP implementation must be tracked against official commencement/rules.

### Internal context

WhitePact is still closing V1 enterprise engineering. Assurance claims must therefore distinguish current `main`, assurance branch artifacts and the future exact V1 enterprise release.

## 7. Decisions

1. Adopt the enterprise assurance master index as the first-party starting point for buyer/auditor evidence.
2. Adopt formal AI governance and risk-management policies.
3. Adopt ISO 27001/42001 readiness structures without claiming certification.
4. Begin prospective operating-evidence collection immediately.
5. Use the RoPA and privacy/AI impact assessment for material data/AI changes.
6. Use current CSA workbooks/portal at submission time; do not rely blindly on historical v4.0.3 material.
7. Do not publicly claim independent audit/pentest/certification/attorney review until external evidence exists.
8. Block enterprise-release trust claims until exact-SHA revalidation is complete.

## 8. Improvement actions

| Action | Owner | Gate/cadence |
|---|---|---|
| Freeze enterprise V1 release SHA and exact-SHA evidence bundle | Maintainer | V1 release gate |
| Implement/verify retention enforcement and collect deletion evidence | Maintainer | Before privacy commitments are treated as fully technically enforced |
| Execute restore/key-rotation/access-review evidence cycles | Maintainer | Per operating-evidence register |
| Strengthen production resilience/HA consistent with sold SLA | Maintainer | Before stronger availability commitments |
| Submit CSA STAR + STAR for AI using current portal/materials | Authorized applicant | Pre/post V1 launch as appropriate |
| Engage independent pentest | External assessor + maintainer | Funding/customer requirement / before strong external assurance claims |
| Engage SOC 2 auditor | External CPA/auditor | Once scope/operating evidence supports engagement |
| Engage ISO certification body | External certification body | When ISMS/AIMS operation is mature enough |
| Obtain legal review of material enterprise contracts | Qualified counsel | Before relying on high-risk/negotiated terms |
| Add independent organizational oversight | Founder/organization | As soon as practical for enterprise scale |

## 9. Review conclusion

WhitePact has enough first-party control evidence and documentation to enter a disciplined pre-audit phase. The major remaining trust gaps are no longer a lack of paperwork; they are external independence, operating history, final-release verification and a small number of real operational/engineering gaps.

This conclusion must not be represented as independent certification, audit or security validation.
