# Founder Action Checklist

> Every item below requires the founder personally — an account creation,
> an external submission, a real conversation, or a legal/financial
> decision — none of which Claude can do on your behalf (see this
> project's standing policy against creating accounts or executing
> financial actions for you). This consolidates every such item flagged
> across `STRATEGY_ROADMAP.md`, `compliance/MCP_DISTRIBUTION_GUIDE.md`,
> `compliance/OEM_LICENSING.md`, `compliance/COMPLIANCE_STARTER_KIT_OFFER.md`,
> `compliance/INSURANCE_PARTNERSHIP_PITCH.md`,
> `compliance/TRUST_INDEX_PAPER.md`, `compliance/SOC2_READINESS.md`,
> `compliance/INTERNAL_SECURITY_REVIEW.md`, `DEPLOY_RUNBOOK.md`, and the
> legal drafts — one place to work through, instead of six documents.
>
> Nothing here is ordered by urgency for you specifically — work top to
> bottom or pick whatever's cheapest/fastest for your own situation.
> Check items off in this file directly as you complete them; it's a
> tracker, not a one-time read.

Last reviewed: 2026-07-23

---

## 1. MCP distribution (zero cost — founder time only)

*Source: `compliance/MCP_DISTRIBUTION_GUIDE.md`*

- [ ] Submit `responsibleai-mcp` to the official MCP registry —
      **confirmed live**: `github.com/modelcontextprotocol/registry`
      (real, found via research 2026-07-23; publishes via a `server.json`
      manifest and a CLI publisher tool the repo documents). Note: your
      GitHub CLI is already authenticated as `Guruprasath-Annadurai` — say
      the word and this PR can be opened for you; otherwise it's a normal
      PR flow you do yourself.
- [ ] Submit to community MCP directories/marketplaces (Glama, PulseMCP,
      or whatever's current — search fresh, don't trust any fixed list).
- [ ] Submit to Smithery or an equivalent MCP hosting/discovery platform,
      if one is current.
- [ ] Add a "Listed on [Directory]" badge to the README once accepted
      anywhere.
- [ ] Write a short launch post (blog, LinkedIn, "Show HN" if applicable)
      timed to the first directory acceptance.
- [ ] Check OpenAI's current developer docs for ChatGPT connector/MCP
      registration process (moves fast — verify before acting).
- [ ] Check Google's current Gemini API / Gemini Enterprise docs for
      connector/MCP registration process (same caveat).

## 2. OEM/white-label outreach (zero cost — founder time only)

*Source: `compliance/OEM_LICENSING.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 1*

- [ ] Identify 5-10 named agent-platform startups as OEM prospects.
- [ ] Fill in and send the drafted outreach email to each — content is
      ready, recipient research and sending are yours.
- [ ] Have an actual OEM license agreement drafted by an attorney before
      any real deal closes — the one-pager is a conversation starter only.
- [ ] Update Section 4's pricing anchors once a real deal closes somewhere
      different from the starting numbers.

## 3. Compliance starter kit sales (zero cost to start)

*Source: `compliance/COMPLIANCE_STARTER_KIT_OFFER.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 2*

- [ ] Quote the starter kit to 3 companies in your own network first, at a
      founding-customer discount, before publishing any public price.
- [ ] Have a simple one-page scope-of-work ready before taking a real
      payment (even an email exchange is fine for the first few).
- [ ] Update the pricing table once a real engagement closes at a
      different number.

## 4. Insurance/underwriting outreach (one afternoon, long-shot)

*Source: `compliance/INSURANCE_PARTNERSHIP_PITCH.md`, draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md` Section 3*

- [ ] Two real, named candidates found 2026-07-23: **AIUC** (Artificial
      Intelligence Underwriting Company — SF-based, AIUC-1 audit standard
      + Beazley-backed liability coverage; frame as complementary, not
      competing) and **Testudo** (Lloyd's-backed MGA, $10M-$10B revenue
      mid-market focus — likely too large a customer profile to be your
      own prospect, but worth a direct data-partnership pitch anyway).
      Find current contact channels on `aiuc.com` and Testudo's site.
- [ ] Search for additional current candidates beyond these two — this
      market kept expanding through 2026.
- [ ] Fill in and send the drafted email to 2-3 targets.
- [ ] Get any real interest confirmed in writing before treating it as a
      partnership or announcing it publicly.

## 5. arXiv publication

*Source: `compliance/TRUST_INDEX_PAPER.md`*

- [ ] Convert the Markdown draft to LaTeX (or a pandoc-generated PDF, if
      your target category accepts it — verify current arXiv format
      requirements first).
- [ ] **Confirmed as of arXiv's 2026-01-21 policy update**: an
      institutional email alone no longer qualifies a first-time
      submitter. Without prior authorship on an already-accepted paper in
      `cs.AI`/`cs.CY`, you need a personal endorser (advisor, colleague, or
      existing arXiv author with endorsement privileges) — identify and
      confirm that person *before* starting the submission.
- [ ] Replace every placeholder reference in the paper's References section
      with real, correctly formatted citations.
- [ ] Get a second, ideally domain-expert, reader to review the paper
      before submitting — this was written by the same team that built the
      system it describes.
- [ ] Re-verify every code file reference in the paper against the current
      codebase immediately before submission.
- [ ] Create an arXiv account and actually submit.

## 6. Hosted instance — **DONE, live as of 2026-07-23**

*Source: `DEPLOY_RUNBOOK.md`, `SLA.md`, `STRATEGY_ROADMAP.md` Part 0*

The plan below (GCP VM + Docker Compose) turned out not to be what
actually got built — GCP's billing setup hit real friction (UPI payment
failures), so the founder pivoted to a card-free managed-services stack
instead. What's actually live:

- [x] **Compute**: Render free-tier web service (`responsibleai-dashboard`),
      auto-deploying `Dockerfile` from `main` on every push. Live at
      `https://responsibleai-dashboard.onrender.com`.
