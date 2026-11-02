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

## Render (compute)

**Updated 2026-07-23**: the live reference deployment's actual compute
vendor, chosen after both Oracle Cloud and Google Cloud's signup flows
required a payment card the founder didn't have. Render, Supabase, and
Upstash together replace the single-VM architecture with three
card-free managed services — a real architectural change, not a rename.

**Role**: builds and runs `Dockerfile` on every push to `main`
(`autoDeploy: yes`), serving `https://responsibleai-dashboard.onrender.com`.
Free tier: shared CPU, **no persistent local disk** — this is the direct
cause of the Postgres-to-Supabase decision below, proven the hard way
(the first deploy's in-container SQLite data was lost on the very next
redeploy).

| Question | Answer |
|---|---|
| What data reaches them? | The running application and whatever it holds in memory/logs. No database data lives on Render itself (see Supabase, below) — but request/response bodies pass through its compute at runtime. |
| Independent certification? | SOC 2 Type II compliant, ISO/IEC 27001 certified — see [render.com/docs/certifications-compliance](https://render.com/docs/certifications-compliance), checked directly. |
| What if Render has an outage? | Single free-tier instance, no redundancy — a Render outage is a platform outage. Free tier also has no SLA uptime commitment from Render itself. |
| What if Render has a breach affecting us? | Render's own incident-notification obligations under its customer terms apply, not separately negotiated. Practically: rotate all secrets (API keys, database credentials) immediately, treat as P1 per `compliance/INCIDENT_RESPONSE_RUNBOOK.md`. |
| Residual risk | **Medium** — free-tier vendor lock-in and no redundancy, offset by verified SOC 2/ISO 27001 certification. Appropriate for pre-revenue stage; paid tier removes the "no persistent disk / shared CPU" constraints once justified. |
| Alternative considered? | Yes — chosen specifically because its free tier requires no card, unlike OCI/GCP's signup flows. Any VPS provider remains a viable alternative once budget allows. |

---

## Supabase (database)

**Role**: managed PostgreSQL for the live reference deployment, accessed
via its transaction-mode connection pooler (`aws-1-us-west-2.pooler.supabase.com:6543`)
rather than the direct host — the direct host resolves IPv6-only and is
unreachable from Render's network, discovered live during this
deployment (see `DEPLOY_RUNBOOK.md`). This is where all persistent
governance data actually lives.

| Question | Answer |
|---|---|
| What data reaches them? | Everything the application persists — trust scores, audit logs, organization/API key metadata, incident records, all governance tables. Full access in principle (as with any managed database host), governed by Supabase's own personnel/access controls, not ours. |
| Independent certification? | SOC 2 Type II, ISO 27001, HIPAA, and PCI DSS certified — see [supabase.com/docs/guides/security/soc-2-compliance](https://supabase.com/docs/guides/security/soc-2-compliance), checked directly. |
| What if Supabase has an outage? | Single-project, single-region deployment with no cross-region failover configured — a Supabase outage is a platform outage. Free-tier projects also pause after a period of inactivity per Supabase's own policy — check current terms before relying on this for anything beyond early-stage use. |
| What if Supabase has a breach affecting us? | Supabase's own incident-notification obligations under its customer terms apply. Practically: rotate the database password immediately (this also breaks the connection string everywhere it's configured — plan for that), treat as P1 per `compliance/INCIDENT_RESPONSE_RUNBOOK.md`. |
| A real, already-encountered technical risk | The transaction-mode pooler is incompatible with asyncpg's default prepared-statement caching — fixed in code (`statement_cache_size=0` in both `db/engine.py` and `migrations/env.py`), but worth flagging here as the kind of integration risk a managed-pooler architecture introduces that a direct database connection wouldn't. |
| Residual risk | **Medium** — free-tier vendor lock-in and pooler-specific integration risk (now mitigated in code), offset by strong, verified certification status (SOC 2 Type II + ISO 27001 + HIPAA + PCI DSS is a notably strong set for a free-tier database vendor). |
| Alternative considered? | Yes — chosen specifically for its card-free free tier; any managed Postgres provider (RDS, Cloud SQL, Neon, etc.) remains viable once budget allows. |

---

## Upstash (cache / rate-limit backend)

**Role**: managed Redis for the shared rate-limit backend (`RAI_REDIS_URL`),
replacing the in-memory limiter so rate limits are enforced consistently
even if the app runs multiple replicas in the future.

| Question | Answer |
|---|---|
| What data reaches them? | Rate-limit counters only — no governance data, PII, or credentials are stored in Redis. |
| Independent certification? | **No independently verified certification found as of this review** — stated honestly rather than assumed or guessed. Re-check Upstash's own current security/compliance documentation before citing this vendor in a customer-facing security review. |
| What if Upstash has an outage? | Rate limiting would fail open or closed depending on `limits` library behavior on a backend connection failure — not explicitly tested against a real Upstash outage as of this review; worth a deliberate test before relying on this in a customer-facing SLA conversation. |
| What if Upstash has a breach affecting us? | Since only rate-limit counters are stored, the practical blast radius is low — but rotate the Redis credential and treat as at least a P3 per `compliance/INCIDENT_RESPONSE_RUNBOOK.md` regardless. |
| Residual risk | **Low** — minimal data exposure (counters only), though the certification gap above means this vendor's own security posture is less independently verifiable than Render's or Supabase's. |
| Alternative considered? | Yes — chosen for its card-free free tier and native Redis TCP protocol support (unlike some serverless Redis competitors that are REST-API-only, which wouldn't work with this app's existing `limits[redis]`-based rate limiter without a code change). |

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
- **No formal vendor questionnaire process** (e.g., sending Render,
  Supabase, Upstash, or Stripe a security questionnaire directly) — this
  assessment relies on each vendor's own public certification
  disclosures, not a vendor-specific interrogation.
- **No SLA-backed vendor accountability beyond each vendor's own standard
  terms** — all three infrastructure vendors' free tiers carry no
  negotiated SLA; that's disclosed in `compliance/CAIQ_SELF_ASSESSMENT.md`
  Domain 6, not new information here.

This document is updated whenever the sub-processor list changes (see
`SLA.md`'s note on keeping that table and `compliance/DPA_TEMPLATE.md`
Section 2 in sync) — not left stale as marketing collateral.
