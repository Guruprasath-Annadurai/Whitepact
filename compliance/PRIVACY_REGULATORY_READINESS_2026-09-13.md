# WhitePact Privacy and Regulatory Readiness — 2026-09-13

**Status:** First-party technical/organizational readiness analysis; not legal advice or legal certification  
**Owner:** WhitePact maintainer / service owner  
**Review date:** 2026-09-13

## Source baseline

- GDPR: Regulation (EU) 2016/679 — official text: https://eur-lex.europa.eu/eli/reg/2016/679/
- EU AI Act: Regulation (EU) 2024/1689 — official text: https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:32024R1689
- India DPDP Act/Rules: Ministry of Electronics and Information Technology — https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa?pageTitle=Digital-Personal-Data-Protection-Rules-2025

> Regulatory applicability depends on WhitePact's actual customers, data flows, contractual role and deployment model. This document identifies readiness evidence and known gaps; qualified counsel must validate jurisdiction-specific legal conclusions before WhitePact markets itself as legally compliant in a specific scenario.

## 1. Current WhitePact privacy baseline

Existing canonical evidence:

- `PRIVACY_POLICY.md`
- `compliance/DPA_TEMPLATE.md`
- `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`
- `compliance/VENDOR_RISK_ASSESSMENT.md`
- `compliance/INCIDENT_RESPONSE_RUNBOOK.md`
- `compliance/KEY_MANAGEMENT.md`
- RBAC/SSO/MFA/tenant-isolation controls
- PII guardrails and selective field encryption
- retention commitments and deletion/rights-request procedures described in policy

Important existing limitation: WhitePact's Privacy Policy is intentionally self-drafted and not attorney-reviewed. It also records that adopted retention periods must be backed by actual operational enforcement/evidence rather than assumed from policy text alone.

## 2. GDPR readiness map

| GDPR area | WhitePact readiness | Evidence / action |
|---|---|---|
| Lawfulness, fairness, transparency | Documented | Privacy Policy identifies purposes and asserted legal bases; counsel should validate bases for actual deployment/customer roles |
| Purpose limitation / data minimization | Implemented design + policy | Privacy Policy, PII controls, limited audit/evidence payloads |
| Storage limitation | Partial | Retention schedule adopted; verify automated/manual enforcement and retain deletion evidence |
| Accountability | Implemented first-party structure | Risk policy, evidence index, incident/vendor/security documentation |
| Controller/processor role clarity | Partial | DPA template and shared-responsibility docs exist; customer-specific role needs contract/legal review |
| Processor terms / subprocessors | Prepared | DPA and vendor register; final contractual language requires counsel/customer execution |
| Security of processing | Strong technical baseline | RBAC, MFA/SSO, tenant isolation, encryption options, CI/security testing, audit/evidence, continuity |
| Breach handling | Implemented process | Incident runbook; external notification decisions require legal/contractual assessment |
| Data-subject rights | Documented | Privacy Policy rights/request process; retain real request handling evidence when requests occur |
| Records of processing | Prepared | This readiness pack + DPA/vendor/data-category inventory provide a foundation; formal RoPA should be maintained for actual hosted processing |
| DPIA/high-risk assessment | Prepared process | Trigger privacy/AI impact review for sensitive/high-risk processing or material new data uses |
| International transfers | External/legal dependency | Actual hosting/customer geography and transfer mechanism must be reviewed before relevant deployments |
| EU representative/DPO questions | External/legal dependency | Determine only if factual thresholds/applicability are met; do not appoint/claim unnecessarily |

### GDPR internal tasks WhitePact can complete without an auditor

1. Maintain data-flow and subprocessor inventory.
2. Enforce/document retention and deletion procedures.
3. Maintain a rights-request register template and response evidence.
4. Maintain a privacy-impact/DPIA trigger process.
5. Maintain technical and organizational measures evidence.
6. Review new vendors/data uses before release.
7. Keep controller/processor responsibility language consistent across Privacy Policy, DPA and enterprise contracts.

## 3. India DPDP readiness map

The Government of India published the Digital Personal Data Protection Rules, 2025 and an official enforcement-timeline document on 14 November 2025. WhitePact must assess provision-specific commencement/applicability against the official notifications before relying on any deadline assumption.

