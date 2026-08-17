# Privacy Policy

> ## ⚠️ Provenance notice — read before relying on this document
>
> This policy is **self-drafted and has not been reviewed by a licensed
> attorney**. Every substantive commitment below (retention periods,
> response timeframes, legal bases, security measures) is written as a
> firm, adopted operating policy — not a placeholder — because that is
> what a corporate-grade privacy policy requires. What it is **not** yet:
> validated by counsel against every jurisdiction it claims to address.
> Treat the commitments below as Provider's genuine, current operating
> standard, and treat the *absence of legal certification* as the one
> open risk, not the completeness of the content. Do not represent this
> document as attorney-certified until it actually is.
>
> Data categories in Section 3 were cross-checked against what the live
> hosted instance (`whitepact.com`, formerly reachable only at
> `responsibleai-dashboard.onrender.com` — that URL still works
> unchanged; `whitepact-mcp-http.onrender.com`) actually stores as of
> the date below — a real spot-check, not an assumption.
>
> **Relationship to `PRIVACY.md`**: that document covers the
> differential-privacy mathematical guarantees of the `PrivacyLabel`
> federated-learning module specifically — narrow technical documentation
> for one feature. This document is the general-purpose privacy policy
> for the platform as a whole. Both are needed; neither replaces the
> other.

**Effective date / Last reviewed:** 2026-08-13 · **Platform version:** 1.2.3

---

## 1. Data Controller

**Guruprasath Annadurai**, operating as the WhitePact / ResponsibleAI
project ("**Provider**," "**we**," "**us**," "**our**"), is the data
controller for personal data processed in connection with a
Provider-operated hosted instance of the Service and Provider's public
project touchpoints (Section 4).

**Privacy contact:** annaduraiguruprasath7@gmail.com — the same
security/privacy contact published in `SECURITY.md` and `SLA.md`. No
separate Data Protection Officer has been formally appointed; the privacy
contact above serves that function today.

---

## 2. Scope

This Privacy Policy applies to:

- **The Provider-operated hosted instance of the Service** — currently a
  **free tier only**; no paid hosted tier or enterprise agreement is live
  as of this version (see `SLA.md` Scope section). Data categories in
  Section 3 describe what the free-tier hosted instance actually
  collects today.
- **Provider's public project touchpoints**, which exist independent of
  hosting status: the public Trust Leaderboard, Trust Index verification
  pages, and AI Incident Database (Section 5).

**This Policy does not apply to self-hosted deployments.** When Customer
runs the platform entirely on its own infrastructure, Provider does not
collect, process, transmit, or have access to any of Customer's data.
Customer is solely responsible for its own privacy commitments to its own
end users in that mode, using Customer's own privacy policy.

---

## 3. Information We Collect

We apply data minimization: we collect only what is necessary to operate
the Service, secure it, bill for it, and comply with legal obligations.

| Category | Specific data | Purpose | Legal basis (GDPR Art. 6) |
|---|---|---|---|
| Account/organization data | Organization name, slug, billing contact email (processed via Stripe) | Providing the Service; billing | Contract |
| API key metadata | Key name, role, creation/last-used timestamps, SHA-256 hash of the key (the raw key itself is never stored) | Authentication; access control | Contract; legitimate interest (security) |
| Audit log metadata | Endpoint, method, status code, timing, IP address (opt-in, field-encrypted — see `db/encryption.py`) | Security monitoring; tamper-evident governance logging | Legitimate interest; legal obligation where audit trails are regulatorily required |
| Content Customer submits | Prompts, model outputs, or text submitted to guardrail/trust-scoring/hallucination-detection endpoints | Providing the Service's core evaluation functionality | Contract |
| MFA enrollment data | TOTP secret, hashed backup codes (opt-in, field-encrypted) | Multi-factor authentication, where Customer's org enables it | Consent (opt-in feature) |

**We do not require personal data to operate the platform's core
functionality.** Content Customer submits for evaluation may incidentally
contain personal data (e.g., a prompt referencing a name or email
address) — that is Customer's data, submitted at Customer's discretion,
and is processed solely to return the evaluation result, not collected
independently by Provider for any other purpose.

**We do not use cookies or similar tracking technologies for advertising
or cross-site tracking.** The hosted dashboard uses only strictly
necessary session cookies for authentication; no third-party analytics
or advertising trackers are deployed as of this version.

---

## 4. How We Use Information

We use personal data solely for the following purposes, each tied to the
legal basis in Section 3:

- Authenticating requests and enforcing access control.
- Computing trust scores, guardrail results, and other evaluation output
  Customer requests.
