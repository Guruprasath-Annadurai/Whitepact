# OEM / White-Label Licensing — One-Pager

> This is a pricing and positioning document for the "sell the engine, not
> the brand" motion described in `STRATEGY_ROADMAP.md` Part 0, Item 2. It
> is **not a signed legal agreement** — like every other legal-adjacent
> document in this repo (`TERMS_OF_SERVICE.md`, `compliance/DPA_TEMPLATE.md`),
> an actual OEM contract needs attorney review before it's executed with a
> real licensee. This exists so a conversation with a prospective partner
> has concrete numbers and terms to react to, not a blank page.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. The pitch, in one paragraph

Your AI platform needs a governance/trust layer — trust scoring, guardrails,
compliance mapping, audit logging — but building it from scratch is 6-12
months your product roadmap doesn't have room for, and evaluating it isn't
the same conversation as evaluating *us* specifically. Embed the
ResponsibleAI engine under **your own brand** (white-label — see
`RAI_BRAND_NAME`/`RAI_BRAND_LOGO_URL` in `src/responsibleai/dashboard/config.py`,
`GET /api/branding`), so your customers see your product and your
compliance story. What's underneath is real, already-built governance
tooling — 26 MCP tools, 6-dimension trust scoring, NIST AI RMF / EU AI Act
/ ISO 42001 compliance mapping, hash-chained audit logging — not a
placeholder.

**Why this doesn't need our SOC2 to work**: the same way your company
doesn't personally audit Stripe's SOC2 report line-by-line before accepting
payments through it — you rely on Stripe's compliance posture as a
sub-processor, disclosed in your own DPA to your customers, the same
pattern `compliance/DPA_TEMPLATE.md` already uses for our own
sub-processors (GCP, Stripe). An OEM licensee discloses ResponsibleAI as
*their* sub-processor/technology provider the same way, with the same
honest disclosure obligations, not as a vendor whose own certification
status blocks the deal.

---

## 2. What's included

- **Full source access** to the governance engine (already MIT-licensed —
  see `LICENSE`) — trust scoring, guardrails, hallucination detection, bias
  evaluation, drift monitoring, compliance mapping, audit logging.
- **White-label display layer** — `RAI_BRAND_NAME` and `RAI_BRAND_LOGO_URL`
  swap the product name/logo across every served dashboard page and the
  browser tab title, with zero frontend forking required.
- **MCP server** (26 tools, 10 resources) embeddable in the licensee's own
  agent/AI product under their own MCP server name if desired.
- **Ongoing updates** — new governance features, compliance framework
  additions, and security fixes as they ship on `main`.

## 3. What's explicitly NOT included (be upfront about this)

- **Our own SOC2/pentest status** doesn't transfer — see
  `compliance/SOC2_READINESS.md` and `compliance/INTERNAL_SECURITY_REVIEW.md`
  for exactly what exists today. A licensee's own compliance story is their
  own to build and disclose; don't let a prospect assume otherwise.
- **A managed/hosted instance we operate on the licensee's behalf** — see
  `SLA.md`'s central caveat: no ResponsibleAI-operated hosted instance
  exists yet. This is source/engine licensing, not a managed service
  (that's a separate, later conversation once `docker-compose.prod.yml`
  is running in production somewhere real).
- **Exclusivity** — this is not (initially) an exclusive license to any one
  vertical or licensee; multiple companies can each white-label the same
  underlying engine under their own brands.

---

## 4. Pricing model (starting point for negotiation, not a fixed rate card)

Two structures, pick per-deal based on what the licensee actually wants:

| Model | Structure | When it fits |
|---|---|---|
| **Flat annual license** | A fixed fee for source access + updates, paid annually, no usage tracking | A licensee that wants predictable cost and will run the engine at whatever scale they choose |
| **Revenue share** | A percentage of the licensee's own governance-feature revenue (e.g., if they sell "AI Trust" as a paid add-on to their own customers) | A licensee testing the waters before committing to a flat fee, or one whose own pricing model is usage-based |

**Suggested starting anchor, adjust per conversation**: flat license
starting around **$2,000-5,000/month** for a small-to-mid-size AI platform
(under ~50 employees), scaling with the licensee's own customer count or
revenue for larger deals — these are founder-set starting numbers to open a
negotiation, not benchmarked against comparable deals, since no comparable
deal has closed yet. Revise this table honestly once a first real deal
closes, the same discipline this project's compliance docs already apply
to every other self-assessed claim.

---

## 5. What a licensee needs to bring

- Their own entity to sign the license agreement (once one exists — see
  Section 6).
- Their own decision on hosting (self-host the licensed source themselves,
  same `docker-compose.prod.yml` path any self-hosted customer uses).
- Their own customer-facing compliance disclosures (a DPA/ToS mentioning
  ResponsibleAI as a technology provider/sub-processor, matching the
  Stripe-analogy pattern in Section 1).

---

## 6. Before this goes live

1. This one-pager is a BD conversation starter, not a contract — a real OEM
   license agreement needs the same attorney review every other
   legal-adjacent document in this repo requires before execution.
2. The pricing anchors in Section 4 are founder-set starting points with
   zero deals closed against them yet — update this document honestly the
   first time a real negotiation lands somewhere different, rather than
   treating these numbers as fixed once written down.
3. Confirm the white-label mechanism (Section 2) still matches
   `src/responsibleai/dashboard/config.py`'s actual `brand_name`/
   `brand_logo_url` fields before quoting a prospect a capability that may
   have changed — check the code, not just this document, per this
   project's standing practice.
