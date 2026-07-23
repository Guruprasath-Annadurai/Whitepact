# ResponsibleAI — Strategy & Phased Development Roadmap

Written 2026-07-22. Posture: **Hybrid Phased** (harden the enterprise compliance
core for near-term revenue, then fund the bigger consumer-trust vision from
that revenue — see the D1 decision brief in the session that produced this
document for the reasoning).

This plan is written from two seats at once, on purpose:
- **The CEO seat**: revenue, positioning, what a buyer signs a PO for.
- **The everyday AI-user seat**: someone using Claude, ChatGPT, or Gemini
  every day who has no idea whether the AI behind the product they're using
  is safe, fair, or honest — and currently has zero way to check.

The hard constraint from the founder: **this must make real revenue, on a
schedule, or the whole roadmap is theoretical.** Every phase below states
what it sells and to whom before it states what it builds.

---

## Part 1 — What's actually built today (audit, not aspiration)

Verified against the current codebase, not marketing copy:

| Area | Status |
|---|---|
| Trust scoring (6 dimensions: fairness/privacy/security/robustness/compliance/authenticity) | Built, tested |
| Guardrails Engine (PII/toxicity scan + redaction) | Built, tested |
| Hallucination detection | Built, tested |
| Cost Intelligence + Model Router | Built, tested |
| Multi-tenant RBAC (OWNER/ADMIN/ANALYST/VIEWER) + OIDC SSO enforcement | Built, tested |
| Hash-chained audit log (tamper-evident) | Built, tested |
| Incident management: `incidents` table, `POST/GET /api/incidents`, Alertmanager auto-bridge | Built, tested (this session) |
| Per-tenant Prometheus metrics, CSP/HSTS headers, opt-in field encryption, DB retry-on-failover | Built, tested (this session) |
| Stripe billing (FREE/PRO/ENTERPRISE), plan-based rate limiting, MCP usage metering | Built, tested |
| MCP server exposing 15+ governance tools to any MCP client (Claude Desktop, Cursor, etc.) | Built, tested |
| Compliance paperwork: CAIQ self-assessment, NIST CSF self-assessment, DPA template + attorney scope brief, incident response runbook (tabletop-tested), vendor risk assessment | Built this session |
| SOC2 / ISO 27001 of our own | **Not started** — funding-gated |
| Third-party penetration test | **Not started** — funding-gated |
| Public trust registry / consumer-facing product | **Does not exist yet** |

**Honest read:** the engineering is far ahead of the go-to-market. There is a
genuinely enterprise-credible governance platform sitting here with almost no
customers yet. The roadmap below exists to fix that imbalance, not to keep
building features nobody's paying for.

---

## Part 2 — Phase-by-phase roadmap

### Phase 1 — "Get the first dollar" (Months 1-3)

**CEO framing:** You cannot sell "trust" as an abstraction. You sell a
specific, budgeted line item to a specific buyer. The buyer who has budget
*today* for this is a **compliance/security lead at a mid-size company already
using LLMs in production** who is being asked by their own customers or
regulators "how do you govern your AI?" and has no good answer. That's a
checkbox they need filled, and ResponsibleAI already fills it.

**User framing:** the "everyday user" in this phase isn't a consumer yet —
it's the engineer/compliance person at that company, whose personal relief is
"I don't have to build this from scratch or explain to my CEO why we have no
answer for the auditor."

