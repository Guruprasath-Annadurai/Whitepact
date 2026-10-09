# Commercial source of truth gaps

This inventory records source evidence and owner decisions still required.
Repository baseline: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
Source presence, a local test, or a document titled “production” does not establish
human commercial approval, provider activation or production availability.

## Conflicting commercial structures

`docs/phase1/PADDLE_PRODUCTION_DEPLOYMENT_REPORT.md` describes a local proposal:
Community $0; Cloud Starter $29/month or $290/year; Cloud Team $99/month or
$990/year; Enterprise / Private custom. It explicitly separates these proposals
from FREE/PRO/ENTERPRISE runtime billing enums, calls Cloud tiers Early Access
inquiries, and records no production deployment or counsel approval evidence.
Its heading “Commercial decision” is not independently verified human approval.

`web/src/features/marketing/PricingCards.tsx`,
`web/src/features/marketing/PublicPages.tsx` and generated
`src/responsibleai/dashboard/static/whitepact/pages/pricing.html` are public
presentation surfaces. Runtime billing uses `Plan.PRO` and `Plan.ENTERPRISE`
provider price mappings in `src/responsibleai/dashboard/app.py`. A public Starter
or Team card does not create a runtime entitlement or a provider product.

The owner must reconcile names, amounts, currency, billing periods, annual
discount language, entitlements, availability and provider price identifiers in
one approved commercial record. Do not silently equate Starter with PRO or Team
with ENTERPRISE, or alter product billing enums to fit marketing. Until approval
and mapping are evidenced, public copy should use inquiry/quote language and
withhold unverified paid amounts. Retain historical amounts here as evidence,
not as an offer or an approved price list.

## Provider and legal evidence gaps

| Area | Repository evidence | Required reconciliation |
|---|---|---|
| Paddle | `src/responsibleai/billing/paddle_service.py`; Paddle initialization/checkout/portal/webhook paths in `dashboard/app.py`; `web/src/lib/paddleCheckout.ts` and `paddleClientConfig.ts` | Source supports Paddle; checkout selects initialized Paddle before Stripe fallback. Owner must identify the effective provider, configured environment and approved products without exposing secrets. No production activation is proved. |
| Stripe | `src/responsibleai/billing/stripe_service.py` remains; the earlier generated privacy fallback said “current billing integration uses Stripe” | Phase-1 privacy source and generated fallback now describe Paddle-first repository billing and guarded legacy compatibility. This corrects the historical unconditional Stripe wording; actual deployed provider still requires owner reconciliation. |
| Historical deployment report | Report says no Paddle SDK/checkout created by that earlier candidate | Historical scope statement is not a description of all current code. Preserve chronology instead of treating it as a current integration inventory. |
| Seller/contact | Public legal content and existing contact address | Human owner must confirm legal seller name, address, jurisdiction, valid support/privacy contact and contracting authority. Brand name alone does not prove seller identity. |
| Terms/refunds/privacy | Public legal pages and `docs/phase1/PADDLE_WEBSITE_VERIFICATION.md` | Counsel review and owner sign-off remain external. Do not claim provider verification, statutory compliance, legal approval or certification from local rendering checks. |
| Service claims | Earlier report classifies hosted/enterprise scope as partial and guarantees/certifications as unverified | Confirm offered scope in a written agreement; no automatic SLA, response time, retention, air-gap or certification promise. |

Counsel owns legal interpretation and jurisdiction-specific approval. This phase
can improve clarity and remove contradictory copy but cannot supply that sign-off.
No checkout, provider catalog, webhook configuration, subscription, billing
entitlement or legal seller record is changed by this inventory.

## Explicit owner decision record — open

- Offer: approver, approval date, plan names, prices, currency/taxes, cadence,
  entitlements and runtime/provider mappings are not established here.
- Seller and contact: legal name, address, jurisdiction, contracting authority
  and ownership/validity of the published support/privacy address remain unverified.
- Legal review: reviewer, reviewed versions and terms/privacy/refund approval
  remain unrecorded; local website tests do not close this gate.
- Operation: deployed provider, activation, service availability and domain
  verification need their own evidence before an offer can be published.

Public inquiry copy and the existing published project email do not close these
decisions. Historical amounts above remain an inventory of proposals, not an offer.

## Closing evidence

### Owner decision table — OWNER_ACTION_REQUIRED

| Decision | Current public treatment | Approval needed |
|---|---|---|
| Community/local | MIT source and pinned local evaluation | Confirm supported distribution and support scope. |
| Hosted naming | Hosted evaluation; no public paid offer | Select approved names; map explicitly to runtime PRO/ENTERPRISE without assuming equivalence. |
| Enterprise | Requirements-led private evaluation | Confirm offered scope and contracting process. |
| Pricing and cadence | Paid amounts and annual offers withheld | Approve prices, monthly/annual cadence, renewal and cancellation wording. |
| Currency and taxes | No new currency/tax guarantee | Approve displayed currency and tax treatment for actual markets. |
| Availability | Not proved by repository code | Confirm effective deployed service and eligibility. |
| Provider | Paddle-first repository behavior, guarded legacy compatibility | Prove actual deployed processor/environment separately. |
| Seller/operator | Brand is not legal seller identity | Approve legal identity, address and contracting authority. |

### Contact decision block — OWNER_ACTION_REQUIRED

- Current mechanism: published `annaduraiguruprasath7@gmail.com` mailto and repository disclosure process. Source presence is verified; mailbox operation/ownership has not been independently tested.
- Desired future mechanism: owner-approved corporate evaluation, security and support identities; no address is invented here.
- Setup required: owner chooses addresses, provisions mailboxes/routing and proves delivery/ownership before publication.
- Copy impact: retain neutral evaluation inquiry and existing working mechanism; add no staffed desk, response-time or SLA promise until independently approved.

### Legal review — OWNER / COUNSEL APPROVAL

Terms, Privacy and Refund Policy remain published repository wording, not counsel-qualified legal advice. Review seller identity/jurisdiction, applicable privacy rights, actual processors/data handling/retention, renewal/cancellation/refund obligations and any DPA/support commitments against the real offered service. No new legal address, statutory guarantee, jurisdiction, retention guarantee or SLA is created by this phase.

Keep one owner-approved offer record with approval date and approver, product
names and status, prices/periods/taxes/renewal/cancellation, feature scope and
runtime/provider mappings. Reconcile every public React and generated fallback
surface against it. Record legal review separately, and record actual deployment
identity and provider/domain verification separately. Each gate remains open
until its own evidence exists; none follows from another gate passing.
