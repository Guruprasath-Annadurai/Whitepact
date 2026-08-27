# WhitePact — CSA STAR Repository Audit

**Audit date:** 2026-08-27  
**Repository:** `Guruprasath-Annadurai/Whitepact`  
**Baseline:** `main`  
**Purpose:** evidence-led readiness review for CSA STAR Level 1 (CCM/CAIQ) and CSA STAR for AI Level 1 (AICM/AI-CAIQ).

## Important status language

This document is a self-assessment and readiness audit. It does **not** claim that WhitePact is independently certified, audited, or approved by the Cloud Security Alliance.

- CSA STAR Level 1 is a public **self-assessment** designation after CSA accepts/publishes a valid CAIQ submission.
- CSA STAR for AI Level 1 is a public **self-assessment** designation after CSA accepts/publishes a valid AI-CAIQ submission.
- Only CSA's registry publication/approval can establish those statuses.

## Executive conclusion

WhitePact has a strong technical-control baseline for a solo-maintained project and substantially more evidence than the older `compliance/CAIQ_SELF_ASSESSMENT.md` reflects. The repository is suitable for truthful Level 1 self-assessment work, but known gaps must not be converted into `Yes` answers merely to maximize a score.

### Readiness summary

| Area | Assessment | Evidence / qualification |
|---|---|---|
| Secure SDLC | Strong | CI gates lint, format, type checks, tests, coverage, package build and Helm validation. |
| Vulnerability management | Strong self-managed baseline | `pip-audit`, Bandit, Gitleaks and recurring security scans exist; no independent penetration test exists. |
| Software supply chain | Strong | CycloneDX SBOM, signed release tags, GitHub build provenance, PyPI trusted publishing. |
| Source/change control | Strong with one documented gap | Branch-protection evidence documents PR/CI gates and admin enforcement. Dependency Review is not a required merge gate because Dependency Graph is not enabled. |
| IAM | Strong application capability | RBAC, OIDC, SAML, SSO enforcement and TOTP support exist. Deployment/operator configuration still matters. |
| Tenant/data isolation | Strong application evidence | Org-scoped repositories and tenant-isolation tests; encryption-at-rest differs by deployment mode. |
| Auditability | Strong application evidence | Hash-chained governance/audit records and export/verification capabilities; no external immutable anchor. |
| Business continuity | Defined but limited production resilience | Runbooks/backups/tabletop evidence exist; current reference stack lacks cross-region/automatic failover. |
| Governance/risk | Defined self-governance | `GOVERNANCE.md` establishes quarterly reviews. Independent second-person/board oversight does not exist. |
| Independent assurance | Gap | No independent pentest or annual third-party audit is claimed. |
| Personnel security | Limited / solo-founder context | Formal security-awareness training and personnel/background-check programs are not established as organizational programs. |
| AI governance / agent authority | Strong product controls | Deterministic five-way decisions, authority attenuation, approvals, evidence, memory firewall and trust gates. |
| AI-specific sandboxing | Partial / deployment-dependent | WhitePact governs/mediates selected tool paths but is not a universal OS/container sandbox for every external AI tool/plugin. |
| Prompt separation | Shared responsibility / scope-dependent | Persistent-memory injection patterns are detected, but WhitePact does not own every customer's model system prompt or provider runtime. |
| Model training controls | N/A to WhitePact as currently scoped | WhitePact does not train or distribute foundation models. |

## Scope determination for STAR for AI

WhitePact's most defensible AICM role is:

1. **Orchestrated Service Provider (OSP) — primary.** WhitePact provides an orchestration/governance layer that integrates with and governs AI models/agents and their tool calls.
2. **Application Provider (AP) — secondary.** WhitePact exposes application/API/MCP functionality for AI governance, evaluation, trust and assurance.

WhitePact should **not** claim Model Provider status merely because it evaluates or calls models. It does not train/distribute foundation models in the audited scope. Cloud-infrastructure-provider controls are generally inherited/shared with the deployer's chosen infrastructure rather than owned by WhitePact.

## High-confidence control evidence

### Application and interface security

