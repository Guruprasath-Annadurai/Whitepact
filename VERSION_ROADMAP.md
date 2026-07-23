# Version Roadmap — v1.2.0 → v6.0.0

> This is the version-numbered technical/product plan. `STRATEGY_ROADMAP.md`
> covers the same ground from the business/revenue side (its four Phases
> map roughly one-to-one onto v2 through v5 below); this document exists
> to answer "what actually ships in which release," in the same dated,
> honest style as `CHANGELOG.md`. Later versions (v4+) are directional,
> not committed — stated plainly per version below, the same discipline
> `STRATEGY_ROADMAP.md` Part 4 already applies: **no version starts until
> the previous one's revenue/proof target is hit, or there's an explicit,
> reasoned decision to proceed without it.**

Last reviewed: 2026-07-23 · Current shipped version: 1.2.0

---

## v1.2.0 — shipped, 2026-07-23 (this document's baseline)

See `CHANGELOG.md`'s `[1.2.0]` entry for the full list. Summary: Public
Leaderboard, Trust Index/Passports + embeddable badges, AI Incident
Database, TOTP MFA, expanded field encryption, DB-persisted webhooks,
full dashboard UI rebuild, white-label branding, a one-command self-hosted
deploy script, a full legal/compliance/BD document set, and — new as of
this exact date — a genuinely live hosted instance (Render + Supabase +
Upstash).

---

## v2.0.0 — "Real hosted tier, sellable" (target: Months 1-3 from v1.2.0)

**Maps to**: `STRATEGY_ROADMAP.md` Phase 1 ("Get the first dollar").

**What ships**:
1. **Hosted instance hardened for real traffic** — custom domain + TLS
   (replacing the bare `.onrender.com` URL), a public status page linked
   from `SLA.md`, and the "no hosted instance is live yet" caveat
   *properly* removed from `SLA.md`/`TERMS_OF_SERVICE.md`/`PRIVACY_POLICY.md`
   (not just noted as stale — actually rewritten to describe the real,
   current free-tier-backed hosted offering honestly).
2. **Self-serve onboarding wizard** — signup → API key → first trust
   score dashboard in under 15 minutes, zero sales call required. The
   single highest-leverage revenue unlock per `STRATEGY_ROADMAP.md`
   Phase 1: removes the founder as a bottleneck in every sale.
3. **Stripe billing verified end-to-end** — a real test purchase through
   checkout, not just unit tests against the billing API.
4. **Persistent storage proven under real load** — the Render/Supabase/
   Upstash stack has been proven to *persist data*, not yet proven under
   concurrent multi-user load; this version's bar is "survived a real
   design partner's traffic," not just "survived a redeploy."
5. **MCP distribution actually submitted** — the directory submissions
   drafted in `compliance/MCP_DISTRIBUTION_GUIDE.md` actually done, not
   just prepared.
6. **3-5 design partners onboarded**, ENTERPRISE tier free for 60 days
   each, in exchange for case studies and real-data feedback.
7. **First real paying customers** — target 1-3 by the end of this
   version, per `STRATEGY_ROADMAP.md` Phase 1's revenue discipline.

**What this version deliberately does NOT do**: no SOC2, no pentest, no
consumer-facing product, no new AI-safety features. Same discipline
`STRATEGY_ROADMAP.md` states for Phase 1 — this version is about revenue
and removing the founder as a bottleneck, not new capability.

**Revenue gate before v3.0.0 starts**: 1-3 paying customers, even at a
discounted founding-customer rate. If this isn't hit, v3.0.0 waits rather
than starting on hope.

---

## v3.0.0 — "Enterprise trust" (target: Months 4-8 from v2.0.0)

**Maps to**: `STRATEGY_ROADMAP.md` Phase 2 ("Prove it scales").