- Maintaining the tamper-evident audit log.
- Processing payment, once a paid hosted tier exists (via Stripe).
- Responding to support requests and privacy-rights requests.
- Detecting, investigating, and preventing security incidents, fraud, and
  abuse.
- Complying with legal obligations (e.g., responding to a lawful request
  from a regulator or court).

**We do not sell personal data.** We do not share, rent, or trade
personal data with third parties for their own marketing purposes. **We
do not use Customer's submitted content to train any model Provider
operates**, and do not share it with third-party LLM providers except
where Customer's own configuration explicitly routes it there (e.g.,
Customer supplying their own OpenAI/Anthropic API key for cost tracking
— in that case, the third-party provider's own privacy policy governs
that specific transmission, not this one).

---

## 5. Public Features — A Different Privacy Posture

Three features are **intentionally public by design**. Submitting to
them carries different expectations than ordinary account data:

- **AI Incident Database** (`/incident-db`): reports are reviewed by a
  moderator before publication. Reporter name and contact are opt-in,
  field-encrypted, and never shown publicly. Published incident details
  (title, description, affected model/provider) are **public and
  permanent** once published, matching a CVE-style public registry
  model. Do not submit anything you do not want public.
- **Trust Leaderboard** (`/leaderboard`) and **Trust Index verification
  pages** (`/verify/{passport_id}`): trust scores and the models/providers
  they are computed against are public by design — this is the point of
  an open, independently checkable trust standard
  (`compliance/TRUST_INDEX_SPEC.md`). No personal data is expected here
  beyond whatever a self-assessing organization chooses to attribute a
  score to.

---

## 6. Sub-processors

See `compliance/DPA_TEMPLATE.md` Section 2 for the current, detailed
sub-processor list (Render, Supabase, and Upstash for hosting; Stripe for
billing; Customer's own chosen OIDC provider for SSO; and any LLM
providers Customer configures). That document is the authoritative
source; this Policy incorporates it by reference rather than duplicating
a list that would drift out of sync if maintained in two places.

We remain responsible for our sub-processors' handling of personal data
under data processing agreements consistent with `compliance/DPA_TEMPLATE.md`.
We will provide advance notice via the contact in Section 1 before adding
a new sub-processor that materially changes how personal data is
processed.

---

## 7. Data Retention

We retain personal data only as long as necessary for the purposes in
Section 4, applying the following defined periods as our current adopted
policy:

| Data category | Retention period |
|---|---|
| Account/organization data | Duration of the account relationship, plus 90 days post-termination for legal/audit purposes, then deleted or anonymized. |
| Audit log metadata | 12 months from creation, then deleted, unless a longer period is legally required in Customer's jurisdiction. |
| Submitted evaluation content | Not retained beyond what is needed to return the result and, where applicable, populate Customer's own result history — deleted within 30 days of submission unless Customer's plan tier explicitly includes longer result history. |
| MFA enrollment data | Duration of enrollment; deleted immediately upon MFA disablement or account deletion. |
| Billing records | Retained per Stripe's own retention policy and applicable tax/accounting law (typically 7 years), independent of Provider's own retention of other categories. |

**Current implementation status, stated plainly**: as of this version, no
automated deletion job enforces the schedule above against the live
database — the schedule is Provider's adopted policy, not yet a fully
automated technical guarantee. This gap is tracked in
`FOUNDER_ACTION_CHECKLIST.md` and will be resolved before this Policy is
treated as complete.

---

## 8. Your Privacy Rights

### 8.1 For all users (GDPR-equivalent rights, offered regardless of jurisdiction)

You have the right to:

- **Access** — obtain a copy of the personal data we hold about you.
- **Rectification** — correct inaccurate or incomplete personal data.
- **Erasure** — request deletion of your personal data, subject to
  legal retention obligations (Section 7).
- **Restriction** — request that we limit processing in specific
  circumstances.
- **Portability** — receive your personal data in a structured,
  commonly used, machine-readable format.
- **Objection** — object to processing based on legitimate interest.
- **Withdraw consent** — where processing is based on consent (e.g.,
  MFA enrollment), withdraw it at any time without affecting the
  lawfulness of processing before withdrawal.

**Response timeframe: we will respond to a verified rights request within
30 calendar days.** If a request is complex, we will notify you within
that period and provide a final response within 60 calendar days total.

### 8.2 California residents (CCPA/CPRA)

In addition to Section 8.1, California residents have the right to:

- **Know** what categories of personal data we collect and for what
  purpose (Section 3).
- **Delete** personal data, subject to statutory exceptions.
- **Opt out of sale or sharing** — not applicable in practice, since we
  do not sell or share personal data as defined by the CCPA/CPRA.