Evidence includes Pydantic validation, parameterized SQL through SQLAlchemy, `THREAT_MODEL.md`, `ENFORCEMENT_BOUNDARY.md`, SSRF protections where documented, and SAML/OIDC validation plus regression tests.

### Secure development and supply chain

Primary evidence:

- `.github/workflows/ci.yml`
- `.github/workflows/security-scan.yml`
- `.github/workflows/gitleaks.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/scorecard.yml`
- `.github/workflows/publish.yml`
- `security/release-signers.allowed`
- `compliance/SIGNED_VERSION_TAGS.md`
- `compliance/OPENSSF_SECURITY_EVIDENCE.md`
- `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`

Release controls include a signed-tag gate, build provenance attestation, CycloneDX SBOM generation and PyPI trusted publishing via OIDC.

### Governance, audit and human control

Evidence includes `GOVERNANCE.md`, `compliance/INCIDENT_RESPONSE_RUNBOOK.md`, `compliance/TABLETOP_EXERCISE_2026-07-21.md`, `compliance/VENDOR_RISK_ASSESSMENT.md`, hash-chained audit/governance evidence, and a stateful `PENDING -> APPROVED/DENIED` approval workflow.

### AI / autonomous-system controls

Evidence includes `MACHINE_AUTHORITY_V1.md`, `ENFORCEMENT_BOUNDARY.md`, `THREAT_MODEL.md`, `DETERMINISTIC_VS_PROBABILISTIC.md`, deterministic five-way governance, authority attenuation/delegation, org ceilings, workflow-composition controls, persistent-memory injection scanning, autonomy budgets, A2A trust gates and offline-verifiable evidence bundles.

## Material gaps that must remain visible in CAIQ / AI-CAIQ

1. **Independent audit/assurance:** no independent penetration test or annual independent control assessment.
2. **Independent governance oversight:** one person currently performs founder, security, incident and risk-owner functions.
3. **Reference deployment resilience:** no cross-region or automatic failover is configured for the current reference stack.
4. **Application-layer encryption scope:** encryption at rest is not guaranteed by WhitePact for every self-hosted deployment; some field-level encryption is opt-in.
5. **Audit-log external anchoring:** hash chains detect ordinary database tampering but not a fully compromised writer that recomputes the chain.
6. **Governance coverage:** hosted MCP enforcement is conditional; self-hosted stdio and certain voluntary integration points are outside inline enforcement.
7. **Autonomy-budget concurrency:** a known count-then-decide race can permit a concurrent burst above the configured cap.
8. **Dependency Review enforcement:** Dependency Graph is not enabled, so the Dependency Review workflow is not a required merge gate.
9. **Formal personnel-security program:** security-awareness/background-check processes are not organizationally mature at solo-founder scale.
10. **AI sandboxing:** WhitePact is a governance/policy enforcement layer, not a universal execution sandbox for every customer tool/plugin.
11. **Customer/provider shared responsibility:** model-provider security, model training data, provider retention, and customer system-prompt design are outside WhitePact's direct control.
12. **Legal review:** the repository's DPA template is explicitly not counsel-reviewed.

## Stale evidence to correct on the next standard CAIQ update

The existing `compliance/CAIQ_SELF_ASSESSMENT.md` should not be treated as the current source of truth without reconciliation because it is based on CAIQ v4.0.3, retains older ResponsibleAI naming in places, predates the quarterly risk cadence in `GOVERNANCE.md`, and contains deployment/domain language that has evolved.

If the existing STAR Level 1 submission is already under CSA review, do not replace it merely to modernize these points. Preserve the pending filing, then update the registry assessment through the normal CSA update/renewal process after its disposition.

## Truthful answering rule

- answer **Yes** only when current policy/process/technical evidence exists and matches the scope;
- answer **No** when the control is required in WhitePact's role but is not implemented;
- answer **N/A** only when the role/control genuinely does not apply, with a short scope justification;
- where reality is shared responsibility, use the official template's permitted response and state the customer/provider/deployment dependency explicitly;
- never convert a roadmap item into a current control.

## Audit outcome

**Outcome:** suitable to proceed with CSA STAR for AI Level 1 self-assessment preparation, with explicit gaps and shared-responsibility statements.  
**Not an outcome:** certification, independent attestation, or CSA approval.
