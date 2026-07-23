# Terms of Service — DRAFT

> ## ⚠️ This is a draft, not a binding legal document
>
> This template has **not been reviewed by an attorney**. Do not publish
> this as your live Terms of Service, link it from a signup flow, or treat
> it as enforceable until qualified legal counsel has reviewed it against
> your actual entity structure, jurisdiction, insurance coverage, and the
> specific risk profile of what you're selling. Liability caps,
> indemnification, arbitration/venue clauses, and warranty disclaimers are
> exactly the terms that need a lawyer's judgment, not a template's
> defaults — several sections below are deliberately left as placeholders
> for that reason, the same way `compliance/DPA_TEMPLATE.md` leaves its
> liability section blank rather than guess.
>
> This exists so you have a concrete, platform-accurate starting point to
> hand to an attorney — not a document to publish as-is.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. Who this is between

These Terms of Service ("Terms") govern access to and use of the
ResponsibleAI Governance Platform ("Service"), operated by Guruprasath
Annadurai, operating as the ResponsibleAI project ("Provider," "we," "us").
"Customer" or "you" means the individual or entity that creates an
account, deploys the self-hosted software, or otherwise uses the Service.

**Entity structure placeholder**: this document assumes a sole proprietor
/ individual operator, matching `compliance/DPA_TEMPLATE.md`'s existing
"Data Processor: Guruprasath Annadurai" framing. If a company entity
(LLC, C-corp, etc.) is formed before this goes live, every reference here
needs to be updated to match — that is a real legal distinction (personal
vs. limited liability), not a copy-edit.

---

## 2. What the Service is (and isn't, yet)

The Service is AI governance tooling: trust scoring, guardrail scanning
(PII/toxicity detection), hallucination detection, compliance evaluation
against frameworks like the EU AI Act and NIST AI RMF, cost intelligence,
model routing, drift monitoring, and audit logging, delivered as:

- **Self-hosted software** (source available under the repository's MIT
  license) that Customer deploys and operates on Customer's own
  infrastructure — the FREE tier and the primary way this platform is
  used today.
- **A hosted MCP endpoint and/or hosted dashboard**, if and when Provider
  operates one — **as of this version, no Provider-operated hosted
  instance is live**. See `SLA.md`'s Scope section, which states this
  plainly. These Terms apply to a hosted offering once one exists; until
  then, the sections below describing "the Service" as something Provider
  operates should be read as forward-looking, not a claim about today.

Do not sign a customer up for a hosted subscription, or represent a
hosted tier as available, until a hosted instance is actually live and
this caveat is removed.

---

## 3. Accounts, API keys, and organizations

- Provider does not manage user passwords. Access is via API key (issued
  through `POST /api/orgs/{id}/keys`, hashed at rest, shown once at
  creation and never recoverable) or via Customer's own OIDC/SSO identity
  provider, per `ENTERPRISE_SECURITY.md`.
- Customer is responsible for safeguarding API keys and for all activity
  under them, including revoking a key immediately if it may be
  compromised (`DELETE /api/orgs/{id}/keys/{key_id}`).
- Customer is responsible for its organization's users, roles (Owner /
  Admin / Analyst / Viewer), and any multi-factor authentication policy it
  chooses to enforce (`PUT /api/orgs/{id}/mfa`).
- For self-hosted deployments, Customer controls its own database,
  encryption keys, and infrastructure entirely — Provider has no access
  to Customer's data in that mode and cannot recover it if Customer loses
  its own database or encryption key (`RAI_FIELD_ENCRYPTION_KEY`).

---

## 4. Acceptable use

Customer will not use the Service to:

- Violate any applicable law, or the rights of any third party.
- Attempt to gain unauthorized access to the Service, other customers'
  data, or the infrastructure the Service runs on.
- Reverse engineer, decompile, or attempt to extract the underlying
  models or scoring logic where restricted by the plan tier's license
  terms (not applicable to the self-hosted, MIT-licensed core — see
  `LICENSE`).
- Use the Service's guardrail/red-team/adversarial-testing tools against
  systems Customer does not own or have explicit authorization to test.
  These tools exist for defensive testing of Customer's own AI systems,
  not for attacking third parties.
- Resell or sublicense hosted access without Provider's written consent,
  where a hosted tier exists.

Provider may suspend or terminate access for a violation of this section,
with notice where reasonably practicable.

---

## 5. Billing (PRO / ENTERPRISE plans)

- Plan tiers, pricing, and included tool access are published at
  `GET /api/billing/plans` and summarized in `SLA.md`. What's shown there
  is authoritative over any older figure quoted elsewhere.
- Payment processing is handled by Stripe, Inc. Provider does not receive
  or store raw payment card data — see `compliance/DPA_TEMPLATE.md`
  Section 2 for the sub-processor detail.
