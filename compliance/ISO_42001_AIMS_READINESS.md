# WhitePact ISO/IEC 42001:2023 AIMS Readiness Pack

**Status:** First-party implementation/readiness evidence; not certification  
**Standard target:** ISO/IEC 42001:2023  
**Review date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner

> ISO/IEC 42001:2023 specifies requirements for establishing, implementing, maintaining and continually improving an Artificial Intelligence Management System (AIMS). WhitePact can establish and operate an AIMS internally; certification remains external.

Official reference: https://www.iso.org/standard/42001

## 1. AIMS scope

The AIMS covers WhitePact features that develop, provide, integrate, govern, evaluate or materially influence AI/agent behavior, including:

- deterministic runtime governance and policy enforcement;
- trust, bias, hallucination and guardrail functions;
- MCP and agent integration surfaces;
- approval, denial, redaction, quarantine and evidence paths;
- AI-related dashboard/API administration;
- external/customer-selected model providers where WhitePact integrates with them;
- AI risk, incident and change governance.

WhitePact does not currently claim to be a foundation-model provider and does not currently scope base-model training datasets/weights as WhitePact-controlled assets unless that changes.

## 2. AI governance objectives

WhitePact adopts these AIMS objectives:

1. AI-generated intent must not automatically become privileged authority.
2. High-risk/state-changing actions must be subject to policy, authorization and approval controls appropriate to risk.
3. Material AI/agent decisions must be explainable through deterministic evidence where WhitePact is the enforcement layer.
4. AI security/safety incidents must be traceable to versioned configuration, policy and evidence where technically possible.
5. AI-system changes must trigger reassessment of inventory, risk, impact and framework applicability.
6. Public claims must distinguish deterministic governance guarantees from probabilistic model-quality claims.
7. Customer/provider responsibility boundaries must be explicit.

## 3. AI system inventory

The canonical inventory begins with `compliance/AI_GOVERNANCE_POLICY.md` and is maintained on material change.

| System/component | WhitePact role | Risk focus | Owner boundary |
|---|---|---|---|
| Runtime governance engine | AI/agent control and enforcement | unauthorized action, authority escalation, policy bypass | WhitePact |
| Guardrails/PII/safety scanning | input/output control | data leakage, unsafe content, bypass | WhitePact/configuration shared |
| Trust/bias/hallucination evaluation | assurance/scoring | misleading confidence, model variability, misuse of score | WhitePact methodology + customer use |
| MCP/agent integrations | control surface | tool abuse, prompt injection, over-privilege, transitive actions | WhitePact + integrator |
| External LLM/model providers | dependency | non-determinism, retention, provider compromise, model change | Provider/customer shared |
| Approval/evidence/revocation | oversight/accountability | stale approval, replay, incomplete evidence | WhitePact |

## 4. AI risk and opportunity process

AI risks use `compliance/RISK_MANAGEMENT_POLICY.md` with additional AI-specific dimensions:

- autonomy and real-world impact;
- authority/privilege reach;
- data sensitivity;
- reversibility of action;
- human-oversight strength;
- model/tool/provider dependency;
- prompt/instruction attack surface;
- multi-agent/transitive capability effects;
- evidence and observability quality;
- affected people/business processes;
- potential legal/regulatory impact.

Opportunities are also documented where AI controls improve safety, auditability, availability, customer trust or operational efficiency without weakening control boundaries.

## 5. AI impact-assessment triggers

A documented AI impact/risk review is required before or on:

- introducing a new model/provider used by WhitePact itself;
- adding a privileged/autonomous tool or integration;
- expanding data categories, retrieval sources or retention;
- enabling a new consequential action category;
- materially changing approval/deny/quarantine/redaction logic;
- adding fine-tuning or WhitePact-owned model weights;
- changing system prompts/instruction architecture in a way that affects security;
- adding multi-agent delegation or transitive capability;
- materially changing output used for regulated/high-impact decisions;
- a material AI incident or confirmed policy bypass.

The review records intended purpose, affected stakeholders, authority/capability, foreseeable misuse, data/privacy impact, safety/security impact, human oversight, monitoring, residual risk and release decision.

## 6. Lifecycle control model

### Plan

- define intended purpose and system boundary;
- identify interested parties and requirements;
- classify risk/impact;
- define human oversight and prohibited use;
- identify third-party dependencies.