**What ships:**
1. **Close the CAIQ/NIST CSF gaps that are pure engineering time, not money**: Dependabot (config-only, do this first — it's free), OWASP ZAP scan actually run against a live deployment, an SBOM generator wired into CI.
2. **Self-serve onboarding flow** — today, org creation/API keys/SSO setup requires reading docs. Build the guided onboarding wizard (already spec'd in the UI design work this session) so a compliance lead can go from signup to "here's our trust score dashboard" in under 15 minutes with zero sales call. This is the single highest-leverage revenue unlock: self-serve removes you (the solo founder) as the bottleneck in every sale.
3. **A real pricing page + Stripe checkout flow that works end to end** — verify the existing Stripe integration against a real test purchase, not just unit tests. Revenue fails silently if checkout has a bug nobody's clicked through.
4. **3-5 design partners, not paying customers yet** — give ENTERPRISE tier free to 3-5 real companies for 60 days in exchange for a public case study/testimonial and unfiltered feedback. You need proof it works on someone else's real data before you can sell it on the strength of your own claims.
5. **First real customer conversations, targeted per `compliance/SALES_TARGETING.md`** — this document already exists from earlier work; execute against it instead of writing another one.

**Revenue mechanism:** design partners convert to paying ENTERPRISE customers
at the end of the 60-day window, or don't — either way you learn fast and
cheap. Target: **1-3 paying enterprise customers by end of Phase 1**, even at
a discounted founding-customer rate. Real revenue, not a pilot promise.

**What this phase deliberately does NOT do:** no SOC2, no pentest, no
consumer product, no new AI-safety features. Those all cost money or take
months this phase doesn't have. Discipline here is the point.

---

### Phase 2 — "Prove it scales" (Months 4-8)

**CEO framing:** Once you have 1-3 paying customers, the next unlock is
**removing the reasons a bigger customer says no.** The two biggest objections
at this stage are almost always "you don't have SOC2" and "what happens if
you disappear" (single-founder risk). This phase exists to remove both
objections with the *cheapest* real fix, not the most complete one.

**User framing:** the compliance-lead user's relief deepens from "I have an
answer for the auditor" to "I trust this vendor will still exist and support
me in a year" — a completely different, much higher bar of trust.

**What ships:**
1. **SOC2 Type II process kickoff** — this is the single biggest, slowest
   investment in the whole roadmap (6-12 months, $10-30K/yr). Start the clock
   in Phase 2 using Phase 1's revenue, even if it doesn't land until Phase 3.
   Vanta/Drata-style automated compliance tooling is the affordable path for a
   solo founder, not a Big 4 auditor engagement from day one.
2. **A real third-party pentest** ($5-15K, funded by Phase 1 revenue) —
   removes the second-biggest enterprise objection and gives you a real
   report to put in the Trust Center instead of "not yet performed."
2b. **Fix the "single founder" objection directly, not just implicitly**:
    publish a documented business-continuity/escrow plan (what happens to
    customer data and support if the founder is unavailable — even a simple
    published commitment plus a code-escrow arrangement addresses this
    concrete, common enterprise-procurement blocker).
3. **Usage-based expansion revenue** — instrument the product so customers
   naturally grow their spend (more evaluations, more MCP calls, more seats)
   without a renegotiation — the metering/plan infrastructure already exists
   from this session's work; make sure upgrade prompts actually fire in the UI
   when a customer nears a quota, rather than silently blocking them.
4. **Vertical-specific compliance packs** — instead of one generic product,
   package the same underlying engine as "ResponsibleAI for FinTech" (mapped
   to SR 11-7 model risk management) and "ResponsibleAI for HealthTech"
   (mapped to relevant health AI guidance) — same product, positioned
   language and mapped controls per vertical. This is a content/positioning
   investment, not new engineering, and it 3-5x's the perceived relevance to
   a buyer scanning for "does this apply to my industry."
5. **First hire consideration** — if Phase 1 revenue supports it, this is
   where a single sales/success hire (not another engineer) has the highest
   leverage: the product outpaces the go-to-market capacity of one person.

**Revenue mechanism:** target **10-20 paying customers, $150-400K ARR** by
end of Phase 2 — enough to fund SOC2 completion and the first real headcount
decision in Phase 3.

---

### Phase 3 — "Build the moat: the consumer trust layer" (Months 9-15)

This is where the "hybrid" in Hybrid Phased pays off — Phase 1-2 revenue now
funds the bigger, harder-to-copy vision that directly answers what an
everyday Claude/ChatGPT/Gemini user actually wants: **a way to know, at a
glance, whether the AI they're using is trustworthy — without reading a
whitepaper.**

**CEO framing:** the B2B compliance-checkbox market is real but has a
ceiling — eventually every serious AI vendor builds or buys "good enough"
internal governance. The bigger, durable business is being the *independent,
recognized, third-party trust mark* for AI — the "Better Business Bureau" or
"Underwriters Laboratories" for AI systems. That position compounds: the more
companies get certified, the more valuable the certification becomes to the
next company, and the more consumers recognize and demand the badge.

**User framing (this is the "relief" the founder explicitly asked for):**
today, a person using an AI product has no way to answer "can I trust this?"
except vibes and brand reputation. This phase gives them an actual answer.

**What ships:**
1. **Public Trust Registry** (`trust.responsibleai.app` or similar) — a
   searchable, public page where anyone can look up an AI product/company and
   see its ResponsibleAI trust score, certification status, last audit date,
   and any disclosed incidents — the "Trust Passport" concept from this
   session's UI design work, made public-facing and consumer-legible instead
   of buried in an enterprise dashboard.
2. **A recognizable certification badge/mark** — the actual product a
   certified company embeds on their website/app/pricing page ("Certified by
   ResponsibleAI"), the way "Verified by Visa" or a SOC2 badge works today.
   This is the single highest-leverage consumer-trust feature: it doesn't
   require the end user to visit ResponsibleAI at all — trust travels to
   where the user already is.
3. **Free individual-developer tier** — any solo developer building an AI
   product can run a free trust evaluation and get a badge for a
   side project or small app. This seeds bottom-up adoption and awareness
   long before those developers have enterprise budgets — some fraction of
   them become the enterprise customers of Phase 1-2's playbook two years
   later, but more importantly it makes the badge *common* and therefore
   *meaningful* when a consumer sees it.
4. **Public Incident Transparency Feed** — an opt-in public page (think "a
   status page, but for AI safety incidents across certified companies") —
   if a certified AI product had a real incident (a jailbreak, a bias
   finding, a data exposure) and disclosed it responsibly, that transparency
   is *shown*, not hidden — paradoxically this builds more trust than perfect
   silence, because it proves the certification isn't just a rubber stamp.
5. **"Explain This AI Decision" consumer API** — a lightweight, embeddable
   widget any certified AI product can add so an end user who got a
   confusing or concerning AI response can click "why did it say this?" and
   get a plain-language trace (was this flagged by guardrails, what was the
   trust score at the time, was this a known hallucination pattern) — this
   directly operationalizes the EU AI Act's "right to explanation" for
   end users, not just for internal compliance teams.

**Revenue mechanism:** certification/badge licensing fee (companies pay to be
certified and keep the badge current, tiered by company size), plus the free
developer tier becoming a lead-gen funnel into Phase 1-2's enterprise
product. This is the phase where ResponsibleAI stops being "a tool a company
buys" and starts being "a mark consumers look for," which is a fundamentally
bigger and more durable business than either alone.

---

### Phase 4 — "Platform and ecosystem" (Months 16+)

**CEO framing:** once the certification mark has real recognition, the
platform play is to become the place every AI product integrates *by
default*, the way Stripe became the default for payments — not because it's
the only option, but because integrating it once removes an entire category
of future headaches (compliance, safety, trust) for whoever builds on it.

**What ships (directionally, not committed — revisit once Phase 3 proves out):**
1. **Marketplace of certified AI vendors** — a directory where a company
   *shopping* for an AI vendor (not building one) can filter by ResponsibleAI
   trust score, the same way a company shops for a payment processor by PCI
   compliance level today.
2. **Direct integration partnerships** — work with wrapper/agent-platform
   companies (the thousands of startups built on top of Claude/GPT/Gemini
   APIs) to make ResponsibleAI governance a one-line SDK add, the way
   Sentry/Datadog became the default observability add for any new app.
3. **Regulatory-mapped compliance packs expand** to cover new jurisdictions
   as AI regulation spreads beyond the EU AI Act (this is a content/mapping
   investment that compounds on the vertical-pack work from Phase 2).
4. **Consider the "browser extension" idea seriously here, not earlier** — a
   consumer browser extension showing a trust score badge next to any AI
   chat interface you visit is a great *awareness* product but a weak
   *revenue* product on its own; it makes far more sense once the
   certification mark already has recognition to piggyback on, rather than
   as a Phase 1 bet that spends scarce founder time on a feature with no
   direct revenue path.

---

## Part 3 — Extra feature ideas (the "makes people relieved" list)

Beyond what's sequenced into phases above, these are genuinely novel ideas
worth holding in reserve — not committed to the roadmap, but strong enough to
name explicitly since the ask was specifically for this:

- **"AI Nutrition Label"** — a standardized, glanceable label (like a food
  nutrition facts panel) showing an AI product's training data sources,
  known bias categories, hallucination rate, and last audit date — designed
  to be understood by someone with zero technical background, the single
  most direct answer to "make people relieved" from a non-technical user's
  perspective.
- **Personal AI Safety Score search** — let an individual paste in "which AI
  should I trust with my kid's homework help / my therapy journaling / my
  medical questions" and get a plain-language comparison across major AI
  products' relevant trust dimensions for that specific use case, rather
  than a generic overall score.
- **School/parent compliance package** — a specific, separately-marketed
  version of the trust registry aimed at schools and parents evaluating AI
  tools for classroom or home use — an underserved, high-anxiety audience
  with real willingness to pay for peace of mind, and a completely different
  sales motion (district procurement, not enterprise SaaS) worth testing
  cheaply as a side experiment once Phase 3's registry exists.
- **"Right to be forgotten from training" verification tool** — as AI
  companies face increasing pressure on training-data consent, a tool that
  helps an individual check whether their public content appears in a given
  model's likely training set, and generates the correct legal request to
  each provider — solves a real, growing anxiety with no good current answer.

None of these are committed — they're the reserve list for when Phase 3's
registry needs a second act, or if user research during Phase 3 surfaces one
of these as the thing people actually ask for first.

---

## Part 4 — Revenue discipline (the non-negotiable constraint)

Every phase above states its revenue mechanism up front, on purpose, because
the founder's stated constraint is that revenue must not fail. Three rules
enforce that discipline going forward:

1. **No phase starts until the previous phase's revenue target is hit, or
   there's an explicit, reasoned decision to proceed without it.** Phase 3's
   ambitious consumer registry is explicitly *funded by* Phase 1-2 revenue,
   not by hope — if Phase 2 doesn't reach the ARR target, Phase 3 waits
   rather than draining runway on the bigger bet before the smaller one is
   proven.
2. **Every new feature request (including the "reserve list" ideas above)
   gets asked one question before it's built: who pays for this, and how
   much, specifically?** Not "it builds trust" as an answer — trust has to
   convert to a checkout, a subscription, or a licensing fee somewhere in the
   chain, even if indirectly (e.g., the free developer tier's "revenue" is
   the enterprise leads it generates two phases later — that's fine, as long
   as it's named, not assumed).
3. **Track one number obsessively through every phase: paying customers
   (not signups, not design partners, not registry lookups).** Everything
   else in this roadmap is a means to that number going up on a schedule.

---

*This document is a living roadmap, not a contract — revisit it at the start
of each phase against what was actually learned, the same discipline already
applied to every compliance document in this repo.*
