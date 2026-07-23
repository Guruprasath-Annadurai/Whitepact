# Scope Brief for Attorney Review — DPA Template

Hand this to whoever reviews `compliance/DPA_TEMPLATE.md` (flat-fee legal
service, solo attorney, law clinic) so they don't have to read the whole
document cold. It tells them exactly what's real, what's a placeholder,
and what one decision they need from you before they can start.

---

## The one thing to decide before the call

**Which jurisdiction/regime matters most for your first real customers?**

This changes what the attorney should focus on — don't book the call
without an answer:

- **EU/UK customers likely** → GDPR is the controlling regime. Standard
  Contractual Clauses, the 72-hour breach notification requirement, and
  data subject rights timelines all need GDPR-specific language.
- **US-only customers, no EU/UK** → CCPA/CPRA (if any California
  customers) or a general US commercial DPA baseline otherwise — lighter
  requirements than GDPR, cheaper to review.
- **Mixed/unsure** → say so; the attorney can draft dual-regime language,
  but it costs more and takes longer. Don't guess — if you don't know yet,
  tell them "unsure, first customers likely North American, may expand to
  EU later" and let them scope accordingly.

---

## What's already done (don't pay to have this re-derived)

- Full sub-processor list with purpose, data processed, location, and
  certifications for each (Section 2) — Render, Supabase, and Upstash
  (updated 2026-07-23, the actual live infrastructure vendors as of this
  date), Stripe, customer's own OIDC provider, customer's own LLM
  provider choices. This is factual and current as of 2026-07-23, cited
  to live sources (each vendor's own published compliance page for their
  SOC 2/ISO 27001 status). The attorney doesn't need to research or
  verify these facts — just confirm the *legal framing* around them
  (e.g., is "sub-processor" the right term for the customer's-own-IdP and
  LLM-provider rows, or should those be reframed as something else since
  we don't select or contract with
  them on the customer's behalf).
- Security measures description (Section 5) — references real, verified
  documentation (`ENTERPRISE_SECURITY.md`, the CAIQ and NIST CSF
  self-assessments). Honest about what's *not* certified (no SOC2/ISO
  27001 of our own) — that statement is intentional, not an oversight to
  "fix."
- Scope/parties framing (Section 1) — correctly distinguishes self-hosted
  deployments (where we process none of the customer's data) from a
  future hosted tier (which doesn't exist yet). Confirm this distinction
  holds up legally, but the underlying facts are accurate.

---

## What's a placeholder — these are the actual billable work

| Section | What's missing | Why it needs an attorney, not us |
|---|---|---|
| §6 — Data subject rights assistance | No committed timeline or cost allocation for handling access/deletion/portability requests | Varies by regime (GDPR gives data subjects a right to a timely response; exact "reasonable" timeframe is a legal judgment call) |
| §7 — Breach notification | No committed notification timeframe to the customer | GDPR implies notifying the supervisory authority within 72 hours of *awareness* — whether/how that flows into a customer-facing SLA is a legal decision. An internal process exists (`INCIDENT_RESPONSE_RUNBOOK.md`) and has been through one tabletop drill (`compliance/TABLETOP_EXERCISE_2026-07-21.md`), but not a real production incident (see caveat below) — don't let a committed number get drafted ahead of that proof |
| §8 — International data transfers | No transfer mechanism specified (Standard Contractual Clauses, adequacy decision, etc.) | Only relevant if you'll have EU/UK customers — see the jurisdiction question above. If US-only for now, tell the attorney this section may not need much work yet |
| §10 — Liability | Entirely blank — no caps, no indemnification language | Depends on actual contract value, any insurance coverage you hold (probably none yet), and jurisdiction. This is the section most likely to actually cost attorney time — flag it as the priority item |

---

## One thing to disclose to the attorney directly, not just imply

An internal incident-response runbook now exists
(`compliance/INCIDENT_RESPONSE_RUNBOOK.md` — detect → triage → contain →
eradicate → recover → notify → post-incident review) and has been through
one tabletop drill (`compliance/TABLETOP_EXERCISE_2026-07-21.md`, which
found and fixed two real gaps), but it has **not been tested against a
real production incident**. That's a meaningful distinction to give the
attorney: "drilled once" is better than "never tested," but is still not
the same as "proven to work under pressure with a real customer affected."

**Don't let the attorney draft a breach-notification clause with a
specific numeric commitment (e.g., "within 24 hours") based solely on the
existence of this runbook.** The runbook's own Phase 5 deliberately avoids
committing to a specific timeframe for exactly this reason — it describes
the *process* for deciding whether/how to notify, not a legal SLA. Either:
(a) run a tabletop exercise first to build confidence in an actual number, or
(b) have the attorney draft looser language ("without undue delay")
until that confidence exists, and tighten it once a real drill (or,
unfortunately, a real incident) proves the process works within a
specific timeframe.

Signing a specific SLA you can't operationally meet is worse than an
honest, looser commitment — say this to the attorney explicitly so they
don't over-promise on your behalf by default.

---

## Format note

`DPA_TEMPLATE.md` is a markdown file, not a Word doc or PDF. Ask the
attorney if they want it converted to `.docx` for tracked-changes redlining
— trivial to do, just say the word, don't assume they'll want markdown.

---

## What "done" looks like

A redlined version of `DPA_TEMPLATE.md` (or its `.docx` conversion) with:
- Sections 6, 7, 8, 10 filled in with real, jurisdiction-appropriate terms
- Any legal-framing corrections to Sections 1–5 (facts stay, wording may change)
- The giant "not reviewed by counsel" warning banner at the top removed
  or replaced with an actual review date and the attorney's confirmation

Until all of that is true, keep treating this as a draft — including
telling prospects it's a draft if it comes up before the review is done.