| DPDP readiness area | WhitePact posture | Evidence / action |
|---|---|---|
| Notice/transparency | Prepared | Privacy Policy identifies categories/purposes; India-specific notice should be reviewed for actual hosted service |
| Consent where relied upon | Partial/shared | Consent should be specific, informed and withdrawable where that legal basis applies; avoid using consent where contract/other lawful basis is actually intended without counsel review |
| Reasonable security safeguards | Strong technical baseline | access controls, tenant isolation, encryption options, CI/security scans, incident response, vendor review |
| Data minimization / purpose control | Implemented design + policy | Privacy Policy and architecture boundaries |
| Retention/deletion | Partial | adopted schedule exists; actual enforcement/evidence must be verified |
| Data-principal requests/grievance handling | Prepared | privacy contact and rights-request process exist; India-specific procedural requirements should be validated |
| Processor/subprocessor control | Prepared | DPA/vendor-risk artifacts |
| Personal-data breach response | Implemented process / legal notification external | incident runbook exists; statutory notification content/timing needs current legal check during a real incident |
| Cross-border processing | External/legal dependency | verify restrictions/notifications applicable at deployment time |
| Significant Data Fiduciary obligations | Conditional | assess only if WhitePact is designated or meets applicable conditions; do not self-claim designation |

## 4. EU AI Act readiness map

Regulation (EU) 2024/1689 generally applies from **2 August 2026**, with some provisions applying earlier and certain Article 6(1)-related obligations later. As of this review date, WhitePact must no longer describe the EU AI Act generally as a future-only regime.

WhitePact's regulatory role is deployment/use-case dependent. WhitePact is primarily an AI governance/runtime assurance platform, not currently a provider of its own general-purpose foundation model.

| EU AI Act topic | WhitePact readiness | Evidence / action |
|---|---|---|
| Role classification | Prepared | determine provider/deployer/importer/distributor/other role per actual product/use case; legal validation external |
| Prohibited-practice awareness | Prepared | AI governance policy should block/flag clearly prohibited or unsupported customer uses where WhitePact is in enforcement path; legal determination remains contextual |
| AI literacy/governance | Prepared first-party | AI governance policy, architecture docs, risk process; formal workforce training evidence expands with team growth |
| Risk management | Implemented first-party process | `compliance/RISK_MANAGEMENT_POLICY.md`, AIMS readiness |
| Technical documentation / traceability | Strong technical baseline | versioned code, decisions/evidence, SBOM/provenance, mappings, release evidence |
| Logging/record keeping | Strong technical baseline | hash-chained evidence/audit with documented limitations |
| Human oversight | Strong product support | approval/deny/quarantine/revocation paths; customer deployment must configure appropriate oversight |
| Accuracy/robustness/cybersecurity | Partial / system-dependent | testing/security hardening exists; model/provider accuracy remains shared/probabilistic and must not be overclaimed |
| Transparency | Prepared | documentation must explain intended use, limitations, deterministic vs probabilistic outputs and shared responsibility |
| High-risk conformity obligations | Conditional/external | depends on whether WhitePact or a customer use case falls into relevant high-risk scope; conformity assessment/legal interpretation cannot be self-declared by this pack |
| GPAI obligations | Generally out of current WhitePact scope | WhitePact does not currently train/provide its own GPAI foundation model; re-scope if that changes |

## 5. Privacy/AI impact-assessment trigger

A documented privacy/AI impact review is mandatory before release when a change introduces:

- new categories of personal/sensitive data;
- systematic monitoring/profiling with material effects;
- biometric/health/financial/children's or other high-sensitivity data;
- new cross-border data flow;
- new model/provider receiving customer data;
- new long-term retention or training use;
- consequential automated decision-making;
- new privileged autonomous action;
- material expansion of agent memory/retrieval;
- new public disclosure of customer/end-user data.

The review records purpose, data categories, people affected, legal/contractual role, data flow, retention, subprocessors, security, human oversight, foreseeable harms, mitigations, residual risk and release decision.

## 6. Operating evidence WhitePact should retain

- dated subprocessor reviews;
- privacy-policy/DPA versions accepted by customers where applicable;
- deletion/retention job or manual-run evidence;
- rights-request tickets and response dates (without publishing private request content);
- incident assessments/notifications where applicable;
- impact assessments for material changes;
- vendor DPAs/terms where available;
- exact-release security evidence;
- customer configuration/shared-responsibility acknowledgements where contractually relevant.

## 7. External-only items

WhitePact cannot internally manufacture:

- attorney legal opinion;
- regulator approval/determination;
- court interpretation;
- customer contract execution;
- EU representative/DPO engagement if legally required;
- independent privacy certification/assurance;
- statutory notification outcome from a real incident.

## 8. Claim boundary

Allowed now: **"WhitePact maintains documented GDPR/India-DPDP/EU-AI-Act technical and organizational readiness mappings, privacy/security controls and impact-review procedures."**

Not allowed solely from this work: **"WhitePact is certified GDPR/DPDP/EU-AI-Act compliant"** or any statement implying regulator/attorney approval that does not exist.