- **Refunds, proration, and cancellation terms**: *(placeholder — set by
  counsel and by the actual payment processor configuration before this
  goes live; do not invent a refund policy here without confirming it
  matches what Stripe's configured billing settings actually do.)*
- Failure to pay may result in suspension of hosted access. Self-hosted
  deployments are unaffected by billing status for a hosted tier Customer
  isn't using.

---

## 6. Service Level Agreement

Uptime targets, support tiers, and maintenance windows are defined in
`SLA.md`, incorporated here by reference. As that document states
directly: **self-hosted uptime targets are design recommendations, not an
enforceable commitment** on infrastructure Provider doesn't operate, and
**hosted-tier commitments only become real once a hosted instance is
actually live** — this is the same caveat as Section 2 above, stated
again here because it's the single most load-bearing fact in this whole
document for an enterprise buyer.

---

## 7. Intellectual property

- The self-hosted platform's source code is licensed under the terms in
  `LICENSE` (MIT). Nothing in these Terms restricts rights already
  granted by that license for the self-hosted software.
- Customer retains all rights to its own data — prompts, model outputs,
  evaluation results, and any other content Customer submits to or
  generates through the Service.
- Provider retains rights to the Service's own branding, the "Trust
  Index" scoring methodology (`compliance/TRUST_INDEX_SPEC.md`), and the
  public leaderboard/incident-database infrastructure, apart from
  Customer's own submitted data within them.

---

## 8. Confidentiality

Each party will protect the other's confidential information with at
least the same care it uses for its own confidential information, and
not disclose it except as needed to provide or use the Service, or as
required by law.

*(Placeholder — a real confidentiality clause should define
"confidential information" precisely and set a term; this is a
reasonable default, not a substitute for counsel's specific language.)*

---

## 9. Disclaimers

**Stated honestly, matching this project's standing practice of not
overselling controls that don't exist yet** (see `ENTERPRISE_SECURITY.md`
and `compliance/CAIQ_SELF_ASSESSMENT.md` for the full detail):

- The Service is provided on an "as is" and "as available" basis.
- Provider has **not** completed a SOC 2 or ISO 27001 audit as of this
  version. Trust and security claims made elsewhere in this repository
  are self-assessed and documented, not third-party certified — if
  Customer's procurement process requires a certified vendor, that gap
  should be surfaced now, not discovered after signing.
- Provider has **not** completed a third-party penetration test as of
  this version — only an automated OWASP ZAP baseline scan
  (`scripts/security-scan.sh`) and an internal security review
  (`compliance/INTERNAL_SECURITY_REVIEW.md`), neither of which is a
  substitute for one.
- The Service's trust scores, compliance classifications, hallucination
  detection, and guardrail scanning are automated heuristics and
  statistical estimates, not legal or compliance advice, and not a
  guarantee that any AI system evaluated through the Service is safe,
  unbiased, or compliant with any specific law or regulation. Customer
  remains responsible for its own compliance obligations.

**Warranty disclaimer language (implied warranties of merchantability,
fitness for a particular purpose, etc.)**: *(placeholder — jurisdiction-
specific; set by counsel.)*

---

## 10. Limitation of liability

*(Deliberately left blank — liability caps, indemnification, and the
types of damages excluded (consequential, indirect, etc.) are exactly the
terms that need to be set based on actual contract value, insurance
coverage, and jurisdiction, the same reasoning
`compliance/DPA_TEMPLATE.md` Section 10 already applies to its own
liability section. Do not fill this in from a template found in a
repository.)*

---

## 11. Data processing and privacy

Where the Service processes personal data on Customer's behalf, the terms
of `compliance/DPA_TEMPLATE.md` apply — itself still a draft pending
attorney review, per its own header. General data-handling posture is
described in `ENTERPRISE_SECURITY.md`.

**Note on `PRIVACY.md`**: the existing `PRIVACY.md` in this repository
documents the differential-privacy guarantees of the federated-learning
module (`PrivacyLabel`) specifically — it is technical documentation for
that feature, not a general privacy policy describing how the platform
as a whole collects, uses, and discloses personal data. A real privacy
policy covering the whole Service (what's collected at signup, cookies/
analytics if any, data retention, deletion rights, international
transfers) does not yet exist and should be drafted and reviewed
alongside these Terms before either is published live.

---

## 12. Termination

- Customer may stop using the Service at any time; for self-hosted
  deployments, this is simply stopping the software.
- For a hosted tier, either party may terminate for the other's material
  breach not cured within a reasonable period, or as otherwise specified
  in an order form / master agreement once one exists.
- Upon termination, Provider will handle Customer data per the DPA
  (Section 6 there — data subject rights and deletion) and per Customer's
  own instruction, subject to legal retention requirements.

---

## 13. Governing law and disputes

*(Placeholder — governing law, venue, and whether disputes are resolved
by arbitration or litigation are jurisdiction- and counsel-specific
decisions. Do not select a jurisdiction here without legal advice; the
"wrong" default can meaningfully disadvantage either party.)*

---

## 14. Changes to these Terms

Provider may update these Terms. Material changes will be noted with an
updated "Last reviewed" date at the top of this document, consistent with
how `SLA.md` and `compliance/DPA_TEMPLATE.md` are versioned. Continued use
of the Service after a material change constitutes acceptance.

*(Placeholder — the actual notice mechanism, e.g. email notification for
paying customers, should be decided and stated explicitly before this is
relied upon.)*

---

## Before using this document

1. Have an actual attorney review it against your jurisdiction, your
   actual entity structure (Section 1), and your insurance coverage —
   Sections 5 (refunds), 8 (confidentiality), 9 (warranty disclaimer), 10
   (liability), 12 (termination for a hosted tier), and 13 (governing
   law) are intentionally incomplete or generic here.
2. Do not publish this, link it from a signup or checkout flow, or
   represent it as binding until that review is complete.
3. Keep Section 2 and Section 6's "no hosted instance is live yet"
   caveats accurate — remove them only once a Provider-operated hosted
   instance is actually live, not in anticipation of one.
4. Pair this with a real privacy policy (see Section 11) before either
   goes live — a Terms of Service without a matching privacy policy is
   an incomplete legal foundation for a service that touches personal
   data, and this repository does not yet have one.
