# The Trust Index: An Open, Citable Methodology for Multi-Dimensional AI System Trustworthiness Scoring

> This is a paper draft prepared for arXiv submission, supporting
> `STRATEGY_ROADMAP.md` Part 0, Item 6 — publishing the Trust Index
> methodology (`compliance/TRUST_INDEX_SPEC.md`) as a citable, openly
> reviewable standard, the cheaper-than-a-certificate credibility lever a
> bootstrapped project can pursue with founder time alone.
>
> **What this is not**: an arXiv submission. Actually submitting requires
> (1) converting this Markdown draft to arXiv's expected format (LaTeX is
> the norm; a PDF generated from Markdown via pandoc is accepted in some
> categories but LaTeX is safer), (2) creating an arXiv account, and (3)
> in some categories (notably `cs.CY`, `cs.AI`), a first-time submitter may
> need **endorsement** from an existing arXiv author in that category —
> check arXiv's current endorsement policy before assuming a submission
> will go through unassisted. None of this can be done on the founder's
> behalf; this document is the content, not the submission.

Last reviewed: 2026-07-23

---

## Abstract

AI governance today lacks a standardized, openly-verifiable signal for
comparing the trustworthiness of deployed AI systems across organizations
— unlike domains such as payment security (PCI-DSS) or web application
security (OWASP Top 10), where a published, versioned standard lets any
party independently assess and cite compliance without depending on a
single vendor's proprietary methodology. We present the **Trust Index**, an
open specification for scoring an AI system across six weighted
dimensions — fairness, privacy, security, robustness, compliance, and
authenticity — producing a 0-100 composite score, a letter grade, and a
risk tier. We describe three distinct provenance paths for a Trust Index
score (self-assessment, automated measurement against a public inference
API, and human-reviewed certification), each explicitly labeled to prevent
the conflation of self-reported and independently-verified claims — a
distinction we argue is necessary for any trust signal to remain
meaningful as adoption scales. We provide a reference implementation
(`src/responsibleai/trust/score.py`) and a public verification mechanism
(`GET /api/trust-index/verify/{id}`) that returns the full scored record
for any cited passport ID, making every citation independently checkable
rather than an unfalsifiable claim. We discuss the specification's current
limitations, including the absence of a formal third-party accreditation
process and the lack of statistical confidence intervals on point-estimate
scores, and outline a versioning discipline intended to keep the published
standard synchronized with its reference implementation over time.

---

## 1. Introduction

As organizations increasingly deploy large language models and other AI
systems in production, buyers, regulators, and end users face a recurring
question with no standardized answer: *how trustworthy is this specific AI
system, on what basis, and who verified the claim?* Existing approaches
tend toward one of two extremes. At one end, informal marketing claims
("our AI is safe and unbiased") carry no verifiable structure at all. At
the other, formal regulatory compliance frameworks (the EU AI Act, NIST AI
RMF) are comprehensive but not designed to produce a single, comparable,
publicly citable score suitable for quick buyer-side comparison the way a
credit rating or a PCI-DSS attestation is.

We propose the Trust Index to fill this gap: a lightweight, open,
versioned scoring methodology, deliberately modeled on the publication
pattern of security standards bodies (OWASP, PCI Security Standards
Council) rather than on a proprietary vendor certification. The
specification is published in full (`compliance/TRUST_INDEX_SPEC.md`) and
its reference implementation ships as open-source code
(`src/responsibleai/trust/score.py`), so that the formula computing a
published score is never separated from a paper description that could
drift from what is actually run.

This paper's contribution is threefold: (1) a six-dimension weighted
scoring methodology with defined grade and risk-tier bands; (2) an
explicit three-tier provenance model distinguishing self-reported,
automatically measured, and human-certified scores, which we argue is
necessary to prevent the standard's erosion into an unfalsifiable
marketing claim as adoption grows; and (3) a public verification mechanism
that makes any cited score independently checkable by any third party,
without requiring trust in the citing party alone.

---

## 2. Related work

**Regulatory AI risk frameworks.** The EU AI Act and the NIST AI Risk
Management Framework provide comprehensive governance requirements but are
structured as compliance obligations and voluntary guidance respectively,
not as a single comparable numeric score intended for rapid, informal
buyer-side comparison across vendors.

**Model evaluation benchmarks.** Benchmarks such as TruthfulQA, BBQ, and
HellaSwag measure specific narrow capabilities (truthfulness, bias in
question-answering, commonsense reasoning) and are widely used in the
research community, but are not packaged as a composite, governance-
oriented trust score, nor do they distinguish self-reported from
independently measured results as a first-class feature of the standard
itself.

**Industry security standards.** PCI-DSS and ISO/IEC 27001 demonstrate the
publication pattern this work follows — an open, versioned standard
separable from any single accreditation body, with certification as an
optional paid layer atop a freely available specification. We adopt this
structure directly, substituting AI trustworthiness dimensions for payment
or information-security controls.