- **Non-discrimination** — we will not deny service, charge a different
  price, or provide a different level of service for exercising a
  privacy right.

**Response timeframe: we will confirm receipt within 10 business days and
substantively respond within 45 calendar days**, extendable once by an
additional 45 days where reasonably necessary, with notice.

### 8.3 How to exercise these rights

Contact **annaduraiguruprasath7@gmail.com** with your request. We will
verify your identity before fulfilling access, deletion, or portability
requests to prevent unauthorized disclosure of your data to a third
party.

**Self-hosted Customers**: your organization controls this data directly
and must handle end-user rights requests using your own systems —
Provider has no access to self-hosted data and cannot fulfill a request
on your behalf.

---

## 9. International Data Transfers

Personal data may be processed in the sub-processor locations listed in
`compliance/DPA_TEMPLATE.md` Section 2. Where a transfer crosses a
data-protection boundary (for example, GDPR's restrictions on
international transfers out of the EU/EEA/UK), we rely on Standard
Contractual Clauses or an equivalent recognized transfer mechanism with
the relevant sub-processor, consistent with `compliance/DPA_TEMPLATE.md`
Section 8. **Stated honestly**: the specific transfer mechanism per
sub-processor has not yet been individually confirmed by counsel for
every jurisdiction this Policy addresses — see the provenance notice at
the top of this document.

---

## 10. Security

Security measures are described in `ENTERPRISE_SECURITY.md` and
self-assessed in detail in `compliance/CAIQ_SELF_ASSESSMENT.md` and
`compliance/NIST_CSF_SELF_ASSESSMENT.md`. Concretely:

- Encryption at rest for the database is infrastructure-dependent
  (deployer's responsibility for self-hosted; managed by our hosting
  sub-processor for the hosted instance).
- Specific PII/secret columns (audit log IPs, incident reporter contact
  info, webhook secrets, MFA seeds) use opt-in, application-layer field
  encryption via `RAI_FIELD_ENCRYPTION_KEY` — see `compliance/KEY_MANAGEMENT.md`.
- Transport is TLS-only; the hosted instance does not accept plaintext
  HTTP for any endpoint that could carry personal data.

**Stated honestly**: no SOC 2 or ISO 27001 certification exists as of
this version, and no third-party penetration test has been performed —
only an automated baseline scan (`scripts/security-scan.sh`) and an
internal review (`compliance/INTERNAL_SECURITY_REVIEW.md`). We will not
represent either certification as held until it genuinely is.

**Breach notification**: in the event of a confirmed personal data
breach, we will notify affected Customers without undue delay and, where
feasible, within 72 hours of becoming aware of the breach, consistent
with GDPR Article 33's timeframe — adopted here as our operating
standard regardless of whether GDPR specifically applies to a given
Customer. See `compliance/INCIDENT_RESPONSE_RUNBOOK.md` for the
operational process behind this commitment.

---

## 11. Children's Privacy

The Service is not directed at children, and we do not knowingly collect
personal data from children under 16. If we become aware that we have
collected personal data from a child under 16 without verified parental
consent, we will delete it promptly. We apply 16 as our operating
threshold platform-wide (the stricter of COPPA's 13 and GDPR's default
16) rather than varying it by jurisdiction, to keep this commitment
simple and unambiguous.

---

## 12. Changes to This Policy

Material changes will be reflected by an updated "Effective date / Last
reviewed" line at the top of this document. For changes that materially
reduce your rights or expand how we use your data, we will provide notice
via the contact information on file for your organization at least 30
days before the change takes effect, where practicable. Immaterial
changes (e.g., correcting a stale factual claim, as in the 2026-08-13
revision) may be made without advance notice, but will still update the
effective date.

---

## 13. Contact and Complaints

Questions, requests, or complaints about this Policy: **annaduraiguruprasath7@gmail.com**.

**EU/EEA/UK residents**: you also have the right to lodge a complaint
with your local data protection supervisory authority if you believe we
have not adequately addressed your concern.

---

## Before treating this document as complete

1. **Have an actual attorney review it** against your specific
   jurisdiction(s), entity structure, and insurance coverage. This
   document adopts firm, specific commitments deliberately — that makes
   it stronger to review, not a substitute for review.
2. Do not represent this Policy as attorney-certified until that review
   is complete, even though it is no longer written with open
   placeholders.
3. Confirm Section 7's retention periods and Section 9's transfer
   mechanisms are actually implemented as described, not just documented
   — Section 7 already states honestly where enforcement is not yet
   automated.
4. Publish this alongside, not instead of, `TERMS_OF_SERVICE.md` — a
   privacy policy without matching terms of service is an incomplete
   legal foundation for a service that touches personal data.