### Build/change

- version control and protected-branch review;
- security/static/dependency/secret scanning;
- tests for authorization, tenant isolation, decision paths and known abuse cases;
- explicit change review for privileged agent/tool behavior.

### Validate/release

- exact-SHA CI/security evidence;
- release SBOM/provenance/signing controls;
- adversarial/regression testing appropriate to the changed surface;
- claim-boundary review before public release.

### Operate

- authentication/authorization and tenant controls;
- evidence/logging and monitoring;
- approval/quarantine/revocation mechanisms;
- incident response and vulnerability handling;
- vendor/provider monitoring.

### Retire/change materially

- revoke credentials/integrations;
- follow retention/deletion policy;
- preserve required evidence;
- update inventory and public documentation.

## 7. Human oversight

WhitePact's design principle is that high-risk agent actions can be held for explicit approval, denied or quarantined rather than automatically executed. Human oversight must be meaningful: the approver needs sufficient context, authority and ability to refuse/revoke.

Current limitation: a solo maintainer cannot provide independent organizational oversight over all project controls. This is an organizational risk, not something documentation can cure.

## 8. Transparency and information for users

WhitePact documentation must communicate:

- intended purpose and role;
- limitations and shared-responsibility boundaries;
- whether a decision is deterministic versus probabilistic;
- material data/retention behavior;
- approval/audit behavior;
- provider/customer dependencies;
- current assurance/certification status without inflation.

## 9. AI incident and nonconformity handling

AI incidents are handled through `compliance/INCIDENT_RESPONSE_RUNBOOK.md`. A material incident or nonconformity must trigger, as applicable:

1. containment/revocation/quarantine;
2. evidence preservation;
3. impact and scope assessment;
4. root-cause analysis;
5. corrective action and regression test;
6. risk-register update;
7. inventory/policy/process update;
8. customer/regulator notification if legally/contractually required;
9. effectiveness review.

## 10. Monitoring and AIMS metrics

Useful first-party metrics include:

- Critical/High security findings open over SLA;
- unauthorized/denied/quarantined action counts;
- approval volume and stale/expired approval attempts;
- evidence-chain verification failures;
- cross-tenant authorization test failures;
- AI/agent incidents by severity;
- dependency/provider security events;
- exact-release CI/security pass status;
- policy exceptions and residual High risks;
- time to revoke compromised authority/credential;
- training/awareness completion when team size grows.

## 11. Internal audit and management review

At least annually and before certification, WhitePact should perform a documented AIMS internal review of:

- scope and AI inventory accuracy;
- risk/impact assessments;
- changes since previous review;
- incident/nonconformity history;
- policy/control effectiveness;
- monitoring metrics;
- vendor/model/provider changes;
- legal/regulatory developments;
- customer feedback/complaints;
- resourcing and oversight needs;
- improvement actions.

Because self-review by the sole maintainer lacks independence, it is readiness evidence only. External certification/audit independence cannot be self-created.

## 12. Existing supporting evidence

- `compliance/AI_GOVERNANCE_POLICY.md`
- `compliance/RISK_MANAGEMENT_POLICY.md`
- `compliance/ISO_42001_SUPPORT_MATRIX.md`
- `compliance/NIST_AI_RMF_MAPPING.md`
- `compliance/EU_AI_ACT_TECHNICAL_MAPPING.md`
- `compliance/OWASP_AI_AGENT_SECURITY_MAPPING.md`
- `SPEC.md`
- governance code/tests and evidence/approval/revocation controls
- incident response and vendor-risk evidence
- exact-release and supply-chain assurance artifacts

## 13. Certification blockers that remain external/operational

- accredited ISO/IEC 42001 certification body and independent audit;
- operating evidence from the final scoped service/release;
- stronger separation of duties/independent oversight as organization grows;
- closure of any scoped operational gaps discovered during Stage 1/Stage 2 audit;
- independent penetration/security review where auditors/customers require it.

## 14. Claim boundary

Allowed now: **"WhitePact has established an ISO/IEC 42001:2023-aligned AIMS readiness structure with AI inventory, risk, impact, lifecycle, oversight and incident-governance processes."**

Not allowed without external certificate: **"WhitePact is ISO/IEC 42001 certified."**