**This work's distinguishing claim** is not a novel scoring formula in
isolation, but the combination of (a) an open, versioned, code-synchronized
specification, (b) an explicit, labeled three-tier provenance model, and
(c) a public, per-score verification endpoint — together intended to keep
a "Trust Index score" a checkable claim rather than a marketing assertion,
even as the standard is cited by parties other than its original
publisher.

---

## 3. Methodology

### 3.1 Dimensions and weighting

A Trust Index score is a weighted composite across six dimensions, each
normalized to `[0, 1]` before weighting (Table 1).

**Table 1: Trust Index dimensions and default weights**

| Dimension | Weight | Definition |
|---|---|---|
| Fairness | 0.20 | Absence of detected bias across protected categories in system outputs. |
| Privacy | 0.15 | Avoidance of leaking or mishandling personally identifiable information. |
| Security | 0.20 | Resistance to adversarial manipulation (prompt injection, jailbreaks, data exfiltration, role-confusion). |
| Robustness | 0.15 | Factual reliability; resistance to hallucination. |
| Compliance | 0.20 | Regulatory/governance process maturity (documented audit trails, incident response, framework alignment). |
| Authenticity | 0.10 | For media-generating/evaluating systems: resistance to deepfake/synthetic-media misuse. Not applicable to text-only systems. |

The overall score is computed as:

```
overall_score = Σ(dimension_value_i × weight_i) × 100,  i ∈ {1..6}
```

producing a value in `[0, 100]`. Grade bands are defined as A ≥ 90, B ≥ 80,
C ≥ 70, D ≥ 60, F < 60; risk tiers as LOW ≥ 80, MEDIUM ≥ 60, HIGH ≥ 40,
CRITICAL < 40.

### 3.2 Handling not-applicable dimensions

Not every system under evaluation admits a meaningful measurement on every
dimension — a text-only system has no media-authenticity signal, for
instance. Rather than silently omitting a dimension (which would alter the
effective weighting distribution non-transparently) or fabricating a
measurement, we specify that a not-applicable dimension be held at a
disclosed neutral value of 0.5, with the disclosure itself a required part
of any citation. This design choice trades a small loss of precision for
transparency about what was actually measured versus assumed neutral.

### 3.3 Provenance: three distinct paths to a score

We argue that the central design risk for any open, citable trust standard
is *provenance conflation* — the failure to distinguish a self-reported
claim from an independently verified one once both produce numbers in the
same visible format. We address this directly by defining three
structurally distinct, separately labeled paths to a Trust Index score:

1. **Self-assessment** (free, unverified): a party submits its own
   dimension values and receives a permanently recorded, hashed record.
   The arithmetic is verifiable; the underlying input claims are not
   audited. Every self-assessed record is labeled `certified: false`
   everywhere it is displayed or returned via API.
2. **Automated measurement** (free, independently measured, narrower
   scope): dimensions are computed by directly querying a system's public
   inference API against a fixed evaluation corpus, without relying on
   self-reported values for the dimensions it covers. This is more
   credible than self-assessment but is only applicable to systems
   reachable through a public API, and — in our reference
   implementation — still holds the compliance and authenticity
   dimensions at the disclosed neutral placeholder, since those are not
   directly measurable via API probing alone.
3. **Human-reviewed certification** (paid, no automated path): a reviewer
   examines the evidence behind a submitted score and, if it holds up,
   marks the record `certified: true` with a named certifier and
   timestamp. We deliberately provide no automated route to this state —
   the moment certification could be self-served, it would cease to carry
   information beyond self-assessment.

### 3.4 Verification mechanism

Every generated record receives a stable identifier and a SHA-256
verification hash. A public endpoint
(`GET /api/trust-index/verify/{passport_id}`) returns the complete stored
record for any identifier; an unresolvable identifier returns an explicit
404, signaling that a citation referencing it is unverifiable. We treat
this mechanism — not the scoring formula alone — as the paper's central
methodological contribution: a trust claim that cannot be checked by a
party other than the one making it provides no more assurance than an
unstructured marketing statement, regardless of how principled its
underlying arithmetic is.

We additionally define a minimal citation format (Section 3.5) intended to
make every citation self-documenting with respect to provenance, and an
embeddable badge mechanism (`GET /api/trust-index/badge/{id}.svg`) that
renders the same provenance distinction visually ("Self-Assessed" vs.
"Certified") wherever a score is displayed outside the verification page
itself.

### 3.5 Citation format

We specify a minimum citation format requiring the scored value, grade,
specification version, explicit provenance label, and a verification URL:

> "[System] scored [X]/100 (Grade [Y]) under the [Standard Name] v[version]
> — [self-reported | certified by [certifier] on [date]]. Verify at
> [verify_url]."

