# Consensus Assessment Self-Assessment — {{COMPANY_NAME}}

> Modeled on the Cloud Security Alliance's Consensus Assessment Initiative
> Questionnaire (CAIQ) domain structure. This is a self-administered
> response, not a copy of CSA's proprietary question text, and not a
> substitute for a formal SOC2/ISO 27001 audit — it exists so a security
> reviewer doesn't have to wait on one to get real answers.
>
> **How to use this template**: replace every `[FILL IN: ...]` placeholder
> with a true, specific, citable fact about {{COMPANY_NAME}}'s actual
> systems — a file path, a config value, a documented process. Where a
> control genuinely doesn't exist yet, **write that down plainly** — "Not
> implemented, planned for Q[X]" is a legitimate, credible answer. A vague
> or evasive answer is worse than an honest gap; a reviewer who catches one
> fabricated claim stops trusting every other claim in the document.

Last reviewed: {{DATE}} · Prepared for: {{COMPANY_NAME}}

---

## Domain 1 — Application & Interface Security

| Question | Answer |
|---|---|
| Are applications tested for security vulnerabilities before release? | [FILL IN: what runs in CI — linting, type checking, dependency scanning, SAST? Name the actual tools.] |
| Is input validation enforced on all external-facing APIs? | [FILL IN: what validates request payloads — a schema library, manual checks? Cite the actual mechanism.] |
| Are API keys/secrets ever exposed in logs or error messages? | [FILL IN: how are secrets stored — hashed, plaintext, a secrets manager? Be honest if this hasn't been audited.] |
| Is output encoding applied to prevent injection attacks? | [FILL IN: SQL — parameterized queries or an ORM? XSS — templating auto-escaping, or none?] |
| Are session tokens/API keys rotated and revocable? | [FILL IN: is there a revoke endpoint/process? Is rotation manual or automatic?] |

## Domain 2 — Audit Assurance & Compliance

| Question | Answer |
|---|---|
| Is there an immutable or tamper-evident audit trail? | [FILL IN: does one exist at all? If yes, what makes it tamper-evident — hash chaining, append-only storage, something else?] |
| Can audit logs be exported for external SIEM ingestion? | [FILL IN: is there an export endpoint/format?] |
| Is there a third-party compliance certification (SOC2, ISO 27001)? | [FILL IN: the honest current status — "not started," "in progress since [date]," or the real certification with a verifiable link.] |
| Are compliance framework mappings available (relevant AI/data regulations)? | [FILL IN: does the product map to any named framework? Don't claim one that doesn't apply.] |

## Domain 3 — Business Continuity Management & Operational Resilience

| Question | Answer |
|---|---|
| Is there a documented disaster recovery plan? | [FILL IN: RPO/RTO targets, backup mechanism and frequency.] |
| Is backup data encrypted? | [FILL IN: at the application layer, storage layer, or not at all yet?] |
| Is there a documented uptime SLA? | [FILL IN: real commitment, or "no formal SLA yet" if that's true.] |
| Is there redundancy/failover for the hosted stack? | [FILL IN: multi-replica? Automated failover, or manual?] |

## Domain 4 — Change Control & Configuration Management

| Question | Answer |
|---|---|
| Are schema/infrastructure changes version-controlled and auditable? | [FILL IN: migration tooling, IaC, or manual changes?] |
| Is there a rollback procedure for failed deployments? | [FILL IN: documented steps, or none yet?] |
| Are production deployments gated by automated tests? | [FILL IN: what runs before merge/deploy, and how many tests exist?] |

## Domain 5 — Data Security & Information Lifecycle Management

| Question | Answer |
|---|---|
| Is data encrypted at rest? | [FILL IN: whole-database, field-level, or neither yet? Whose responsibility — the platform's or the deployer's infrastructure?] |
| Is data encrypted in transit? | [FILL IN: TLS termination point — app-level or reverse-proxy/load-balancer?] |
| Is there a data retention and deletion policy? | [FILL IN: documented retention periods per data type, or none yet?] |
| Is field-level/column-level encryption used for sensitive data? | [FILL IN: which specific columns, if any, and the mechanism.] |

## Domain 6 — Infrastructure & Hosting

| Question | Answer |
|---|---|
| What infrastructure provider(s) host the production system? | [FILL IN: name the provider(s) and region(s).] |
| Does the hosting provider carry its own relevant certifications? | [FILL IN: cite the provider's own SOC2/ISO 27001 status — this is real credibility even before the product itself is certified.] |
| What are the actual resource/capacity limits of the current deployment? | [FILL IN: be honest about scale ceilings — don't oversell capacity that hasn't been load-tested.] |

## Domain 7 — Encryption & Key Management

| Question | Answer |
|---|---|
| How are API keys/secrets stored? | [FILL IN: hashing algorithm, or plaintext if that's the honest current state — flag it as a gap if so.] |
| Is there a key rotation mechanism? | [FILL IN: for both user-facing credentials and any application-level encryption keys.] |
| Is field-level/column-level encryption key-rotatable? | [FILL IN: single static key, or a documented rotation procedure?] |

## Domain 8 — Identity & Access Management

| Question | Answer |
|---|---|
| Is role-based access control (RBAC) implemented? | [FILL IN: how many roles, how granular?] |
| Is SSO/OIDC supported? | [FILL IN: which providers, and is it enforceable org-wide?] |
| Is multi-factor authentication supported? | [FILL IN: for which auth paths — human login, API keys, both, neither yet?] |

---

## Compliance roadmap (fill in honestly, don't leave blank)

| Gap | Priority | Target timeframe |
|---|---|---|
| [FILL IN: e.g. "No SOC2"] | [FILL IN] | [FILL IN — or "funding-gated, no committed date" if that's the truth] |
| [FILL IN] | [FILL IN] | [FILL IN] |

---

*Template version 1.0, adapted from the CAIQ self-assessment structure
originally built for the ResponsibleAI Governance Platform
(`compliance/CAIQ_SELF_ASSESSMENT.md` in that project) — see
`compliance/COMPLIANCE_STARTER_KIT_OFFER.md` for how this template was
produced and how to get help filling it in.*
