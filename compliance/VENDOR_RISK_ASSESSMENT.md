# Vendor Risk Assessment — ResponsibleAI Platform

Structured evaluation of the platform's third-party dependencies, closing
the gap `compliance/NIST_CSF_SELF_ASSESSMENT.md`'s GV.SC row used to flag:
"no formal vendor risk assessment process for third-party services —
informal today." This document is that process, applied to the actual
sub-processor list in `SLA.md` and `compliance/DPA_TEMPLATE.md` Section 2.

This is a solo-founder self-assessment, not a third-party audit — same
caveat as every other compliance document in this repo. Where a fact is
independently verifiable (a certification, a registry entry), a source is
cited; where it isn't, that's stated rather than implied.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## Assessment methodology

For each vendor: what data reaches them, what happens if they have an
outage or breach, what independent verification exists, and what the
actual residual risk is once contractual/technical controls are applied.
Reviewed opportunistically today (no scheduled cadence yet — see "What
this doesn't cover" below), not on a fixed calendar.

---

## Google Cloud Platform (GCP)

**Updated 2026-07-23**: switched from Oracle Cloud Infrastructure — OCI's
Always Free signup required a credit card the founder chose not to
provide; GCP's $300/90-day free-trial credit was the workable
alternative. This is a vendor *and* a risk-profile change, not just a
rename — the residual-risk row below reflects that honestly.

**Role**: infrastructure hosting for the reference deployment — compute,
block storage, networking. See `compliance/CAIQ_SELF_ASSESSMENT.md`
Domain 6 for exact region/instance/credit details (`e2-medium` or
`e2-standard-2` Compute Engine instance, single region, no automatic
cross-region failover, $300/90-day free-trial credit — not a permanent
free tier).

| Question | Answer |
|---|---|
| What data reaches them? | Everything — this is the infrastructure the database and application run on. Full access in principle (as with any IaaS host), governed by Google's own personnel/access controls, not ours. |
| Independent certification? | Active SOC 2/SOC 3 reports and ISO/IEC 27001, 27017, 27018 certifications — see [cloud.google.com/security/compliance/soc-2](https://cloud.google.com/security/compliance/soc-2), checked directly, not taken from marketing copy. |
| What if GCP has an outage? | Single-region deployment has no cross-region failover — a GCP regional outage is a platform outage. Documented in `SLA.md`'s DR section, not hidden. Persistent disk storage is encrypted at rest by default regardless (AES-256), independent of the outage question. |
| What if GCP has a breach affecting us? | Contractually, Google's own incident-notification obligations under its customer agreement apply (not something this project has separately negotiated — free-trial terms are Google's standard terms, not custom-negotiated). Practically: rotate all secrets, treat as a P1 per `compliance/INCIDENT_RESPONSE_RUNBOOK.md`. |
| **New risk this vendor introduces that OCI didn't**: the 90-day credit expiry | Unlike OCI's permanent Always Free tier, this reference deployment has a **hard, dated obligation** — track the account creation date and plan a migration-or-pay decision before day 90 (`DEPLOY_RUNBOOK.md`'s prerequisites section states this explicitly). Letting the credit lapse silently would be a self-inflicted outage, not a vendor-caused one — worth flagging as a distinct risk category from the outage/breach rows above. |
| Residual risk | **Medium-to-High while the credit-expiry date is untracked; Medium once a migration/payment plan is confirmed before day 90.** Real vendor lock-in and single-region exposure, offset by verified certification status and encryption-by-default — same underlying profile as the prior OCI assessment, plus the new time-boxed-credit risk above. Appropriate for the current pre-revenue stage; a paid multi-region tier or committed GCP billing (removing the credit-expiry risk) is the documented upgrade path once justified (see Domain 6). |
| Alternative considered? | Yes — GCP was chosen over OCI specifically because of the credit-card requirement at OCI signup; other alternatives (Hetzner, DigitalOcean, AWS) remain viable if GCP stops being the right fit before or after the credit expires. |

---

## Stripe, Inc.

**Role**: payment processing and subscription billing (PRO/ENTERPRISE
plans only). No governance data (trust scores, audit logs, token usage)
reaches Stripe — billing metadata only (customer ID, subscription ID,
plan tier; see `billing/stripe_service.py`).

| Question | Answer |
|---|---|
| What data reaches them? | Billing metadata and whatever payment details the customer enters directly into Stripe's own hosted checkout (never touches this application's servers — Stripe Checkout is redirect-based, not embedded). |
| Independent certification? | Stripe's own published PCI-DSS Level 1 certification — the highest tier, required for any payment processor handling card data directly. Not independently re-verified here beyond Stripe's own public disclosures. |
| What if Stripe has an outage? | Checkout/billing-portal endpoints fail; the core governance platform (evaluation, guardrails, trust scoring, audit log) is unaffected since none of it depends on Stripe at request time. |
| What if Stripe has a breach affecting us? | Card data itself was never held by this application (PCI scope stays with Stripe), limiting exposure to billing metadata (customer/subscription IDs) rather than payment instruments. |
| Residual risk | **Low** — narrow data-sharing scope (metadata only, no card data ever transits this app), Stripe's own PCI-DSS Level 1 status, and no functional dependency for the core product if billing is briefly unavailable. |

---

## Customer's own OIDC/SSO provider (when SSO is enabled)

**Role**: authentication only, when a customer configures SSO
(`RAI_OIDC_ISSUER` etc. — see `ENTERPRISE_SECURITY.md`'s SSO section).

| Question | Answer |
|---|---|
| What data reaches them? | Nothing beyond a standard OAuth2/OIDC authorization-code exchange — this application authenticates *against* the customer's chosen IdP, it doesn't send the IdP any governance data. |
| Independent certification? | Not applicable to assess here — this is the customer's own vendor choice (Okta, Azure AD, Google Workspace, etc.), not one this project selects, contracts with, or certifies on the customer's behalf. Per `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`, whether "sub-processor" is even the right legal term for this row is one of the open questions for attorney review. |
| What if the customer's IdP has an outage? | SSO-enforced orgs (`sso_required=true`) lose the ability to log in until the IdP recovers — a real dependency the customer takes on by enabling SSO enforcement, documented in `ENTERPRISE_SECURITY.md`, not hidden. |
| Residual risk | **N/A / customer-owned** — this project has no vendor relationship with the customer's IdP to assess; the customer's own vendor management applies. |

---

## LLM providers (OpenAI, Anthropic, Google, etc.), when configured

**Role**: model evaluation and cost tracking, under the customer's own
account and API keys — this application calls these providers on the
customer's behalf using credentials the customer supplies and controls.

| Question | Answer |
|---|---|
| What data reaches them? | Whatever prompts/completions the customer's own integration sends through the evaluation/guardrails/cost-tracking modules — entirely the customer's choice of what to send, using their own account. This application does not proxy, log, or retain prompt/completion bodies beyond what the customer's own code does (the audit log records endpoint/method/status/timing, never request/response bodies — see `ENTERPRISE_SECURITY.md`'s audit trail section). |
| Independent certification? | Per each provider's own published terms and certifications — not independently verified here since this project has no direct contractual relationship with these providers; the customer does. |
| What if a provider has an outage or breach? | Falls entirely on the customer's own relationship with that provider and their own incident response — this application's role is limited to evaluating/tracking cost for calls the customer's own code initiates. |
| Residual risk | **N/A / customer-owned** — same reasoning as the OIDC row: no vendor relationship exists between this project and the customer's chosen LLM providers to assess. |

---

## What this doesn't cover

- **No scheduled review cadence.** This assessment was written once,
  opportunistically, alongside other compliance work — not on a
  recurring calendar (annual, on each new vendor, etc.). A real gap for
  a team of one; revisit when a second person joins or a customer
  contract requires a documented cadence.
- **No formal vendor questionnaire process** (e.g., sending GCP or
  Stripe a security questionnaire directly) — this assessment relies on
  each vendor's own public certification disclosures, not a
  vendor-specific interrogation.
- **No SLA-backed vendor accountability beyond each vendor's own standard
  terms** — the GCP free-trial credit in particular carries no negotiated
  SLA; that's disclosed in `compliance/CAIQ_SELF_ASSESSMENT.md` Domain 6,
  not new information here.

This document is updated whenever the sub-processor list changes (see
`SLA.md`'s note on keeping that table and `compliance/DPA_TEMPLATE.md`
Section 2 in sync) — not left stale as marketing collateral.
