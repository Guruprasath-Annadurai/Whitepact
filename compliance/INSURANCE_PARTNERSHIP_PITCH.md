# AI Liability Insurance Partnership Pitch — One-Pager

> BD document for `STRATEGY_ROADMAP.md` Part 0, Item 5 — the
> insurance/underwriting angle. This is a pitch to bring to an AI-focused
> liability/E&O insurer or MGA (managing general agent), not a signed
> partnership — the actual terms of any real arrangement need that
> insurer's own underwriting/legal review, the same way every other
> partnership document in this repo (`compliance/OEM_LICENSING.md`) is a
> conversation starter, not a contract.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. The pitch, in one paragraph

AI liability/E&O insurers underwriting policies for companies deploying
LLM-based products face a real, growing problem: there is no standardized,
objective signal for "how well-governed is this company's AI system"
comparable to what a fire-suppression certificate or a SOC2 report gives a
traditional underwriter. A ResponsibleAI Trust Passport
(`compliance/TRUST_INDEX_SPEC.md`) — a durable, independently-verifiable
record of trust scoring across six governance dimensions, optionally
human-certified — is exactly that kind of objective signal, and it already
exists, is free to generate, and is publicly checkable
(`GET /api/trust-index/verify/{id}`). Pitch: recognize a current, certified
Trust Passport as a rated factor in underwriting AI liability policies —
policyholders who maintain one get a documented, favorable signal; the
insurer gets a cheap, real, checkable data point they don't have today.

---

## 2. Why this doesn't need ResponsibleAI's own SOC2 first

This is the same "borrowed credibility" structure as the OEM pitch
(`compliance/OEM_LICENSING.md` Section 1): the insurer's own underwriting
process — their actuaries, their risk models, their own regulatory
standing — is the credibility layer, not ResponsibleAI's certification
status. ResponsibleAI is supplying a *data signal* the insurer chooses to
weight however their own underwriting judges appropriate; the insurer is
not being asked to vouch for ResponsibleAI, and ResponsibleAI is not
representing itself as a certified vendor in this specific pitch — it's
offering an open, checkable methodology (see
`compliance/TRUST_INDEX_SPEC.md`'s citation format) that any interested
party, including the insurer's own actuaries, can independently verify the
mechanics of.

---

## 3. What ResponsibleAI would need to actually provide

- **Nothing exclusive or proprietary the insurer couldn't check
  themselves** — the Trust Index methodology is designed to be openly
  citable (see Item 6 of `STRATEGY_ROADMAP.md` Part 0: publishing the spec
  itself as an open standard). An insurer's actuaries should be able to
  read the spec and reproduce the scoring logic, not take it on faith.
- **A stable, durable verification endpoint** — already exists
  (`GET /api/trust-index/verify/{passport_id}`), needs no new engineering
  for this pitch specifically.
- **Possibly, a bulk/API-friendly lookup for an insurer's own tooling** —
  not built yet; only worth building once a real conversation confirms an
  insurer wants it, not speculatively ahead of any interest.

## 4. What ResponsibleAI would want in return

- **Recognition, in writing, that a current Trust Passport (ideally
  certified) is a factor the insurer's underwriting considers** — this is
  the actual value: external pull. A company shops for AI liability
  coverage, learns a Trust Passport helps their premium, and seeks out
  ResponsibleAI *because their insurer said so* — a fundamentally
  different, higher-intent lead source than any outbound sales motion.
- **No revenue share or fee required to start** — the value to
  ResponsibleAI is the demand-generation effect, not a payment from the
  insurer; keep the initial ask simple and low-friction to get a first
  yes.

---

## 5. Target list — how to find the right contact

AI liability/E&O insurance is a young, fast-moving line — search fresh
rather than trusting a fixed list written into this document once and left
stale (the same caveat `compliance/MCP_DISTRIBUTION_GUIDE.md` gives for MCP
directories, for the same reason: the landscape changes faster than a
static document should be trusted to track). Look for:

- **Specialty MGAs writing AI/tech E&O policies** — search "AI liability
  insurance," "AI E&O coverage," "technology errors and omissions AI
  rider" for current names; this market has been expanding and specific
  named players will be more current found live than listed here.
- **Insurtechs building underwriting tooling for tech/AI risk** — often
  more receptive to a data-partnership pitch than a traditional carrier,
  since integrating novel risk signals is closer to their core product.
- **Cyber insurance brokers with an AI practice** — a broker who places
  policies for AI companies may be a faster path to an actual underwriter
  conversation than approaching a carrier cold.

**Outreach approach**: a short, direct email — this pitch's Section 1
paragraph, adapted to two sentences, plus a link to a live
`/verify/{passport_id}` page as a working example, not a mockup. Low
volume, high specificity beats a mass email — this is a long-shot,
high-upside experiment costed at one afternoon of research and outreach
per `STRATEGY_ROADMAP.md`'s 90-day action list, not a committed campaign.

---

## 6. Before treating any response as a real partnership

1. Any actual written recognition from an insurer needs their own legal/
   compliance sign-off, not just an underwriter's informal enthusiasm —
   don't announce a "partnership" publicly until something is actually in
   writing from a party with authority to commit the insurer.
2. Don't over-promise Trust Passport reliability in this pitch beyond what
   `compliance/TRUST_INDEX_SPEC.md` actually claims — a self-assessed score
   is self-reported, and the pitch should be clear that only a *certified*
   passport carries independent review, not the free self-assessed tier.
3. Track this as a long-shot, asymmetric-upside experiment, not a revenue
   line to build a forecast around until a first real conversation
   confirms genuine interest.
