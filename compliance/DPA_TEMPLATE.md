# Data Processing Agreement (DPA) — DRAFT TEMPLATE

> ## ⚠️ This is a draft, not a legal document
>
> This template has **not been reviewed by an attorney**. Do not execute
> this with a customer, attach it to a contract, or represent it as
> binding until qualified legal counsel has reviewed it against your
> actual entity structure, jurisdiction, and the specific customer's
> requirements (GDPR, CCPA, or another regime may impose different
> mandatory clauses). This exists so a customer's legal team has a
> concrete starting point to redline, not a document to sign as-is.
>
> Filling in a sub-processor's name accurately (see below) does not make
> the surrounding legal language correct or enforceable — those are
> separate problems, and only the second one requires a lawyer.

Last reviewed: 2026-07-21 · Platform version: 1.2.0

---

## 1. Parties and scope

This Data Processing Agreement ("DPA") is entered into between:

- **Data Controller**: the customer entity licensing the ResponsibleAI
  Governance Platform ("Customer").
- **Data Processor**: Guruprasath Annadurai, operating as the
  ResponsibleAI project ("Processor").

This DPA applies to Processor's processing of personal data on behalf of
Customer in connection with Customer's use of the ResponsibleAI platform,
whether self-hosted by Customer or (if applicable) accessed via a
Processor-hosted instance.

**Self-hosted deployments**: for the majority of deployments — where
Customer runs the platform entirely within Customer's own infrastructure
— Processor does not process Customer's data at all. This DPA's
obligations on Processor apply only to the narrow surfaces below where
data actually reaches Processor-controlled or Processor-selected
infrastructure (e.g., a Processor-operated hosted instance, if Customer
subscribes to one).

---

## 2. Sub-processors

Processor uses the following sub-processors. Each is engaged only for the
specific purpose listed; no sub-processor receives data beyond what that
purpose requires.

