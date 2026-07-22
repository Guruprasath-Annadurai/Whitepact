# The ResponsibleAI Trust Index — Open Specification

An open, versioned methodology for scoring an AI system's trustworthiness
across six dimensions, published the way OWASP publishes its Top 10 or PCI
Security Standards Council publishes PCI-DSS: free to read, free to cite,
free to self-assess against. The goal isn't for every company to buy
ResponsibleAI's product — it's for "scored under the Trust Index" to mean
something specific and checkable, the same way "PCI-DSS compliant" does,
regardless of who administers the check.

Spec version: **1.0** (see "Versioning" below for what a version bump means)

Reference implementation: `src/responsibleai/trust/score.py`
(`TrustScoreEngine`) — this document describes the same formula that ships
in code, not a separate paper standard that drifts from what's actually run.

---

## The six dimensions

Every Trust Index score is a weighted composite of six dimensions, each
normalized to 0-1 (1 = fully trustworthy) before weighting:

| Dimension | Weight | Definition |
|---|---|---|
| Fairness | 20% | Absence of detected bias across protected categories (gender, race, age, religion, disability, and similar) in the system's outputs. |
| Privacy | 15% | How well the system avoids leaking or mishandling personally identifiable information. |
| Security | 20% | Resistance to adversarial manipulation — prompt injection, jailbreaks, data exfiltration, role-confusion attacks. |
| Robustness | 15% | Factual reliability and resistance to hallucination — how often the system's claims hold up. |
| Compliance | 20% | Regulatory/governance maturity — documented processes, audit trails, incident response, applicable-framework alignment (GDPR, EU AI Act, etc.). |
| Authenticity | 10% | For systems that generate or evaluate media: resistance to deepfake/synthetic-media misuse. Not applicable to text-only systems — see "Not-applicable dimensions" below. |

**Overall score** = `Σ(dimension_value × weight) × 100`, producing a 0-100
score. Grade bands: A ≥ 90, B ≥ 80, C ≥ 70, D ≥ 60, F < 60. Risk tiers: LOW
≥ 80, MEDIUM ≥ 60, HIGH ≥ 40, CRITICAL < 40.

### Not-applicable dimensions

Not every system can be meaningfully measured on every dimension — a
text-only LLM has no media-authenticity signal to measure, for instance.
Rather than force a fabricated number, an assessment may hold a
not-applicable dimension at a disclosed neutral 0.5 rather than silently
omitting it (omission would change the weighting math in a way that isn't
transparent). **Any citation of a Trust Index score should state which
dimensions were actually measured versus held neutral** — this platform's
own automated leaderboard does exactly that (see
`compliance/LEADERBOARD_METHODOLOGY.md`), and self-assessments should too.

---

## Three ways to get a Trust Index score — not the same thing

This is the most important section in this document. A number under the
Trust Index means something different depending on how it was produced,
and conflating the three is exactly the kind of thing this spec exists to
prevent:

### 1. Self-assessment (free, unverified)

`POST /api/trust-index/assess` — anyone can submit six dimension values
(0-1) for any system and receive a scored, hashed, permanently-recorded
Trust Passport with a stable, publicly verifiable ID. **The inputs are
whatever the submitter provides — this endpoint does not independently
measure anything.** It is the equivalent of self-reporting your own SAT
score: the arithmetic is real and verifiable, but the underlying claim
about your system's actual fairness/privacy/security/etc. is not audited.
Every self-assessed passport is labeled `"certified": false` everywhere it
appears (API response, verify page), and the standard citation format
(below) requires saying "self-reported."

### 2. Automated measurement (free, independently measured, narrower scope)

The public leaderboard (`GET /api/leaderboard`,
`compliance/LEADERBOARD_METHODOLOGY.md`) independently measures fairness,
privacy, security, and robustness by actually calling a model's public API
against a fixed prompt corpus — nobody self-reports these numbers. This is
more credible than self-assessment but only covers models reachable
through a public inference API (not, e.g., an internal classification
system or a proprietary pipeline), and still holds compliance/authenticity
at the same disclosed neutral placeholder for the same reason described
above.

