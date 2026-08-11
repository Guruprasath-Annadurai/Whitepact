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
   update (a hosting vendor's region/terms change, a Stripe feature change, a new LLM provider
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

---

## 6. Project decision-making and open source contribution

Sections 1-5 above cover *risk* oversight. This section covers the
separate, narrower question of how day-to-day open source contribution
and code-change decisions work — added as part of
`MIGRATION_WHITEPACT_V2.md` Phase 18 (open source governance).

- **Model**: founder-led, same single-person structure as Section 2 —
  Guruprasath Annadurai
  ([@Guruprasath-Annadurai](https://github.com/Guruprasath-Annadurai))
  has final say on what merges and when. No steering committee, core
  team, or maintainer council exists today. `.github/CODEOWNERS`
  reflects this directly (one name, not invented team handles), for
  the same reason Section 2 states every role plainly rather than
  implying a team that doesn't exist.
- **Code changes**: reviewed and merged at the founder's discretion —
  see `CONTRIBUTING.md` for the mechanics of proposing one (fork, PR,
  tests, style).
- **Architecture and roadmap**: `SPEC.md` is the current architecture
  contract; `MIGRATION_WHITEPACT_V2.md` is the active migration plan.
  Both are living documents, updated as decisions are made, not voted on.
- **Releases**: `RELEASING.md` documents the actual mechanical
  process; what ships in a given version is a founder decision.
- **Becoming a contributor**: anyone can contribute (see
  `CONTRIBUTING.md`). Contributing doesn't itself confer commit
  access, a title, or decision-making authority — there's no formal
  path to "maintainer" defined here today, for the same
  don't-invent-process-before-it's-needed reason as everywhere else in
  this document.
- **Code of Conduct**: see `CODE_OF_CONDUCT.md`. Enforcement is the
  founder's responsibility today, for the same reason Section 4 states
  there's no separate oversight body yet.

Like Sections 1-5, this section describes what's actually true today,
not a permanent commitment. If the project grows a real set of
regular, trusted contributors, a more distributed model may follow —
written here once it's actually true, not announced ahead of it.
