# WhitePact Risk Management Policy

**Status:** Effective when merged to `main`  
**Owner:** WhitePact maintainer / service owner  
**Initial approval date:** 2026-08-27  
**Review cadence:** At least quarterly and on significant change

## 1. Purpose

This policy establishes the formal process WhitePact uses to identify, evaluate, treat, accept, monitor, and document security, privacy, operational, supply-chain, and AI-specific risks. It is intentionally lightweight for a solo-maintained project, but it is a real operating policy rather than an aspirational certification claim.

This policy does **not** represent an independent audit, SOC 2 report, ISO certification, penetration test, or CSA STAR designation. Those claims may only be made when independently or externally obtained as applicable.

## 2. Scope

The process applies to:

- the WhitePact source repository and release pipeline;
- the hosted reference deployment and its managed infrastructure vendors;
- authentication, authorization, secrets, audit logging, multi-tenancy, billing, webhooks, MCP and API surfaces;
- dependencies, build and release provenance, SBOMs, GitHub Actions, package publication and third-party services;
- AI/agent governance controls, prompt/input handling, PII handling, tool/action decisions, approval gates, model-provider dependencies, and AI-generated outputs processed by WhitePact;
- customer data and metadata processed by WhitePact.

## 3. Roles and accountability

At the current team size, the sole maintainer is the risk owner, control owner, and approval authority. This concentration of duties is documented as a structural limitation and must be revisited when additional privileged personnel join.

The owner must not describe a self-review as an independent assessment. Independent assurance remains a separate control and gap.

## 4. Risk assessment method

Each identified risk is recorded with:

1. **Asset / process** affected.
2. **Threat or failure mode**.
3. **Likelihood**: Low / Medium / High.
4. **Impact**: Low / Medium / High / Critical.
5. **Inherent risk** before controls.
6. **Existing controls and evidence**.
7. **Residual risk** after controls.
8. **Treatment**: Mitigate / Avoid / Transfer / Accept.
9. **Owner**.
10. **Target date** when remediation is required.
11. **Status and review date**.

### Risk rating

- **Critical:** credible path to severe compromise, safety failure, regulatory exposure, or widespread customer impact. Immediate treatment or service restriction is required.
- **High:** material confidentiality, integrity, availability, authorization, AI-safety, or supply-chain impact. Prioritize ahead of normal feature work.
- **Medium:** meaningful but bounded risk with compensating controls.
- **Low:** limited impact or low likelihood; monitor and address opportunistically.

## 5. Review triggers

A risk review is required:

- at least once per quarter;
- before or immediately after a material architecture change;
- when a new infrastructure, payment, identity, AI/model, analytics, or data-processing vendor is introduced;
- when a new privileged integration, MCP tool, agent action, webhook, or externally reachable API is added;
- after a security incident or confirmed vulnerability;
- after a Critical/High dependency advisory affecting shipped components;
- after a significant regulatory or contractual requirement change;
- before making a new public compliance/security claim.

## 6. Vulnerability and finding treatment

Security findings are tracked to closure or documented acceptance. Critical and High findings take priority over feature development when exploitation could materially affect customers or the service. Automated scans complement, but do not replace, independent testing.

Evidence includes Git history, issues/PRs, CI results, security scan artifacts, `SECURITY.md`, `compliance/INTERNAL_SECURITY_REVIEW.md`, `compliance/VENDOR_RISK_ASSESSMENT.md`, the incident-response runbook, and release attestations.

## 7. Initial risk register — 2026-08-27

| ID | Risk | Residual rating | Current treatment / evidence | Status |
|---|---|---|---|---|
| RM-001 | No independent penetration test or independent annual assurance | High | Internal Bandit/pip-audit/manual review exists and is explicitly non-independent; do not misrepresent it | Accepted temporarily / funding dependent |
| RM-002 | GitHub classic branch-protection configuration could not be independently verified through the connected integration; no repository rulesets were visible during the 2026-08-27 review | Medium | CI, CODEOWNERS, dependency review, Gitleaks, Scorecard and security workflows exist; owner should verify protected-branch settings directly | Open verification item |
| RM-003 | Reference deployment uses single free-tier Render/Supabase/Upstash services without cross-region failover | High | Documented in CAIQ/vendor-risk/continuity evidence; appropriate only for early-stage/reference service | Accepted for current stage |
| RM-004 | Upstash independent certification status was not verified in the existing vendor review | Low | Stores rate-limit counters only; no governance data/PII intended | Monitor |
| RM-005 | Vendor-risk review previously had no scheduled cadence | Medium | This policy establishes quarterly + change-triggered review | Mitigated on merge |
| RM-006 | Prompt injection / adversarial AI input could attempt to manipulate tool or governance behavior | High | WhitePact decision engine, input scanning/guardrails, approval/redaction/quarantine outcomes, RBAC and audit evidence; AI policy adds explicit review requirement | Mitigated / continuously tested |
| RM-007 | AI-provider or customer-configured model behavior may be non-deterministic or unsafe | Medium | Customer/provider responsibility is separated; WhitePact evaluates/governs rather than training foundation models; require bounded actions and approval where policy demands | Mitigated / shared |
| RM-008 | Secrets or credentials exposed through source/deployment | High | Environment-based secrets, hashed API keys, Gitleaks, trusted PyPI publishing, signed tag gate, least-privilege workflow permissions | Mitigated |
| RM-009 | Software supply-chain compromise | High | Dependency review, pip-audit, signed release tags, CycloneDX SBOM, GitHub build provenance attestations, PyPI trusted publishing | Mitigated |
| RM-010 | Solo-maintainer concentration of duties and continuity risk | Medium | Project continuity plan, version-controlled evidence, automated CI/release controls; revisit when team grows | Accepted / monitored |

## 8. Risk acceptance

Only the service owner may accept residual risk at the current team size. A High or Critical risk may not be described as “resolved” unless its treatment is implemented and evidence exists. Acceptance must state the reason, duration/trigger for reconsideration, and compensating controls.

## 9. Evidence retention

Risk decisions and remediation evidence should remain version-controlled where safe. Secrets, credentials, customer data, and sensitive incident data must never be committed merely to satisfy evidence requirements.

## 10. Review record

| Date | Reviewer | Outcome |
|---|---|---|
| 2026-08-27 | WhitePact maintainer | Initial policy and risk register created for current CSA STAR / STAR for AI readiness work. |
