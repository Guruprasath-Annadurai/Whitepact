# Compliance Starter Kit — Scope of Work

> Fill-in-the-blank scope-of-work for the paid tiers described in
> `compliance/COMPLIANCE_STARTER_KIT_OFFER.md`. This is what
> `FOUNDER_ACTION_CHECKLIST.md` Section 3 means by "have a simple
> one-page scope-of-work ready before taking a real payment" — send this
> (filled in, as an email or attached doc) to a prospect *before* they
> pay anything, get their written agreement (a reply confirming the
> terms is enough for the first few customers — no need for a lawyer-
> drafted contract at this stage), and keep the exchange for your own
> records. Not legal advice; if a specific deal needs more protection
> than this, get an actual contract reviewed by counsel instead of
> stretching this template to cover it.

---

## 1. Parties and date

**Provider**: [Your name / WhitePact]
**Client**: [Client company name]
**Date**: [Date]
**Engagement tier** (pick one — pricing anchors from
`compliance/COMPLIANCE_STARTER_KIT_OFFER.md` Section 2, adjust to what
actually closes):

- [ ] Guided fill-in (async review) — **$[500-1,500] flat**
- [ ] Full consulting engagement — **$[2,500-6,000] flat**
- [ ] + Ongoing quarterly refresh add-on — **$[300-800]/quarter**

## 2. What Client receives

Two filled-in self-assessment documents, structured the same way this
project's own real, public documents are —
`compliance/CAIQ_SELF_ASSESSMENT.md` and
`compliance/NIST_CSF_SELF_ASSESSMENT.md` are the actual work sample;
point the client at them before they sign, not just this scope:

1. **CAIQ-style self-assessment** — modeled on the Cloud Security
   Alliance's Consensus Assessment Initiative Questionnaire domain
   structure (not a copy of CSA's proprietary question text).
2. **NIST CSF self-assessment** — mapped to the NIST Cybersecurity
   Framework's function/category structure.

Both documents are scaffolded from
`compliance/starter-kit/CAIQ_TEMPLATE.md` and `NIST_CSF_TEMPLATE.md`
via `scripts/generate_compliance_kit.py`, then filled in with Client's
own real, specific facts — never generic or fabricated answers. Every
control is answered as either a true, citable fact (a config value, a
documented process, a file/policy reference) or an honestly disclosed
gap ("Not implemented, planned for Q[X]"). A vague or evasive answer is
treated as worse than an honest gap — see the template's own header
for why.

## 3. What Client does not receive (say this before they pay, not after)

- **Not a certification.** This produces an honest self-assessment, the
  same category of document `compliance/CAIQ_SELF_ASSESSMENT.md` is —
  not a SOC2 report, not an ISO 27001 certificate, not any third-party
  attestation. Do not represent it as one to Client's own customers or
  investors.
- **Not legal advice.** If Client's specific regulatory obligations
  (HIPAA, PCI, a specific state privacy law, GDPR/CCPA specifics) need
  more than an honest security-posture self-assessment, say so plainly
  and refer them to counsel — don't stretch this engagement to cover
  ground it doesn't.
- **Not an audit of Client's actual security posture.** The answers
  reflect what Client's team reports and what the interview/review
  surfaces — this engagement does not independently verify Client's
  systems (e.g., no penetration test, no code review of Client's
  codebase).

## 4. Process (fill in per tier)

**Guided fill-in (async review):**
1. Client fills in both templates themselves using their own systems
   knowledge.
2. Provider does one round of written feedback: flags vague answers,
   inflated maturity ratings, and missing evidence citations — the
   same rigor applied to this project's own documents.
3. Client incorporates feedback. Engagement ends — no additional
   review rounds included at this tier.

**Full consulting engagement:**
1. **Intake call** ([duration, e.g. 60–90 min]): Provider interviews
   Client about their actual systems, data handling, and existing
   security controls.
2. **First draft**: Provider writes the first draft of both documents
   directly from the interview and any materials Client shares.
3. **One revision round**: Client reviews, flags corrections/gaps,
   Provider incorporates them.
4. Engagement ends after the revision round — further changes are a
   new engagement or fall under the quarterly refresh add-on.

## 5. Timeline

[Fill in — the outreach email drafted in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 2 tells
prospects "about a week instead of from scratch"; don't commit to a
firmer number than you can actually deliver on your first few real
engagements, and update this template once you know your real
turnaround.]

## 6. Payment terms

[Fill in — e.g., "50% on engagement start, 50% on delivery of first
draft" or "full payment on completion." Confirm your own payment
collection method (invoice, Stripe, etc.) works before promising a
specific mechanism to the client.]

## 7. Confidentiality

Provider will not share Client's specific answers, systems details, or
identity as a client without Client's written permission. [Add a
one-line mutual NDA reference here if a specific deal needs one — most
early engagements can run without a separate NDA if this line is
enough for the client.]

## 8. Client sign-off

By replying to confirm, Client agrees to the scope, tier, and pricing
above. [Provider name] will begin work on [date] after
[first-payment/deposit] terms above are met.

---

*Before sending this to a real prospect: re-verify
`scripts/generate_compliance_kit.py` and the two templates in
`compliance/starter-kit/` still match this document's description —
check the code, not just this page (per
`compliance/COMPLIANCE_STARTER_KIT_OFFER.md` Section 5). Update the
pricing anchors in Section 1 and this file together the first time a
real deal closes at a different number.*
