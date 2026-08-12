# The honest, no-budget path to enterprise trust — without a SOC 2 report

Last reviewed: 2026-08-12 · Author: Guruprasath Annadurai

**Why this document exists**: a real SOC 2 Type I/II report requires an
independent, AICPA-accredited CPA firm and typically costs real money
even at the cheapest end of the market — real 2026 pricing researched
for this document: Zero Day CPA from ~$5K fixed, Sprinto/Drata/
Secureframe/Scytale in the ~$6-7.5K/yr range for compliance-automation
platforms bundled with an auditor, a DIY-plus-budget-auditor approach
at $15-30K, and lean SOC 2 Type I engagements generally landing $10-50K
([SOC 2 Auditors for Startups (2026)](https://soc2auditors.org/soc-2-auditors-startups/),
[SOC 2 Costs for Startups](https://www.startupdefense.io/soc-2-costs-for-startups-complete-breakdown-and-budget-guide)).
None of that is available right now. This document is what's actually
buildable at **zero cost**, stated honestly — not a claim that any of
it is equivalent to SOC 2, because it isn't, and pretending otherwise
to an enterprise buyer would violate this project's own
never-fabricate rule.

**The one non-negotiable rule for using any of this**: never describe
anything below as "SOC 2 compliant," "SOC 2 certified," or "audited."
It isn't. What it is: real, independently verifiable, free evidence
that a security-conscious buyer can check themselves, today, without
waiting on us.

---

## What's real and free, already built or built today

| Signal | What it proves | Cost | Status |
|---|---|---|---|
| [OpenSSF Scorecard](https://scorecard.dev) | Automated, third-party-run security-practice scoring (branch protection, code review, dependency pinning, vulnerability response, etc.) — the same metric [CISA](https://www.cisa.gov/resources-tools/services/openssf-scorecard) and major cloud providers reference | Free, forever | **Added today** — `.github/workflows/scorecard.yml`, weekly + on-push, results published to the public Scorecard API and linked from the README badge |
| CycloneDX SBOM + Sigstore provenance attestation | Exactly what's in every release, cryptographically signed proof of what built it | Free (already CI infrastructure) | Already shipping — `RELEASING.md`, Phase 15 |
| `dependency-review.yml` | Every PR's new/changed dependencies checked for known vulnerabilities and license compliance before merge | Free (GitHub Actions) | Already shipping |
| Branch protection on `main` | Required CI checks before any pull request can merge, no force-push, no deletion | Free (GitHub) | **Enabled today** |
| `THREAT_MODEL.md` | A real STRIDE-structured threat model against the actual current attack surface, not a template | Free (this session's work) | Already shipping |
| `compliance/CAIQ_SELF_ASSESSMENT.md` | A completed Consensus Assessments Initiative Questionnaire — the same question set CSA STAR Level 1 asks for | Free | Already shipping |
| `compliance/NIST_CSF_SELF_ASSESSMENT.md` | NIST Cybersecurity Framework maturity self-rating by function | Free | Already shipping |
| `compliance/INTERNAL_SECURITY_REVIEW.md`, `compliance/INCIDENT_RESPONSE_RUNBOOK.md` | Documented internal security process | Free | Already shipping |

## CSA STAR Registry, Level 1 — **submitted 2026-08-12**

Level 1 self-assessment is free to submit and free to maintain — an
organization completes the CAIQ and submits it for publication on the
[STAR Registry](https://cloudsecurityalliance.org/star/registry), no
fee for submission or listing, annual update required to stay current
([CSA STAR overview](https://hyperproof.io/csa-star/),
[CSA STAR Level 1 vs Level 2](https://atlantsecurity.com/blog/csa-star-level-1-vs-level-2-key-differences)).
The completed CAIQ v4.0.3 (`compliance/CAIQv4.0.3_WhitePact_completed.xlsx`,
`scripts/caiq_answers.py`) was submitted through the founder's own CSA
account via the STAR submission portal (`star.watch`) as a Self
Assessment, Service Category: SaaS. As of 2026-08-12 the submission
status shows **Email Confirmed → Approved by Organization → Pending
CSA Approval** — everything on the founder's side is complete; it now
sits in CSA's own review queue with no fixed published SLA. Check
[cloudsecurityalliance.org/star/registry](https://cloudsecurityalliance.org/star/registry)
periodically for "WhitePact" to appear, and watch the account email for
any CSA follow-up. Do not describe this as "SOC 2 compliant" or
"audited" — it is a self-assessment, and should be described that way
to buyers, same as every other signal on this page.

**Open item**: the Backup Point of Contact on the submission form was
filled with the founder's own second email, since there is currently no
second person with real oversight authority (see
`FOUNDER_ACTION_CHECKLIST.md` Section 10 and `GOVERNANCE.md`) — revisit
via CSA's edit/update flow once a real second contact exists.

## What none of this replaces

- A named second person with actual standing to push back on security
  decisions — `GOVERNANCE.md` Section 4 states this plainly; no
  document or automated scan substitutes for it.
- Independent penetration testing.
- The specific, evidence-over-time assurance a real SOC 2 Type II
  report gives (continuous operating effectiveness over a 3-12 month
  observation window, examined by an independent CPA firm) — a
  point-in-time self-assessment, however honest, is a different kind
  of claim and should never be presented as equivalent.

## When there's budget again

Revisit the pricing table above — Zero Day CPA (~$5K) or a bundled
platform like Sprinto/Drata/Secureframe (~$6-7.5K/yr) are the
cheapest real entry points researched for this document, both citations
above. `SOC2_READINESS.md` already maps every AICPA Trust Services
Criteria control against current reality, so whichever firm is engaged
starts from a known gap list instead of discovering it mid-audit —
that prep work is what actually shortens (and cheapens) a real
engagement.
