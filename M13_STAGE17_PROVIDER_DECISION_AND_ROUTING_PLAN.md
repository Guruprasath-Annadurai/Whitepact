# Stage 17 provider decision and routing plan

Prepared 29 Oct 2026. No provider account was opened, no live document was submitted, and no charge was made. This plan does not change production authority. Draft PRs #238, #239, #240, and #241 were not modified.

Stage 17 is not passed. The canonical 25-stage journey is not passed.

## 1. Provider comparison

List prices and coverage below are what the vendors published on the cited pages when this note was written. They are not a quote for the founder's legal entity. A dashboard price can differ by country, volume, and contract. None of these marketing claims is, by itself, NIST IAL2 or eIDAS Substantial/High evidence.

| Question | Veriff | Persona | Sumsub | Stripe Identity |
| --- | --- | --- | --- | --- |
| Official pages read | [Pricing](https://www.veriff.com/pricing), [countries](https://www.veriff.com/supported-countries), [webhooks](https://devdocs.veriff.com/docs/webhooks-guide) | [Pricing](https://withpersona.com/pricing), [IAL2 help](https://help.withpersona.com/articles/QC1OAt4zLihlELoVNJ5jmK/), [webhooks](https://docs.withpersona.com/webhooks-best-practices) | [Pricing](https://sumsub.com/pricing/), [FAQ](https://docs.sumsub.com/page/faq), [webhooks](https://docs.sumsub.com/docs/webhook-manager) | [Use cases](https://docs.stripe.com/identity/use-cases), [checks](https://docs.stripe.com/identity/verification-checks), [pricing](https://stripe.com/pricing), [webhooks](https://docs.stripe.com/webhooks) |
| Published price | Essential $0.80, Plus $1.39, Premium $1.89 per verification. Monthly minimums $49, $99, and $209. Enterprise is custom. | Essential from $250 per month, 12-month minimum. Higher plans are volume-priced. Startup program is an application, not an automatic grant. | Basic $1.35 with $149 monthly minimum. Compliance $1.85 with $299 monthly minimum. Charged for successful verifications. Custom above about 1,000 per month. | Listed $1.50 per completed ID-document and selfie verification. $0.50 per ID-number lookup, and that lookup is described as US SSN only. |
| Trial | Self-serve page says 15 days, no credit card, Premium features during the trial. | Not a public free trial on the pricing page. Evaluation is by contacting Persona. | 14 days and 50 checks. | A Stripe test-mode integration exists. The pricing page read here did not state a standing free live quota. |
| Documents and geography | Marketing: 230+ countries and territories, 12,500+ document specimens, passports, national IDs, driving licences, residence permits. | Government ID for 200+ countries and territories, plus selfie, database, and NFC checks. | FAQ: documents from 220+ countries and territories and 14,000+ types. The customer chooses which documents a level accepts. | Document checks for a published country list of government IDs, described as 120+ countries. Field extraction does not support Arabic, Chinese, Cyrillic, Greek, Hebrew, Korean, Tamil, or Thai script. |
| Business eligibility | Not stated as a closed country list on the pages read. A self-serve account still requires Veriff to accept the business. | Not stated as a closed country list. Public-sector and Kantara material is separate from a commercial KYC contract. | Not stated as a closed country list. Credit card is the published payment method for the listed plans. | Generally available only for businesses in Japan, the United Kingdom, and the United States. Self-serve public beta adds a published list that includes much of the EEA, Switzerland, Australia, Canada, and New Zealand. Industry restrictions also apply. |
| Webhook | Decision webhook is required for document and selfie IDV. `X-HMAC-SIGNATURE` over the raw body with a shared secret. | `Persona-Signature` is `t=<unix>,v1=<hmac>` over `timestamp.body`, SHA-256. Multiple secrets can be present during rotation. Events can arrive out of order. | `x-payload-digest` plus `X-Payload-Digest-Alg`. Default for a new webhook is `HMAC_SHA256_HEX`. SHA-512 is available. Older webhooks can still be SHA-1 until edited. Secret verification is optional in their dashboard and must be required by us. | `Stripe-Signature` over the raw body and the endpoint secret. Replay protection is part of Stripe's documented signature scheme. |
| Assurance claim that is actually relevant | UK DIATF is a named product in the webhook guide. The pricing page does not say a default Essential decision is NIST IAL2 or eIDAS High. | Kantara approval for IAL2 proofing, assessed under NIST SP 800-63A revision 3, identity proofing only. Persona says its IAL2 templates are not fully compliant out of the box and the customer remains responsible. eIDAS is named as a separate regional standard, not as something the template automatically meets. | The pages read describe ID, liveness, face match, and optional AML. They do not claim NIST IAL2 or eIDAS Substantial/High for the Basic plan. | Document, selfie, and data checks for fraud and KYC support. The pages read do not claim NIST IAL2 or eIDAS. |

Ordinary login, email OTP, and a vendor "verified" badge are not IAL2. IAL2, in NIST SP 800-63A, is remote or in-person proofing that binds a person to evidence at that level. eIDAS Substantial and High are EU assurance levels for electronic identification. A document-and-selfie product can be configured toward those levels. Buying the cheapest plan does not establish that it has been.

## 2. Business eligibility unknowns

These are blocking, and they are not assumed:

- The founder's legal entity, its country of incorporation, and the countries where customers will be proofed.
- Whether that entity is in a prohibited industry for the chosen vendor.
- Whether Stripe Identity's business-location rule excludes the entity. If the entity is outside the generally available and public-beta lists, Stripe Identity is not an eligible candidate until Stripe says otherwise.
- Which customer documents must work on day one, including non-Latin scripts Stripe says it does not extract.
- Whether the required assurance is fraud-screening document checks, NIST IAL2, eIDAS Substantial, or eIDAS High.
- Data-processing role, retention, subprocessors, and whether EU or India data residency is required. Persona lists EU hosting as a higher-plan option. The other three need a data-processing addendum before production.
- Who may sign the vendor contract and who may hold the API secret.
- Sanctions and age rules for the customer population.

Until those are answered, no vendor is selected.

## 3. Existing routing defect

`src/responsibleai/enterprise/router.py` function `_verification` always does this:

```python
secret = identity_webhook_secret_from_env()
return VerificationService(get_enterprise_engine(), HmacVerificationProvider(secret))
```

It never reads `WHITEPACT_IDENTITY_APPROVED_PROVIDERS`, `WHITEPACT_IDENTITY_PROVIDER_NAME`, or `HttpCallbackIdentityProvider.from_env`. The same hard-wiring appears in `EnterpriseIAM.create_api_key`, `service.py` around the other `HmacVerificationProvider` constructions, and the webhook secret helper path.

`HmacVerificationProvider.name` is `hmac-reference`. `identity_assurance_accepted` rejects that name in production and rejects it in development unless `WHITEPACT_IDENTITY_REFERENCE_CONTRACT=1`. So a live Veriff, Persona, Sumsub, or Stripe webhook cannot become `IDENTITY_VERIFIED` through this constructor: the signature check is the reference HMAC, not the vendor signature, and the stored provider name would be the reference name.

That is a fail-closed gap, not a production identity proof. It is also the wrong place to "just set the reference switch". The reference switch is a development contract. It must not be treated as a commercial provider.

`HttpCallbackIdentityProvider` already refuses `hmac-reference` and refuses insecure production URLs. It is a generic HTTP client. It is not a Veriff, Persona, Sumsub, or Stripe signature adapter, and it must not be relabelled as one.

## 4. Proposed fail-closed implementation

Do not apply this until the founder names a provider and the CTO accepts the contract.

Selection, in order:

1. If the process is production, ignore `hmac-reference` and ignore `WHITEPACT_IDENTITY_REFERENCE_CONTRACT`.
2. If the approved-provider set is empty, refuse session start and webhook intake with the existing not-enrolled error. Do not construct a provider.
3. If the only approved provider is `hmac-reference`, allow `HmacVerificationProvider` only outside production and only when the reference switch is on.
4. If the approved set contains exactly one commercial name, construct that vendor's adapter. The adapter's `name` must equal that approved name. An unknown name, or two commercial names, refuses.
5. The vendor adapter verifies the raw body with that vendor's header and algorithm, checks the timestamp window, and returns one canonical event: `event_id`, `subject_id` equal to the pending WhitePact session, vendor session id, decision, and an assurance level that is in `WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS`.
6. Existing `VerificationService` rules stay: pending session required, approved provider and level required, replay key on the provider event, expiry, suspension, and no elevation from a column write alone.
7. A vendor "approved" or `GREEN` or `verified` status maps to `IDENTITY_VERIFIED` only when step 5 accepted the assurance level. Otherwise the outcome is `REVIEW_REQUIRED` or `REJECTED` and credential issuance stays closed.

Files that would change after approval, and not before:

- `src/responsibleai/enterprise/router.py` — `_verification` only.
- `src/responsibleai/enterprise/service.py` — the three `HmacVerificationProvider` call sites, to call the same selector.
- `src/responsibleai/enterprise/identity_providers/` — one new module per approved vendor. No module in this plan.
- `tests/test_m13_identity_provider_selection.py` — new tests listed below.

The selector must not add `hmac-reference` to the production allowlist and must not mark a user verified in the adapter.

Proposed negative tests, to be added with the selector, not before:

- Production plus `WHITEPACT_IDENTITY_PROVIDER_NAME=veriff` and a valid reference HMAC still does not verify.
- An approved name with no registered adapter returns not-enrolled and writes no `IDENTITY_VERIFIED` row.
- A vendor payload whose signature is valid but whose session id does not match the pending row is rejected and the row stays pending.
- A replay of an accepted `event_id` does not create a second verification.
- Two approved commercial names fail closed.

## 5. Privacy and assurance requirements

- The webhook endpoint stores the vendor event id, decision, and assurance level. It does not need the document image in the WhitePact database. Prefer vendor-hosted images and a short retention setting in the vendor account.
- Sign a data-processing agreement before any real end-user document is sent.
- Biometric consent must be explicit where the customer's law requires a non-biometric alternative. Stripe's own go-live notes say this for some jurisdictions.
- Assurance configuration is an allowlist, not a vendor adjective. Suggested values to choose from, not to enable now: `document-selfie-vendor`, `nist-ial2`, `eidas-substantial`, `eidas-high`. Only the value the founder and CTO name may be added to `WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS`.
- Kantara or UK DIATF evidence, if it is the requirement, must be the vendor's current certificate for the exact flow we enable, not a blog post.

## 6. Minimum real-provider acceptance test

After approval, in the vendor's test or sandbox environment, with no production WhitePact traffic:

1. Create one pending WhitePact session for a disposable test user.
2. Complete the vendor's sandbox flow with the vendor's synthetic document, not a real passport or national ID.
3. Deliver the signed sandbox webhook once. The stored provider name equals the approved vendor, the assurance level equals the approved level, and the status becomes `IDENTITY_VERIFIED` only for that session.
4. Replay the same webhook. No second row and no second issuance.
5. Send a webhook with a bad signature, a stale timestamp, a different subject, and an unapproved assurance string. Each leaves the user unverified.
6. Attempt credential issuance before the webhook and after a rejected webhook. Both fail with the existing identity gate.
7. Confirm production configuration still rejects `hmac-reference`.

Sandbox success is not Stage 17 closure. Closure still needs the founder-approved entity, the signed contract, and a recorded assurance decision.

## 7. Founder decisions required

1. Legal entity and country.
2. Customer countries and the document types that must work.
3. Required assurance level: vendor document-and-selfie, NIST IAL2, eIDAS Substantial, or eIDAS High.
4. One provider to take to contract. This plan does not choose one.
5. Approval to pay that vendor's minimum and per-check price.
6. Approval of the data-processing terms and retention period.
7. The DCO choice in section 8, if hosted DCO must go green before Stage 17.

## 8. DCO decision for `39619c4b`

Commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` is `docs(security): publish WhitePact M13-S4 enterprise security qualification and Codex handoff suite`, authored by Techezz Infos `<Techezzinfos@gmail.com>` at 15 Oct 2026, 6:41 PM IST. The message has no `Signed-off-by` trailer. The hosted I1 DCO job fails on that commit. A later commit with a trailer does not repair it, because the check walks every commit in the range.

Choices, none of which is done here:

- The author adds a `Signed-off-by` trailer for that commit. That rewrites history and needs the author's and the repository owner's agreement. It is not done from this agent.
- Replace the range with a new history in which that commit's tree is reused under a properly signed commit. That is also a history rewrite and needs the same agreement.
- The founder records an explicit, narrow exception for this one SHA in the DCO workflow. That is an owner policy change. It is not a silent skip, and it is not implemented in this change.
- Leave the job red until one of the above happens.

No exception was added and no commit was rewritten.

## 9. Verification of this note

This change is a document. It does not alter `router.py`, the assurance allowlist, or Stage 19. Reviewers can confirm the defect by reading `_verification` and the `HmacVerificationProvider` constructor call sites named above.

M13 remains open. Production remains no-go. M14 is not authorized.