- [x] **Database**: Supabase managed Postgres, accessed via its
      transaction-mode pooler (the direct host is IPv6-only and
      unreachable from Render — fixed by using the pooler + a
      `statement_cache_size=0` fix in both `db/engine.py` and
      `migrations/env.py`).
- [x] **Rate-limit backend**: Upstash managed Redis, replacing the
      in-memory limiter (`rate_limit_backend: redis` confirmed via
      `/api/health`).
- [x] Migrations applied, first real org + OWNER key created, bootstrap
      key retired — confirmed to survive a redeploy (proving persistence
      actually works, not just configured).
- [ ] Register or point a real domain/subdomain at the Render service
      (currently only reachable at its `.onrender.com` URL).
- [ ] Set up a public status page (statuspage.io or equivalent) and link
      it from `SLA.md`.
- [ ] **Now that this is genuinely live**, go back and remove/update the
      "no hosted instance is live yet" caveat in `SLA.md`,
      `TERMS_OF_SERVICE.md`, and `PRIVACY_POLICY.md` — this is now
      inaccurate as written and should reflect the real (free-tier,
      no-custom-domain-yet) status rather than either overclaiming or
      leaving the old "doesn't exist" language standing.
- [ ] **Abandoned**: the GCP project (`responsible-ai-503312`) — either
      delete it to avoid any future billing surprise, or keep it as a
      dormant sandbox; it's not part of the live architecture.
- [ ] **Unresolved**: your Supabase database password and Upstash Redis
      token both appeared in plaintext during this session's chat
      history — rotate both from their respective dashboards when you
      get a chance, same as the other credentials flagged along the way.

## 7. Billing (only once selling live)

*Source: `DEPLOY_RUNBOOK.md` step 12*

- [ ] Create live-mode Stripe Prices matching `mcp/licensing.py`'s
      `plan_catalog()`.
- [ ] Add and test the Stripe webhook endpoint in test mode before
      flipping to live keys.

## 8. Legal review (before anything above touches a real customer)

*Source: `TERMS_OF_SERVICE.md`, `PRIVACY_POLICY.md`,
`compliance/DPA_TEMPLATE.md`, `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`,
`compliance/OEM_LICENSING.md`*

- [ ] Decide your target jurisdiction/regime (EU/UK vs. US-only vs.
      mixed) — `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`'s first question,
      needed before booking any attorney call.
- [ ] Get `TERMS_OF_SERVICE.md` attorney-reviewed before publishing or
      linking it from a signup flow.
- [ ] Get `PRIVACY_POLICY.md` attorney-reviewed before publishing.
- [ ] Get `compliance/DPA_TEMPLATE.md` attorney-reviewed before executing
      it with any real customer.
- [ ] Get a real OEM license agreement drafted before signing any
      white-label deal (see Section 2 above).
- [ ] Decide your entity structure (stay sole proprietor, or form an
      LLC/corp) — affects every legal document above, all of which
      currently assume sole proprietor.

## 9. SOC 2 and penetration test (funding-gated — no fixed date)

*Source: `compliance/SOC2_READINESS.md`, `compliance/INTERNAL_SECURITY_REVIEW.md`*

- [ ] Once the hosted instance (Section 6) has run for at least a full
      quarter, engage a real CPA firm for a SOC 2 Type I report, using
      `compliance/SOC2_READINESS.md` as the intake packet.
- [ ] Operate under Type I's controls for 3-12 months, then pursue Type II.
- [ ] Commission a real third-party penetration test ($5-15K) once budget
      allows — `compliance/INTERNAL_SECURITY_REVIEW.md` narrows the gap
      but doesn't close it.

## 10. Governance and organizational (founder decisions, no fixed date)

*Source: `GOVERNANCE.md`, `compliance/SOC2_READINESS.md`*

- [ ] Decide on and bring in a named second person with real oversight
      authority (advisor, fractional CISO, or eventual co-founder) — the
      single item on this whole checklist that is purely a founder
      decision, not an engineering or documentation task.
- [ ] Run `GOVERNANCE.md`'s first scheduled quarterly risk review on
      2026-10-23.
- [ ] Set a real, counsel-confirmed breach-notification timeframe once the
      DPA is attorney-reviewed (Section 8) and the internal 72-hour target
      has been tested against a real incident, not just one tabletop drill.

---

## How to use this file

Work through whichever section is cheapest or most relevant to what you're
doing right now — nothing here has a hard dependency ordering except
Section 6 (hosted instance) gating Section 9 (SOC 2) and parts of Section
7. Check items off directly in this file as you go; it's meant to be
edited over time, not a one-time snapshot.
