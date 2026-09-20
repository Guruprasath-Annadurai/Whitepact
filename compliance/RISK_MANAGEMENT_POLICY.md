# WhitePact Risk Management Policy

**Status:** Effective when merged to `main`  
**Owner:** WhitePact maintainer / service owner  
**Initial approval date:** 2026-08-27  
**Review cadence:** At least quarterly and on significant change

## Purpose and scope

WhitePact formally identifies, evaluates, treats, accepts, monitors, and documents security, privacy, operational, supply-chain, vendor, and AI-specific risks affecting the source repository, release pipeline, hosted reference deployment, APIs/MCP/agent integrations, customer data, and third-party services.

This policy is first-party governance evidence. It is not an independent audit, penetration test, SOC 2 report, ISO certification, or CSA STAR designation.

## Accountability

At the current team size, the sole maintainer is the risk owner, control owner, and approval authority. This concentration of duties is itself monitored as a risk and must be revisited when additional privileged personnel join. Self-review must never be described as independent assurance.

## Risk method

Every material risk is recorded with: asset/process, threat or failure mode, likelihood, impact, inherent risk, existing controls/evidence, residual risk, treatment (mitigate/avoid/transfer/accept), owner, target date, status, and review date.

Risk ratings: **Critical** (immediate treatment/service restriction), **High** (priority over normal feature work), **Medium** (meaningful but bounded with compensating controls), **Low** (limited impact/likelihood; monitor).

## Mandatory review triggers

Review at least quarterly and additionally on: material architecture changes; new infrastructure/payment/identity/AI/data vendors; new privileged MCP/tool/agent actions; externally reachable API changes; security incidents; Critical/High dependency findings; major regulatory/contract changes; and before new public compliance claims.

## Initial risk register — 2026-08-27

| ID | Risk | Residual rating | Treatment / evidence | Status |
|---|---|---|---|---|
| RM-001 | No independent penetration test or independent annual assurance | High | Recurring Bandit/pip-audit and internal manual review exist but are explicitly non-independent | Temporarily accepted / funding dependent |
| RM-002 | Protected-branch changes depend on required CI/DCO checks | Low | Verified during this review: GitHub refused PR merge while required status checks were pending/failing; DCO requires signed-off commits | Implemented control |
| RM-003 | Reference deployment uses single free-tier Render/Supabase/Upstash services without cross-region failover | High | Disclosed in CAIQ/vendor-risk/continuity evidence | Accepted for current reference stage |
| RM-004 | Upstash independent certification status not verified in existing vendor review | Low | Intended data limited to rate-limit counters | Monitor |
| RM-005 | Vendor/risk review previously lacked a fixed cadence | Medium | This policy establishes quarterly + change-triggered review | Mitigated on merge |
| RM-006 | Prompt injection/adversarial AI input could manipulate tool or governance behavior | High | Guardrails, decision outcomes, approval/redaction/quarantine, RBAC, audit and AI governance policy | Mitigated / continuous testing |
| RM-007 | External/customer model behavior may be unsafe or non-deterministic | Medium | WhitePact governs/evaluates rather than training foundation models; shared responsibility and approval boundaries documented | Mitigated / shared |
| RM-008 | Secret/credential exposure | High | Environment secrets, hashed API keys, Gitleaks, least-privilege workflows, trusted publishing | Mitigated |
| RM-009 | Software supply-chain compromise | High | Dependency review, pip-audit, signed release tags, CycloneDX SBOM, build provenance, PyPI trusted publishing | Mitigated |
| RM-010 | Solo-maintainer continuity / separation-of-duties limitation | Medium | Project continuity documentation and automated controls; reassess when team grows | Accepted / monitored |

## Vulnerability and finding treatment

Security findings are tracked to closure or documented acceptance. Critical and High findings take priority where exploitation could materially affect customers or the service. Evidence may include Git history, PRs/issues, CI results, security-scan artifacts, `SECURITY.md`, `compliance/INTERNAL_SECURITY_REVIEW.md`, `compliance/VENDOR_RISK_ASSESSMENT.md`, incident-response evidence, and release attestations.

## Risk acceptance and evidence retention

Only the service owner may accept residual risk at the current team size. High/Critical risks may not be called resolved without implemented evidence. Risk evidence should be version-controlled where safe; secrets, credentials, customer data, and sensitive incident data must never be committed merely to satisfy evidence requirements.

## Review record

| Date | Reviewer | Outcome |
|---|---|---|
| 2026-08-27 | WhitePact maintainer | Initial formal policy and risk register created for CSA STAR / STAR for AI readiness. |
