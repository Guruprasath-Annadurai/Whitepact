# Governance & Risk Oversight

> This document establishes a real, adoptable process — a recurring
> risk-review cadence a solo maintainer can start immediately, at zero
> cost. It does **not** solve the harder gap underneath it: a named second
> person with actual authority to oversee the person who builds and
> operates this platform. That gap is stated honestly below rather than
> papered over with a policy document alone — a cadence is process, not a
> substitute for a second set of eyes with real standing to say no.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. What this document is for

`compliance/NIST_CSF_SELF_ASSESSMENT.md`'s GOVERN function flags two related
gaps:
- **GV.RM** (risk management strategy): no formal, scheduled risk-review
  cadence — risks get addressed reactively (audit → fix → document) rather
  than via a standing process.
- **GV.OV** (oversight of risk management): no board/exec oversight
  function exists — every decision is made and reviewed by the same
  person.

This document closes the first gap for real: a concrete, scheduled cadence
that starts now. It documents the second gap honestly rather than
fabricating an oversight structure that doesn't exist — see Section 4.

---

## 2. Current structure — stated plainly

Every role below is held by one person as of this version:

| Role | Who | 
|---|---|
| Founder / maintainer | Guruprasath Annadurai |
| Security contact (`SECURITY.md`) | Same person |
| Incident Commander (`compliance/INCIDENT_RESPONSE_RUNBOOK.md`) | Same person |
| Risk owner (this document) | Same person |

This is expected and appropriate at the current stage (pre-funding, solo
founder) — it is not something to hide, and it is exactly the fact a SOC 2
auditor or an enterprise security reviewer will ask about first (see
`compliance/SOC2_READINESS.md` Section 2.1's Governance row). The honest
answer today is "no one but the founder oversees this yet." The cadence
below is what's buildable right now, without waiting for that to change;
Section 4 names what still needs a real second person.

---

## 3. Risk-review cadence

**Quarterly**, starting with the quarter following this document's
adoption (next review: **2026-10-23**, then every 3 months thereafter).

Each review is a written pass over:

1. **Open gaps** — re-read `compliance/CAIQ_SELF_ASSESSMENT.md`,
   `compliance/NIST_CSF_SELF_ASSESSMENT.md`, and
   `compliance/SOC2_READINESS.md`'s gap lists. For each item still open,
   confirm it's still accurate (has anything shipped that closes it?) and
   still correctly prioritized.
2. **New risks** — anything that changed since the last review: new
   dependencies, new features that touch customer data, new
   infrastructure, a near-miss that didn't become a full incident.
3. **Vendor risk** — re-check `compliance/VENDOR_RISK_ASSESSMENT.md`
   against current sub-processors; confirm nothing changed without an
   update (new OCI region, a Stripe feature change, a new LLM provider
   integration).
4. **Incident/tabletop cadence** — per
   `compliance/INCIDENT_RESPONSE_RUNBOOK.md`'s "what this runbook does not
   yet cover" section: is it time for another tabletop drill? A reasonable
   trigger is "a new detection source or response phase was added since
   the last drill" (matching that document's own stated criterion), not a
   fixed interval independent of what actually changed.
5. **Write it down** — a dated entry appended to Section 5 below, even if
   the conclusion is "no material change this quarter." A skipped or
   undocumented review is the same as not having a cadence at all.

This is genuinely buildable today, without budget or a second hire — it's
pure process discipline, the same category of work that moved
`compliance/NIST_CSF_SELF_ASSESSMENT.md`'s Respond function from Partial to
Defined once the incident-response runbook was actually written down.

---

## 4. What this cadence does not fix — stated honestly

A self-review, however disciplined, is still one person checking their own
work — the same limitation `compliance/INTERNAL_SECURITY_REVIEW.md` states
about its own findings relative to a real third-party penetration test.
Two things a quarterly solo cadence cannot substitute for:

- **A named advisor, fractional CISO, or co-founder with actual standing to
  push back.** This is a decision for the founder to make (who, when,
  compensated how) — not something a document or a process can create by
  itself. Until that person exists, treat every review above as
  self-assessment, not independent oversight, in any conversation with an
  enterprise buyer or an auditor.
- **A board or equivalent oversight body**, which `compliance/SOC2_READINESS.md`
  correctly flags as something CC1 (Control Environment) will ask about
  directly. Not applicable at a pre-funding, solo-founder stage — but also
  not something to represent as existing.

**When to revisit this section**: the moment a second person joins with
any operational or advisory role — update this document the same day, not
"eventually." An out-of-date governance document is worse than an honest
gap, because it actively misleads whoever reads it next (a customer's
security reviewer, a future hire, an auditor).

---

## 5. Review log

| Date | Reviewer | Summary |
|---|---|---|
| 2026-07-23 | Guruprasath Annadurai | Initial adoption of this cadence. No prior quarterly review existed before this document. |
