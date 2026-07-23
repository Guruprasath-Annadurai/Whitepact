# Compliance Starter Kit — Pricing & Offer One-Pager

> This is a BD/pricing document for the "sell the methodology, not just the
> product" motion in `STRATEGY_ROADMAP.md` Part 0, Item 4 — the sharpest
> bootstrap move available: get paid to help other companies assess
> themselves before ResponsibleAI has its own SOC2. Like every other
> pricing document in this repo (`compliance/OEM_LICENSING.md`), the
> numbers here are founder-set starting points for a negotiation, not a
> fixed, benchmarked rate card.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. The problem this sells into

Every small AI/software company hits the same wall this project hit: an
enterprise prospect's security review asks for a completed vendor
questionnaire (CAIQ-style) or a NIST CSF self-assessment, and the honest
answer is "we've never written one." Writing one from a blank page takes
days of unfamiliar work; hiring a consultant to write one from scratch
costs thousands and weeks. Most of these companies also can't afford a
real SOC2 audit yet ($10-30K/year) — same constraint this project has,
solved the same way: a rigorous, honest self-assessment first.

**What's being sold**: not a certificate (this project doesn't have one to
sell), but the *methodology and the finished document structure* — proven
by actually being used, in production, on this very project's own real
compliance posture (`compliance/CAIQ_SELF_ASSESSMENT.md`,
`compliance/NIST_CSF_SELF_ASSESSMENT.md`). The credibility claim is
verifiable: point a prospect at those two real documents as the work
sample.

---

## 2. What's included, by tier

| Tier | What you get | Price (starting anchor) |
|---|---|---|
| **Self-serve template** | The two blank templates (`compliance/starter-kit/CAIQ_TEMPLATE.md`, `NIST_CSF_TEMPLATE.md`) plus `scripts/generate_compliance_kit.py` to scaffold them with your company name — free download, no engagement required | **Free** |
| **Guided fill-in (async review)** | You fill in the templates yourself; one round of written feedback flagging vague answers, inflated maturity ratings, or missing evidence citations — the same rigor this project applies to its own docs | **$500-1,500 flat**, one-time |
| **Full consulting engagement** | A structured intake call, the founder (or whoever does this work) interviews you about your actual systems and writes the first draft directly, one revision round included | **$2,500-6,000 flat**, one-time, scoped to CAIQ + NIST CSF together |
| **Ongoing quarterly refresh** | Re-review and update the documents as your systems change — the same discipline `GOVERNANCE.md`'s quarterly cadence applies internally | **$300-800/quarter**, add-on to either paid tier above |

**Why flat-fee, not hourly**: the same reason a lawyer quotes a flat fee
for a will instead of billing hourly for an unfamiliar client — the buyer
wants a predictable number, and the work itself (structured interview +
template) is repeatable enough to price flat once done a few times.

---

## 3. How to actually sell this (mechanics, not just pricing)

1. **Proof-of-work, not a pitch deck**: the strongest sales asset is
   this project's own two real, filled-in documents — send them directly,
   don't describe them. A prospect reading a genuinely honest, detailed
   self-assessment (including its own stated gaps) is a far stronger
   credibility signal than any marketing copy could be.
2. **Target the same segment `compliance/SALES_TARGETING.md` already
   identifies** for the main product — Seed/Series A/B startups and
   mid-market SaaS companies facing their first real vendor security
   review, not enterprises that require SOC2 regardless.
3. **Bundle with the main product where it makes sense**: a company buying
   the compliance starter kit is, by definition, exactly the buyer profile
   for ResponsibleAI's core governance product too (they're building an AI
   product and just discovered they need a compliance story) — this is a
   natural lead-gen funnel into the core product, not just a standalone
   revenue line.
4. **First three customers at a discount, in exchange for a testimonial**
   — the same design-partner logic `STRATEGY_ROADMAP.md` Phase 1 applies
   to the main product, applied here: real proof this works on someone
   else's actual systems is worth more than the discount costs.

---

## 4. What this explicitly does not promise

- **Not a certification** — filling in these templates produces an honest
  self-assessment, the same category of document
  `compliance/CAIQ_SELF_ASSESSMENT.md` is, not a SOC2/ISO 27001 report. Say
  this plainly to every buyer; overselling this as "compliance
  certification" would be the exact kind of fabrication this project's own
  compliance work has consistently refused to do.
- **Not legal advice** — if a buyer's specific regulatory obligations
  (HIPAA, PCI, a specific state privacy law) require more than an honest
  security-posture self-assessment, say so and refer them to counsel,
  don't stretch this product to cover ground it doesn't.

---

## 5. Before taking a real payment for this

1. Have a simple engagement agreement ready (even a one-page scope-of-work
   email exchange is fine for the first few customers) — don't take money
   with zero written scope, for both parties' protection.
2. Re-verify Section 2's pricing against what actually closes — update
   this document the first time a real deal lands somewhere different,
   the same honesty discipline every other pricing anchor in this repo
   (`compliance/OEM_LICENSING.md` Section 4) already commits to.
3. Confirm `scripts/generate_compliance_kit.py` and the two templates in
   `compliance/starter-kit/` still match this document's description
   before quoting anyone — check the code, not just this page.
