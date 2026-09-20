# WhitePact — CSA STAR Level 1 + STAR for AI Level 1 Readiness Review

**Review date:** 2026-08-27  
**Repository:** `Guruprasath-Annadurai/Whitepact`  
**Target:** STAR Level 1 using CAIQ-Lite v4.1.0; STAR for AI Level 1 using AI-CAIQ v1.1  
**Assessment:** First-party self-assessment/readiness review; not an independent audit.

## Conclusion

WhitePact has substantial technical evidence for first-party STAR submissions: vulnerability disclosure, automated security/dependency/secret scanning, OpenSSF Scorecard, protected-branch required checks, DCO, signed release-tag gating, SBOM generation, build provenance, RBAC, SSO/MFA, tenant isolation, hash-chained audit evidence, incident-response documentation, vendor-risk review, continuity evidence, and explicit control limitations.

The repository is not independently audited. Level 1 answers must preserve honest `No` / `N/A` responses for absent or out-of-scope controls.

The recommended cloud path is **CAIQ-Lite v4.1.0** because CSA accepts CCM/CAIQ-Lite submissions into STAR and positions Lite for smaller/resource-constrained organizations. The AI path is **AI-CAIQ v1.1**.

## Scope

WhitePact is an AI governance/runtime assurance platform with API/dashboard, MCP and agent-integration surfaces, guardrails, evaluation/trust functions, multi-tenant persistence and a hosted reference deployment. It is primarily an AI application/orchestration governance provider, not a foundation-model provider.

The hosted reference deployment relies on managed third parties such as Render, Supabase and Upstash. Provider certifications are inherited/shared evidence only; they are not WhitePact certifications.

## Evidence map

| Area | Evidence | Assessment |
|---|---|---|
| Vulnerability disclosure | `SECURITY.md` | Strong |
| Recurring application security | `.github/workflows/security-scan.yml` (Bandit + pip-audit) | Strong first-party evidence |
| Dependency/secrets | dependency-review, Gitleaks and security workflows | Strong |
| Change/repository governance | CODEOWNERS, PR process, protected `main` requiring status checks, DCO signed-off commits | Strong |
| Supply chain | signed release tag gate, trusted PyPI publishing, CycloneDX SBOM, GitHub provenance attestation | Strong |
| Internal review | `compliance/INTERNAL_SECURITY_REVIEW.md` | Strong self-review; explicitly not pentest |
| IAM | RBAC, OIDC/SAML, SSO enforcement, TOTP MFA | Strong |
| Multi-tenancy | org-scoped data/repository methods | Strong documented implementation |
| Audit | hash-chained audit log plus verify/export endpoints | Strong with stated limitations |
| Vendor risk | `compliance/VENDOR_RISK_ASSESSMENT.md` | Good; fixed cadence added by risk policy |
| Incident response | incident runbook/tabletop evidence | Good |
| Continuity/DR | SLA, backup/restore and continuity evidence | Good for current stage; HA remains limited |
| Data protection | key-management docs, optional field encryption, managed infra encryption | Mixed/shared |
| Independent assurance | None | Open gap |
| AI governance | Product controls + `compliance/AI_GOVERNANCE_POLICY.md` | Good on merge |
| Formal risk management | `compliance/RISK_MANAGEMENT_POLICY.md` | Good on merge |

## Material findings

1. **No independent audit/pentest.** Internal review and automated scans must never be marked as independent assurance.
2. **Protected branch verified.** GitHub blocked a merge attempt because required checks had not succeeded. The DCO check requires `Signed-off-by:` trailers; this compliance branch was rebuilt to satisfy rather than bypass it.
3. **Reference resilience is limited.** Current free-tier deployment has no cross-region failover; recovery/backup controls should not be conflated with HA.
4. **AI role scope matters.** WhitePact does not train foundation models; training-dataset/model-weight controls may be `N/A` with rationale when the question truly presupposes model-provider ownership.
5. **Governance is not sandboxing.** Tool approval/gating does not prove every third-party plugin executes in a hardened OS/container sandbox.
6. **Universal app-layer at-rest encryption is not present.** Reference infrastructure provides managed encryption, while WhitePact itself only applies field encryption selectively/optionally as documented.

## Answer rules

- `Yes`: only when a currently implemented or genuinely inherited/shared control is evidenced.
- `No`: applicable control not implemented.
- `N/A`: genuinely outside WhitePact's role/scope, with a written reason.
- Attribute third-party certifications to the provider.
- Never call internal scans an independent audit/pentest.
- Roadmap/future work is not a current control.
- WhitePact product mappings to NIST/ISO/EU AI Act are product capabilities, not organizational certifications.

## High-confidence themes

**Implemented/Yes where exact question wording matches:** vulnerability disclosure; automated security/dependency testing; API validation/key handling; RBAC/tenant isolation; SSO/MFA; audit evidence/export; version control; required merge checks/DCO; release provenance/SBOM; incident-response procedures; vendor-risk assessment; webhook SSRF validation; retention mechanisms; PII guardrails; approval/redaction/deny/quarantine governance paths.

**No/open where exact question applies:** independent annual audit; independent penetration test; cross-region redundancy; universal application-layer encryption at rest; blanket sandbox isolation for every external tool/plugin.

**Common N/A candidates subject to exact wording:** WhitePact-operated physical datacenter controls; WhitePact-owned foundation-model pre-training; WhitePact-owned model-weight protection/rotation where no such weights exist; training-dataset poisoning/provenance controls for models WhitePact does not train; customer-owned LLM-provider controls beyond WhitePact's integration boundary.

## Final readiness state

| Target | State | External/owner step remaining |
|---|---|---|
| CSA STAR Level 1 — CAIQ-Lite v4.1.0 | Submission-preparation ready with disclosed gaps | Transfer/finalize official workbook, applicant identity/legal attestation, CSA authenticated upload/publication |
| CSA STAR for AI Level 1 — AI-CAIQ v1.1 | Submission-preparation ready with disclosed gaps | Transfer/finalize official workbook, applicant identity/legal attestation, CSA authenticated upload/publication |

Until CSA publishes the assessment in its registry, WhitePact must not claim it **has** STAR Level 1 or STAR for AI Level 1.