---

## 4. Reference implementation

The methodology described here is implemented as open-source code
(`src/responsibleai/trust/score.py` for scoring;
`src/responsibleai/trust/passport.py` for record generation;
`src/responsibleai/db/passport_repository.py` for persistence and
verification). We consider synchronization between the published
specification and the running implementation a first-class design
requirement, not an afterthought: the specification document states
explicitly that the reference implementation's default weights are the
source of truth for the current version, and specification version bumps
are recorded as dated changelog entries alongside the corresponding code
change, rather than as an independently drifting paper standard.

---

## 5. Discussion and limitations

**No formal third-party accreditation process yet.** As of the current
specification version, certification is performed only by the standard's
originating team. We consider this an honest, stated limitation rather
than a design goal — a mature version of this standard would define how an
independent auditor could become an accredited certifier, analogous to
accreditation bodies for ISO management-system standards, but this is not
yet built.

**Point estimates without confidence intervals.** A Trust Index score is a
point estimate from a single evaluation run, not a distribution with error
bars. Future versions may incorporate repeated-measurement variance,
particularly for the automated-measurement provenance path, where
re-querying a live model's API could in principle surface score
volatility that a single measurement does not capture.

**Not a substitute for regulatory compliance certification.** Scoring well
under this standard is not itself a compliance certification for any
specific law or regulation. The compliance dimension references frameworks
such as GDPR and the EU AI Act as inputs to its own scoring, but a high
Trust Index score should not be represented, by any party citing it, as
equivalent to formal regulatory compliance.

**Self-assessment remains gameable in principle.** Nothing prevents a
self-assessing party from submitting favorable, unverified dimension
values. We view this as an accepted, disclosed limitation of the
self-assessment tier specifically (matching the explicit `certified: false`
labeling), not a flaw in the standard as a whole — the same way a
self-reported SAT score is arithmetically real but not independently
proctored, and is understood as such by anyone reading it correctly
labeled.

---

## 6. Conclusion

We present the Trust Index as an open, versioned, code-synchronized
methodology for scoring AI system trustworthiness, distinguished from
prior work primarily by its explicit three-tier provenance model and
public per-score verification mechanism. We publish the full specification
and reference implementation openly, in the pattern of established
security and payment-industry standards, with the goal that a Trust Index
citation become a checkable claim rather than a marketing assertion,
regardless of which party is doing the citing. We identify the absence of
a formal third-party accreditation process as the standard's most
significant current limitation and an explicit direction for future work.

---

## References

*(Populate with real, checkable citations before submission — do not
submit with placeholder references. Candidates to review and cite
properly, by their actual publication venues:)*

- Dwork, C., & Roth, A. (2014). *The Algorithmic Foundations of
  Differential Privacy.* [Relevant if citing this project's related
  `PRIVACY.md` differential-privacy work as prior art for the privacy
  dimension's measurement approach.]
- Lin, S., Hilton, J., & Evans, O. (2022). *TruthfulQA: Measuring How
  Models Mimic Human Falsehoods.* [Relevant to the robustness dimension
  and the `rai_benchmark` truthfulqa suite.]
- Parrish, A., et al. (2022). *BBQ: A Hand-Built Bias Benchmark for
  Question Answering.* [Relevant to the fairness dimension.]
- NIST. *AI Risk Management Framework (AI RMF 1.0).* National Institute of
  Standards and Technology, 2023.
- European Parliament and Council. *Regulation (EU) 2024/1689 (EU AI
  Act).*
- PCI Security Standards Council. *Payment Card Industry Data Security
  Standard (PCI-DSS).* [Cited as the structural model for open-standard
  publication with optional paid certification.]

---

## Before submitting this to arXiv

1. **Convert to arXiv's expected format.** LaTeX (via a standard template
   such as `article` or a relevant conference/journal class) is the safest
   choice; verify current format requirements on arXiv's own submission
   help pages before starting, since these can change.
2. **Verify the endorsement requirement for your target category** (likely
   `cs.CY` — Computers and Society, or `cs.AI`) — arXiv requires
   endorsement from an existing author in that category for some
   first-time submitters. Check this before assuming submission is
   friction-free.
3. **Replace every placeholder reference in Section "References"** with
   verified, correctly formatted citations to the actual papers/standards
   — do not submit with unchecked citations.
4. **Have a second, ideally domain-expert, reader review the paper** before
   submission — this draft was produced by the same team that built the
   system it describes, the same self-review limitation
   `compliance/INTERNAL_SECURITY_REVIEW.md` states plainly about its own
   findings. An independent read catches things self-review cannot.
5. **Re-verify every code/file reference** (`src/responsibleai/trust/score.py`,
   etc.) against the actual current codebase before submission — this
   paper describes the system as of its "Last reviewed" date above, and
   the code may have moved on by the time you actually submit.