**What ships**:
1. **SOC 2 Type I engaged and completed**, funded by v2.0.0's revenue,
   using `compliance/SOC2_READINESS.md` as the intake packet — the
   single biggest, slowest investment in this whole roadmap (see that
   document's Section 5 for realistic cost/timeline).
2. **A real third-party penetration test** ($5-15K, funded by v2.0.0
   revenue) — replaces `compliance/INTERNAL_SECURITY_REVIEW.md` as the
   answer to "have you been pentested," which stops being sufficient once
   real enterprise money is on the table.
3. **A named second person with real governance authority** — the one
   item `GOVERNANCE.md` explicitly flags as a founder decision no process
   document can substitute for; this version is where that decision
   should actually get made, since SOC 2's CC1 (Control Environment) will
   ask about it directly.
4. **The breach-notification target becomes a real contractual term** —
   `compliance/INCIDENT_RESPONSE_RUNBOOK.md`'s internal 72-hour target
   graduates from "internal operating standard" to an actual DPA clause,
   once tested against a real incident (not just the one tabletop drill)
   and set by counsel per `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`.
5. **Business-continuity/escrow plan published** — addresses the
   "single founder" objection directly: what happens to customer data
   and support if the founder is unavailable.
6. **Vertical-specific compliance packs** — "ResponsibleAI for FinTech"
   (SR 11-7 model risk management mapping) and "ResponsibleAI for
   HealthTech" — same engine, positioned language and mapped controls
   per vertical, a content investment not a new-engineering one.
7. **Usage-based expansion revenue instrumented** — upgrade prompts
   actually fire in the UI when a customer nears a quota.
8. **First hire consideration** — a sales/success hire, if v2.0.0 revenue
   supports it; higher leverage than another engineer at this stage.
9. **Multi-region/HA architecture, first real attempt** — not the
   single-instance Render/Supabase/Upstash setup from v1.2.0/v2.0.0;
   at least one paid, redundant deployment path documented and tested.

**Revenue gate before v4.0.0 starts**: 10-20 paying customers,
$150-400K ARR, per `STRATEGY_ROADMAP.md` Phase 2 — enough to fund SOC 2
completion and the v3.0.0 headcount decision.

---

## v4.0.0 — "Public trust registry" (target: Months 9-15 from v3.0.0)

**Maps to**: `STRATEGY_ROADMAP.md` Phase 3 ("Build the moat"). This is
where the B2B compliance product starts funding the bigger, harder-to-copy
consumer-trust vision.

**What ships**:
1. **Public Trust Registry** — a searchable public page where anyone
   looks up an AI product/company and sees its ResponsibleAI trust score,
   certification status, last audit date, and disclosed incidents. The
   Trust Passport concept from v1.2.0, made consumer-legible instead of
   buried in an enterprise dashboard.
2. **A recognizable certification badge/mark at real scale** — the free
   self-assessed / paid certified badge mechanism from v1.2.0
   (`trust/badge.py`) now has an actual review team/process behind the
   paid tier, not just a founder doing it manually.
3. **Free individual-developer tier** — any solo developer gets a free
   trust evaluation and badge; seeds bottom-up adoption before those
   developers have enterprise budgets.
4. **Public Incident Transparency Feed** — a status-page-style public
   feed of disclosed AI safety incidents across certified companies,
   building the "the certification isn't just a rubber stamp" case.
5. **"Explain This AI Decision" consumer widget** — embeddable, operationalizes
   the EU AI Act's "right to explanation" for end users, not just
   internal compliance teams.
6. **The Trust Index spec gains real external citation traction** — the
   arXiv paper (`compliance/TRUST_INDEX_PAPER.md`) has been submitted and
   ideally cited/referenced by others by this point, not just published.

**Revenue mechanism**: certification/badge licensing fees (tiered by
company size) plus the free developer tier feeding v2.0.0-v3.0.0's
enterprise funnel — this is the version where ResponsibleAI stops being
"a tool a company buys" and starts being "a mark consumers look for."

---

## v5.0.0 — "Platform and ecosystem" (target: Months 16+ from v4.0.0)

**Maps to**: `STRATEGY_ROADMAP.md` Phase 4. **Directional, not committed**
— revisit once v4.0.0 proves out, per this document's own opening
discipline statement.

**What ships (directionally)**:
1. **Marketplace of certified AI vendors** — a directory a company
   shopping *for* an AI vendor (not building one) can filter by trust
   score, the way payment-processor shopping filters by PCI compliance
   level today.
2. **Direct integration partnerships / SDK** — a one-line governance
   add for agent-platform startups built on Claude/GPT/Gemini APIs, the
   way Sentry/Datadog became the default observability add. The OEM/
   white-label motion from `compliance/OEM_LICENSING.md` (v1.2.0) scaled
   to multiple real licensees rather than a founder-time BD experiment.
3. **Regulatory-mapped compliance packs expand** to jurisdictions beyond
   the EU AI Act, compounding on v3.0.0's vertical-pack content
   investment.
4. **SOC 2 Type II achieved** — requires 3-12 months operating under
   v3.0.0's Type I controls; this is the version where that clock
   actually completes.
5. **A real accredited third-party certifier program** — closes the gap
   `compliance/TRUST_INDEX_SPEC.md`'s "What this spec does not cover"
   section names directly: today, certification is performed only by
   this project's own team; this version defines how an independent
   auditor could become an accredited Trust Index certifier, the way ISO
   management-system standards have accredited certification bodies.

---

## v6.0.0 — "Category-defining standard" (directional, no target date)

**Not mapped to any current `STRATEGY_ROADMAP.md` phase** — this is
beyond that document's current planning horizon, included here because
the ask was specifically for a plan through v6. Treat everything below as
a hypothesis to validate against what v4.0.0-v5.0.0 actually teach, not a
committed spec.

**What this version represents, directionally**:
1. **The Trust Index is a genuinely recognized external standard** —
   cited by other researchers/companies independent of ResponsibleAI's
   own promotion of it, the way OWASP's Top 10 or PCI-DSS are referenced
   without needing OWASP or the PCI Council to constantly re-explain
   them.
2. **Insurance partnerships operational, not just pitched** — the
   `compliance/INSURANCE_PARTNERSHIP_PITCH.md` conversation from v1.2.0
   has, by this point, either produced a real underwriting recognition
   or been abandoned as a dead end — this version assumes the former.
3. **Multi-jurisdiction legal/compliance coverage** — beyond the EU AI
   Act and US-centric framing in `TERMS_OF_SERVICE.md`/`PRIVACY_POLICY.md`
   as originally drafted; real international data-transfer mechanisms,
   not placeholder caveats.
4. **Enterprise SLA tier with real contractual uptime commitments** —
   graduated from `SLA.md`'s current "design target, not enforced"
   framing to an actual negotiated, insured commitment for top-tier
   customers.
5. **A decision point on the company's own trajectory** — by v6.0.0, the
   accumulated proof (revenue, certification, registry adoption, insurer
   recognition) is either strong enough to support a real fundraise or an
   acquisition conversation, or it isn't — this version is explicitly the
   point to make that call honestly rather than assume it by default.

---

## The discipline this document commits to

Same three rules `STRATEGY_ROADMAP.md` Part 4 already states, restated
here because they apply to version numbers just as much as phase names:

1. No version starts until the previous one's revenue/proof target is
   hit, or there's an explicit, reasoned decision to proceed without it.
2. Every new feature gets asked one question before it's built: who pays
   for this, and how much, specifically?
3. Track paying customers, not version numbers, as the real measure of
   progress — this document sequences *what* ships, not a promise about
   *when*, since the actual pace depends entirely on the revenue this
   plan itself is designed to produce.