### 3. Certification (paid, human-reviewed)

`POST /api/trust-index/certify/{passport_id}` — a human reviewer
(currently: this platform's own certification process; the spec is
intentionally written so a third party could run their own compatible
certification process against the same formula) examines the evidence
behind a submitted score and, if it holds up, marks the passport
`"certified": true` with a certifier identity and timestamp. **There is no
automated path to certification, by design** — the moment certification
could be self-served, it stops meaning anything more than
self-assessment. This is the paid product: self-assessment and the
methodology itself are free; the audited badge costs money, the same
relationship ISO 9001 or SOC 2 has between their published standard (free
to read) and the accredited audit (paid).

---

## Citing a Trust Index score

A citation should include enough for the reader to verify it themselves.
Minimum acceptable format:

> "[System] scored [X]/100 (Grade [Y]) under the ResponsibleAI Trust Index
> v[version] — [self-reported | certified by [certifier] on [date]].
> Verify at [verify_url]."

Example, self-reported:

> "Acme Chatbot scored 78.5/100 (Grade C) under the ResponsibleAI Trust
> Index v1.0 — self-reported. Verify at
> https://responsibleai.app/verify/3fae2c1a-....”

Example, certified:

> "Acme Chatbot scored 91.2/100 (Grade A) under the ResponsibleAI Trust
> Index v1.0 — certified by ResponsibleAI Certification Team on
> 2026-08-01. Verify at https://responsibleai.app/verify/3fae2c1a-....”

Every `POST /api/trust-index/assess` response includes a ready-to-use
`citation` string in exactly this format, so callers don't have to
construct it by hand.

### Verifying a citation

`GET /api/trust-index/verify/{passport_id}` (or the human-readable
`/verify/{passport_id}` page) returns the full stored record — dimension
scores, generation timestamp, certification status, and the SHA-256
verification hash — for any passport ID. A 404 means the ID doesn't
correspond to a real record: the citation is unverifiable and should be
treated skeptically. This is the entire mechanism that makes "cite your
score" meaningful instead of an unfalsifiable claim.

---

## Versioning

Spec version bumps (semver-style: MAJOR changes to weights or dimension
definitions, MINOR additions of new optional signals, PATCH clarifications
with no scoring impact) are recorded here and stamped on every generated
passport (`spec_version` field) — a score computed under v1.0 and one
computed under a future v2.0 are not directly comparable unless the
changelog says otherwise. `TrustScoreEngine`'s default weights in
`src/responsibleai/trust/score.py` are the source of truth for the current
version; this document is kept in sync with that code, not the reverse.

### Changelog

**v1.0 — 2026-07-22 (current)**
Initial published specification. Six dimensions, weights as listed above.
Self-assessment, automated leaderboard measurement, and human-reviewed
certification introduced as three distinct, clearly-labeled paths to a
score.

---

## What this spec does not cover

- **A formal accreditation process for third-party certifiers.** Today,
  certification is performed only by this platform's own team. A future
  version may define how an independent auditor could become an
  accredited Trust Index certifier, the way accredited bodies exist for
  ISO standards — not built yet, stated as a gap rather than implied.
- **Statistical confidence intervals on scores.** A score is a point
  estimate from a fixed evaluation, not a distribution with error bars.
- **Legal or regulatory endorsement.** Scoring well under this standard is
  not a substitute for actual regulatory compliance (GDPR, EU AI Act, etc.)
  — the compliance *dimension* references those frameworks, but a high
  Trust Index score is not itself a compliance certification for any
  specific law.

This document is versioned and kept honest the same way every other
compliance document in this repository is — corrections and clarifications
land here as dated changelog entries, not silent edits.