| Sub-processor | Purpose | Data processed | Location | Sub-processor's own certifications |
|---|---|---|---|---|
| **Oracle Corporation (Oracle Cloud Infrastructure / OCI)** | Infrastructure hosting for the Processor-operated reference deployment (compute, block storage, networking) | All data stored by the platform when running on this infrastructure — trust scores, audit logs, cost/usage records, organization/API key metadata. Encrypted at rest by OCI Block Volume (AES-256, Oracle-managed keys) by default. | Single "home region" selected at deployment (see `compliance/CAIQ_SELF_ASSESSMENT.md` Domain 6 for the exact region and its constraints — no multi-region replication on the current tier). | Active SOC 2 attestation (CSA STAR, renewed 2026-05-21) and ISO/IEC 27001 certification (CSA STAR, renewed 2026-01-08), both verifiable at the [CSA STAR registry](https://cloudsecurityalliance.org/star/registry/oracle-corporation/services/oracle-cloud-infrastructure). |
| **Stripe, Inc.** | Payment processing and subscription billing (only if Customer is on a paid PRO/ENTERPRISE plan) | Billing contact and subscription metadata only — **no governance data** (trust scores, audit logs, prompts, model outputs) is ever sent to Stripe. See `src/responsibleai/billing/stripe_service.py`. | Per Stripe's own data processing terms and infrastructure (Stripe maintains its own PCI-DSS Level 1 certification, published separately by Stripe). | Stripe's own published compliance documentation — Processor is a sub-processor's customer here, not a re-certifier of Stripe's controls. |
| **Customer's own OIDC/SSO identity provider** (Okta, Azure AD, Google Workspace, etc.), *if Customer enables SSO* | Authentication only | Authentication claims (email, name, role/group membership) passed at login — no governance data. | Per Customer's own IdP choice and configuration — Processor does not select this sub-processor, Customer does. | Not applicable — this is Customer's own vendor relationship, listed here for completeness since it is a data flow, not because Processor selected it. |
| **LLM providers** (OpenAI, Anthropic, Google, etc.), *only if Customer configures the cost-tracking/eval modules to call them* | Model evaluation and cost tracking, at Customer's explicit configuration | Whatever Customer's own integration sends — under Customer's own account and API keys with that provider, not Processor's. | Per each provider's own infrastructure and terms. | Not applicable — Customer's own vendor relationship and contract, not a Processor sub-processor relationship in the traditional sense; listed for transparency since it is a real data flow Customer should be aware of. |

**Sub-processor changes**: Processor will update this list and notify
Customer (via the contact on file) at least 30 days before adding or
replacing a sub-processor that will process Customer's personal data,
except where a shorter notice period is required for security or legal
reasons. *(This clause, and its exact notice period, is a placeholder —
confirm the correct standard with counsel before relying on it.)*

---

## 3. Nature and purpose of processing

Processor processes personal data solely to provide the ResponsibleAI
governance platform's functionality: AI trust scoring, guardrail scanning
(PII/toxicity detection), compliance evaluation, cost/usage tracking, and
audit logging, as configured by Customer.

Processor does not use Customer's data for any purpose other than
providing the service, and does not sell, rent, or otherwise
commercially exploit Customer's data.

---

## 4. Categories of data subjects and personal data

- **Data subjects**: Customer's own end users, employees, or other
  individuals whose data passes through Customer's use of the platform
  (e.g., individuals named in text scanned by the Guardrails Engine,
  or Customer's own personnel who hold platform API keys/accounts).
- **Categories of personal data**: dependent entirely on what Customer
  sends to the platform. The platform itself does not require personal
  data to function — API keys are hashed, audit logs record endpoint/
  method/timing metadata (not request bodies) by default. Any PII that
  ends up in scanned text, model prompts, or responses is Customer's own
  data, processed only as configured.

---

## 5. Security measures

Processor implements the technical and organizational measures described
in `ENTERPRISE_SECURITY.md`, `compliance/CAIQ_SELF_ASSESSMENT.md`, and
`compliance/NIST_CSF_SELF_ASSESSMENT.md`, including but not limited to:

- Role-based access control, SSO with enforceable SSO-only mode
- Hash-chained, tamper-evident audit logging
- Multi-tenant data isolation by organization ID
- Encryption at rest (infrastructure-dependent — see Section 2's OCI entry
  for the reference deployment's specifics)
- Dependency vulnerability scanning on every code change

**Stated honestly, per this project's standing practice**: Processor has
**not** completed a SOC 2 or ISO 27001 audit of its own. The measures
above are self-assessed and documented, not third-party certified. If
Customer's own compliance program requires a certified processor, this
DPA should not be executed until that changes — say so now, not after
signing.

---

## 6. Data subject rights assistance

Processor will provide reasonable assistance to Customer in responding to
data subject requests (access, deletion, correction, portability) to the
extent the requested data resides in Processor-controlled systems. For
self-hosted deployments, Customer controls this data directly and this
section is not applicable.

*(The exact assistance timeline and cost allocation is a placeholder —
this is precisely the kind of clause that varies by jurisdiction and
should be set by counsel, not left as a default.)*

---

## 7. Breach notification

Processor will notify Customer of a confirmed personal data breach
affecting Customer's data without undue delay.

**Stated honestly**: as flagged in `compliance/NIST_CSF_SELF_ASSESSMENT.md`'s
Respond function, Processor does not yet have a formal breach-notification
SLA with a specific committed timeframe (e.g., GDPR's 72-hour requirement
to the supervisory authority). **Do not execute a DPA that requires a
specific breach-notification timeframe until that internal process
actually exists** — this is listed as a known gap, not papered over.

---

## 8. International data transfers

Processing occurs in the sub-processors' locations listed in Section 2.
Where this involves a transfer across a data-protection boundary (e.g.,
GDPR's international transfer restrictions), the appropriate transfer
mechanism (Standard Contractual Clauses, adequacy decision, etc.) must be
confirmed by counsel for Customer's specific jurisdiction — not assumed
from this template.

---

## 9. Term and termination

This DPA remains in effect for the duration of the underlying services
agreement between Customer and Processor. Upon termination, Processor
will delete or return Customer's data per Customer's instruction, subject
to any legal retention requirements.

---

## 10. Liability

*(Deliberately left blank — liability allocation, caps, and indemnification
are exactly the terms a lawyer needs to set based on the actual contract
value, insurance coverage, and jurisdiction. Do not fill this in from a
template found in a repository.)*

---

## Before using this document

1. Have an actual attorney review it against your jurisdiction and the
   specific customer's requirements.
2. Confirm the sub-processor list above is still accurate — it reflects
   this platform's state as of the date at the top of this document, not
   a permanent guarantee. Check `ENTERPRISE_SECURITY.md`'s "Third-party
   data flows" section for the current list before relying on this one.
3. Fill in Sections 6, 7, 8, and 10 with real, counsel-approved terms —
   they are intentionally incomplete here.
4. Do not send this to a customer as a final document. Send it as "here's
   our starting draft" if a customer's legal team wants to see your
   posture before their own redline — that's the only advisable use of
   an unreviewed template.
